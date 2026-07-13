"""Async IMAP poller that monitors a mailbox for new emails and processes them."""

from __future__ import annotations

import asyncio
from typing import Optional

import aioimaplib
import httpx

from email_worker.api_client.ticket_client import TicketClient
from email_worker.config.settings import settings
from email_worker.imap.parser import parse_email
from email_worker.models.email_models import ParsedEmail
from email_worker.models.event_models import (
    ClassifyResponse,
    TicketCreatePayload,
    TimelineEventPayload,
)
from email_worker.smtp.sender import EmailSender
from email_worker.storage.message_store import message_store
from email_worker.thread.resolver import resolve_thread
from email_worker.utils.logger import logger


def _soc_routing_rule(classify: ClassifyResponse) -> str:
    """Apply SOC routing logic: if cybersecurity + critical, route to security team.

    Args:
        classify: The AI classification result.

    Returns:
        The team to assign, potentially overridden by SOC rules.
    """
    if (
        classify.category.lower() == "cybersecurity"
        and classify.priority.lower() == "critical"
    ):
        logger.info(
            "SOC routing rule triggered: cybersecurity + critical -> security team"
        )
        return "security"
    return classify.team


def _email_description(email_data: ParsedEmail) -> str:
    description = (email_data.plain_text_body or email_data.html_body or "").strip()
    if description:
        return description
    return email_data.subject or "(no email body)"


class IMAPPoller:
    """Async IMAP mailbox poller that fetches and processes unread emails."""

    def __init__(
        self,
        ticket_client: Optional[TicketClient] = None,
        email_sender: Optional[EmailSender] = None,
    ) -> None:
        self.host = settings.imap_host
        self.port = settings.imap_port
        self.user = settings.imap_user
        self.password = settings.imap_password
        self.poll_interval = settings.imap_poll_interval_seconds
        self.ticket_client = ticket_client or TicketClient()
        self.email_sender = email_sender or EmailSender()
        self._client: Optional[aioimaplib.IMAP4_SSL] = None
        self._running = False

    async def _connect(self) -> aioimaplib.IMAP4_SSL:
        """Connect to the IMAP server and login.

        Returns:
            An authenticated IMAP4_SSL client.

        Raises:
            ConnectionError: If connection or login fails.
        """
        logger.info(
            "Connecting to IMAP server %s:%d as %s",
            self.host,
            self.port,
            self.user,
        )
        try:
            if self.port == 993:
                client = aioimaplib.IMAP4_SSL(host=self.host, port=self.port)
            else:
                client = aioimaplib.IMAP4(host=self.host, port=self.port)

            await client.wait_hello_from_server()
            await client.login(self.user, self.password)
            await client.select("INBOX")
            logger.info("IMAP connection established and INBOX selected")
            return client
        except (ConnectionRefusedError, TimeoutError, OSError) as e:
            logger.error("IMAP connection failed: %s", e)
            raise ConnectionError(f"IMAP connection failed: {e}") from e
        except aioimaplib.AioImapException as e:
            logger.error("IMAP login failed: %s", e)
            raise ConnectionError(f"IMAP login failed: {e}") from e

    async def _ensure_connected(self) -> aioimaplib.IMAP4_SSL:
        """Ensure we have an active IMAP connection, reconnecting if needed.

        Returns:
            An authenticated IMAP client.
        """
        if self._client is None:
            self._client = await self._connect()
            return self._client

        try:
            await self._client.noop()
        except (aioimaplib.AioImapException, OSError, EOFError):
            logger.warning("IMAP connection lost, reconnecting...")
            try:
                await self._client.logout()
            except Exception:
                pass
            self._client = await self._connect()

        return self._client

    async def _fetch_unseen_uids(self) -> list:
        """Fetch UIDs of unseen (unread) emails in the inbox.

        Returns:
            A list of UID strings for unseen messages.
        """
        client = await self._ensure_connected()
        try:
            status, data = await client.search("UNSEEN")
            if status != "OK":
                logger.warning("IMAP search for UNSEEN returned status: %s", status)
                return []

            if not data or not data[0]:
                return []

            uid_str = data[0].decode() if isinstance(data[0], bytes) else str(data[0])
            return uid_str.split() if uid_str.strip() else []

        except (aioimaplib.AioImapException, OSError, EOFError) as e:
            logger.error("Failed to fetch unseen emails: %s", e)
            self._client = None
            return []

    async def _fetch_email_by_uid(self, uid: str) -> Optional[bytes]:
        """Fetch a single email by its UID.

        Args:
            uid: The IMAP UID of the email.

        Returns:
            Raw email bytes if found, otherwise None.
        """
        client = await self._ensure_connected()
        try:
            status, data = await client.fetch(uid, "(RFC822)")
            if status != "OK" or not data:
                logger.warning("Failed to fetch UID %s: status=%s", uid, status)
                return None

            logger.info("IMAP fetch response for UID %s: %s", uid, str(data)[:200])

            for part in data:
                # Handle tuple format FIRST: (b'126 FETCH (RFC822 {6994}', bytearray(...))
                # The tuple[1] contains the actual email, tuple[0] is just the IMAP response line
                if isinstance(part, tuple) and len(part) >= 2:
                    if isinstance(part[1], (bytes, bytearray)):
                        email_bytes = bytes(part[1]) if isinstance(part[1], bytearray) else part[1]
                        logger.info("✓ Extracted %d bytes from tuple[1] (type: %s)", len(email_bytes), type(part[1]).__name__)
                        return email_bytes
                # Handle direct bytes (fallback for simpler IMAP responses)
                elif isinstance(part, (bytes, bytearray)):
                    # Skip small bytes that look like IMAP protocol responses
                    if len(part) < 100:
                        logger.debug("Skipping small bytes part: %d bytes", len(part))
                        continue
                    email_bytes = bytes(part) if isinstance(part, bytearray) else part
                    logger.info("✓ Extracted %d bytes from IMAP response (type: %s)", len(email_bytes), type(part).__name__)
                    return email_bytes

            logger.warning("No email content found in fetch response for UID %s", uid)
            logger.warning("Data structure: %s", [type(p).__name__ for p in data])
            return None

        except (aioimaplib.AioImapException, OSError, EOFError) as e:
            logger.error("Failed to fetch email UID %s: %s", uid, e)
            self._client = None
            return None

    async def _mark_as_seen(self, uid: str) -> None:
        """Mark an email as seen (add \\Seen flag).

        Args:
            uid: The IMAP UID of the email.
        """
        try:
            client = await self._ensure_connected()
            await client.store(uid, "+FLAGS", "(\\Seen)")
            logger.debug("Marked UID %s as seen", uid)
        except Exception as e:
            logger.warning("Failed to mark UID %s as seen: %s", uid, e)

    async def _process_new_email(self, email_data: ParsedEmail) -> None:
        """Process a new (non-reply) email: classify, SOC route, create ticket, send ack.

        Args:
            email_data: The parsed email data.
        """
        logger.info(
            "Processing new email from %s: %s",
            email_data.from_address,
            email_data.subject,
        )

        try:
            classify = await asyncio.wait_for(
                self.ticket_client.classify_email(
                    subject=email_data.subject,
                    description=_email_description(email_data),
                ),
                timeout=60.0,
            )
        except asyncio.TimeoutError:
            logger.warning(
                "Classification timed out for email from %s, using fallback",
                email_data.from_address,
            )
            classify = ClassifyResponse(
                category="general_it", priority="medium", risk_level="standard", team="it"
            )
        except Exception as e:
            logger.warning(
                "Classification failed for email from %s: %s. Using fallback.",
                email_data.from_address,
                e,
            )
            classify = ClassifyResponse(
                category="general_it", priority="medium", risk_level="standard", team="it"
            )
        logger.info(
            "Classification result: category=%s, priority=%s, team=%s",
            classify.category,
            classify.priority,
            classify.team,
        )

        team = _soc_routing_rule(classify)

        description = _email_description(email_data)

        # Append attachment metadata to the description so it is visible on the ticket
        if email_data.attachments:
            attachment_lines = ["\n\n--- Attachments ---"]
            for att in email_data.attachments:
                size_kb = att.size / 1024
                attachment_lines.append(
                    f"  • {att.filename} ({att.content_type}, {size_kb:.1f} KB)"
                )
            description += "\n".join(attachment_lines)

        ticket_payload = TicketCreatePayload(
            subject=email_data.subject,
            description=description,
            requester_email=email_data.from_address,
            category=classify.category,
            priority=classify.priority,
            risk_level=classify.risk_level,
            team=team,
        )

        try:
            ticket = await self.ticket_client.create_ticket(ticket_payload)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 409:
                try:
                    error_data = e.response.json()
                except Exception:
                    error_data = {}
                if isinstance(error_data, dict) and error_data.get("error") == "duplicate_ticket":
                    existing_number = error_data.get("existing_ticket_number", "")
                    existing_status = error_data.get("existing_ticket_status", "")
                    logger.warning(
                        "Duplicate ticket detected for email from %s: existing=%s",
                        email_data.from_address,
                        existing_number,
                    )
                    try:
                        await self.email_sender.send_duplicate_notice_email(
                            to_email=email_data.from_address,
                            to_name=email_data.from_address,
                            existing_ticket_number=existing_number,
                            existing_ticket_status=existing_status,
                            existing_ticket_subject=email_data.subject,
                        )
                        logger.info(
                            "Duplicate notice email sent to %s for existing ticket %s",
                            email_data.from_address,
                            existing_number,
                        )
                    except Exception as email_err:
                        logger.error("Failed to send duplicate notice email: %s", email_err)
                    return
            raise

        # Use ticket_number (SPS-2026-116) instead of id (UUID) for user-facing references
        ticket_number: str = ticket.get("ticket_number", "")
        ticket_uuid: str = ticket.get("id", "")

        if not ticket_number or not ticket_uuid:
            logger.error("Ticket created but missing number or ID: %s", ticket)
            return

        logger.info(
            "Ticket %s (ID: %s) created from email from %s",
            ticket_number,
            ticket_uuid,
            email_data.from_address,
        )

        # Send the acknowledgement directly from the IMAP worker so the
        # requester gets confirmation even if the backend event listener lags.
        try:
            await self.email_sender.send_ack_email(
                to_email=email_data.from_address,
                ticket_id=ticket_number,
                subject=email_data.subject,
                requester_name=email_data.from_name or email_data.from_address,
            )
            logger.info(
                "ACK email sent directly for email-created ticket %s",
                ticket_number,
            )
        except Exception as email_err:
            logger.error(
                "Failed to send direct ACK email for ticket %s: %s",
                ticket_number,
                email_err,
                exc_info=True,
            )

        # Upload email attachments as actual files
        if email_data.attachments and ticket_uuid:
            try:
                for att in email_data.attachments:
                    if att.content:
                        await self.ticket_client.upload_attachment(ticket_uuid, att)
            except Exception as attach_err:
                logger.warning(
                    "Failed to upload some email attachments: %s",
                    attach_err,
                    exc_info=True,
                )

        if email_data.message_id:
            message_store.save_message_mapping(
                email_data.message_id, ticket_number
            )

        # Ack is now sent by the event_listener via the backend event feed,
        # so we no longer send it directly from the IMAP poller.

    async def _process_reply_email(
        self, email_data: ParsedEmail, ticket_id: str
    ) -> None:
        """Process a reply email: append to ticket timeline.

        Args:
            email_data: The parsed email data.
            ticket_id: The resolved ticket ID (e.g. SPS-2026-001).
        """
        logger.info(
            "Processing reply to ticket %s from %s",
            ticket_id,
            email_data.from_address,
        )

        content = email_data.plain_text_body or email_data.html_body or "(no content)"

        event_payload = TimelineEventPayload(
            event_type="email_reply",
            content=content,
        )

        try:
            await self.ticket_client.append_timeline_event(
                ticket_id, event_payload
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 409:
                try:
                    error_data = e.response.json()
                except Exception:
                    error_data = {}
                if isinstance(error_data, dict):
                    ticket_status = error_data.get("status", "closed")
                    ticket_number = error_data.get("ticket_number", ticket_id)
                else:
                    ticket_status = "closed"
                    ticket_number = ticket_id

                logger.warning(
                    "Ticket %s is %s, cannot append reply. Sending locked notice.",
                    ticket_number,
                    ticket_status,
                )
                try:
                    await self.email_sender.send_ticket_locked_email(
                        to_email=email_data.from_address,
                        to_name=email_data.from_address,
                        ticket_number=ticket_number,
                        ticket_status=ticket_status,
                    )
                except Exception as email_err:
                    logger.error("Failed to send locked email notice: %s", email_err)
                return
            raise

        if email_data.message_id:
            message_store.save_message_mapping(
                email_data.message_id, ticket_id
            )

        logger.info(
            "Reply appended to ticket %s from %s",
            ticket_id,
            email_data.from_address,
        )

    async def poll_once(self) -> int:
        """Poll the IMAP inbox for new emails and process them.

        Returns:
            The number of emails processed in this poll cycle.
        """
        logger.info("=== Starting poll cycle ===")
        try:
            uids = await self._fetch_unseen_uids()
        except ConnectionError as e:
            logger.error("Cannot poll IMAP: %s", e)
            return 0

        logger.info("Found %d unseen UIDs", len(uids))
        if not uids:
            return 0

        logger.info("Processing %d unseen emails", len(uids))
        processed = 0

        for uid in uids:
            logger.info("Starting to process UID %s", uid)
            try:
                logger.info("Fetching email UID %s", uid)
                raw_email = await self._fetch_email_by_uid(uid)
                if raw_email is None:
                    logger.warning("No raw email for UID %s, marking as seen", uid)
                    await self._mark_as_seen(uid)
                    continue

                logger.info("Parsing email UID %s", uid)
                try:
                    email_data = await asyncio.wait_for(
                        asyncio.get_event_loop().run_in_executor(None, parse_email, raw_email),
                        timeout=10.0,
                    )
                except asyncio.TimeoutError:
                    logger.error("Email parsing timed out for UID %s, will retry on next poll", uid)
                    continue

                if email_data is None:
                    logger.warning("Failed to parse email UID %s, will retry on next poll", uid)
                    continue

                logger.info("Parsed email UID %s: from=%s, subject=%s", uid, email_data.from_address, email_data.subject[:50])

                # Skip emails from helpdesk itself to prevent loops
                if email_data.from_address == self.user:
                    logger.warning("Skipping email from helpdesk address (loop prevention): %s", uid)
                    await self._mark_as_seen(uid)
                    processed += 1
                    continue

                if email_data.message_id:
                    message_store.save_message_mapping(
                        email_data.message_id, "pending"
                    )

                logger.info("Resolving thread for UID %s", uid)
                try:
                    thread_type, ticket_id = await asyncio.wait_for(
                        asyncio.get_event_loop().run_in_executor(None, resolve_thread, email_data),
                        timeout=10.0,
                    )
                except asyncio.TimeoutError:
                    logger.error("Thread resolution timed out for UID %s", uid)
                    await self._mark_as_seen(uid)
                    continue

                logger.info("Thread resolved for UID %s: type=%s, ticket=%s", uid, thread_type, ticket_id)

                if thread_type == "new":
                    logger.info("Processing as new email UID %s", uid)
                    await self._process_new_email(email_data)
                elif thread_type == "reply" and ticket_id:
                    logger.info("Processing as reply UID %s -> %s", uid, ticket_id)
                    await self._process_reply_email(email_data, ticket_id)
                else:
                    logger.warning(
                        "Unhandled thread resolution: type=%s, ticket=%s",
                        thread_type,
                        ticket_id,
                    )

                logger.info("Marking UID %s as seen after successful processing", uid)
                await self._mark_as_seen(uid)
                processed += 1
                logger.info("Finished processing UID %s", uid)

            except Exception as e:
                logger.error(
                    "Error processing email UID %s: %s", uid, e, exc_info=True
                )
                import traceback
                logger.error("Full traceback:\n%s", traceback.format_exc())

                # Only mark as seen if this is a permanent error (bad email format)
                # Leave transient errors (backend down, network issues) unread for retry
                error_msg = str(e).lower()
                if "connection" not in error_msg and "timeout" not in error_msg and "unreachable" not in error_msg:
                    logger.warning("Marking UID %s as seen due to permanent error", uid)
                    try:
                        await self._mark_as_seen(uid)
                    except Exception:
                        pass
                else:
                    logger.info("Leaving UID %s unread for retry (transient error)", uid)

        return processed

    async def start_polling(self) -> None:
        """Start the continuous polling loop. Runs indefinitely."""
        self._running = True
        logger.info(
            "IMAP poller started: polling every %d seconds",
            self.poll_interval,
        )

        while self._running:
            try:
                count = await self.poll_once()
                if count > 0:
                    logger.info("Poll cycle complete: %d emails processed", count)
            except Exception as e:
                logger.error(
                    "Poll cycle failed: %s. Will retry in %ds.",
                    e,
                    self.poll_interval,
                    exc_info=True,
                )

            await asyncio.sleep(self.poll_interval)

        logger.info("IMAP poller stopped")

    async def stop(self) -> None:
        """Gracefully stop the poller and close connections."""
        self._running = False
        if self._client:
            try:
                await self._client.logout()
            except Exception:
                pass
            self._client = None
        await self.ticket_client.close()
        logger.info("IMAP poller shut down")
