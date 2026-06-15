"""Async IMAP poller that monitors a mailbox for new emails and processes them."""

from __future__ import annotations

import asyncio
import email
from typing import Optional, Set

import aioimaplib

from email_worker.api_client.ticket_client import TicketClient
from email_worker.config.settings import settings
from email_worker.imap.parser import parse_email
from email_worker.models.email_models import ParsedEmail
from email_worker.models.event_models import (
    ClassifyResponse,
    TicketCreatePayload,
    TimelineEventPayload,
)
from email_worker.storage.message_store import message_store
from email_worker.thread.resolver import resolve_thread
from email_worker.utils.logger import logger
from email_worker.utils.retry import async_retry


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


class IMAPPoller:
    """Async IMAP mailbox poller that fetches and processes unread emails."""

    def __init__(
        self,
        ticket_client: Optional[TicketClient] = None,
    ) -> None:
        self.host = settings.imap_host
        self.port = settings.imap_port
        self.user = settings.imap_user
        self.password = settings.imap_password
        self.poll_interval = settings.imap_poll_interval_seconds
        self.ticket_client = ticket_client or TicketClient()
        self._client: Optional[aioimaplib.IMAP4_SSL] = None
        self._running = False
        self._processed_uids: Set[str] = set()

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
        except aioimaplib.AioimapException as e:
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
            # Check connection by sending a noop
            await self._client.noop()
        except (aioimaplib.AioimapException, OSError, EOFError):
            logger.warning("IMAP connection lost, reconnecting...")
            try:
                await self._client.logout()
            except Exception:
                pass
            self._client = await self._connect()

        return self._client

    async def _fetch_unseen_uids(self) -> list[str]:
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

        except (aioimaplib.AioimapException, OSError, EOFError) as e:
            logger.error("Failed to fetch unseen emails: %s", e)
            # Reset client to force reconnect next time
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

            # aioimaplib returns tuples of (flags, body_bytes)
            for part in data:
                if isinstance(part, tuple) and len(part) >= 1:
                    # The second element is typically the raw email bytes
                    raw = part[1] if len(part) > 1 else part[0]
                    if isinstance(raw, bytes):
                        return raw

            return None

        except (aioimaplib.AioimapException, OSError, EOFError) as e:
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

        # Step 1: AI Classification
        classify = await self.ticket_client.classify_email(
            subject=email_data.subject,
            description=email_data.plain_text_body or email_data.html_body or "",
        )
        logger.info(
            "Classification result: category=%s, priority=%s, team=%s",
            classify.category,
            classify.priority,
            classify.team,
        )

        # Step 2: SOC Routing Rule
        team = _soc_routing_rule(classify)

        # Step 3: Create ticket
        ticket_payload = TicketCreatePayload(
            subject=email_data.subject,
            description=email_data.plain_text_body or email_data.html_body or "",
            requester_email=email_data.from_address,
            category=classify.category,
            priority=classify.priority,
            team=team,
        )

        ticket = await self.ticket_client.create_ticket(ticket_payload)
        ticket_id: str = ticket.get("id", ticket.get("ticket_id", ""))

        if not ticket_id:
            logger.error("Ticket created but no ID returned: %s", ticket)
            return

        logger.info(
            "Ticket %s created from email from %s",
            ticket_id,
            email_data.from_address,
        )

        # Store the original email's Message-ID so replies can be tracked
        if email_data.message_id:
            message_store.save_message_mapping(
                email_data.message_id, ticket_id
            )

        # Step 4: Send acknowledgment email
        try:
            from email_worker.smtp.sender import EmailSender
            sender = EmailSender()
            await sender.send_ack_email(
                to_email=email_data.from_address,
                ticket_id=ticket_id,
                subject=email_data.subject,
                requester_name=email_data.from_address,
            )
            logger.info(
                "Acknowledgment email sent for ticket %s", ticket_id
            )
        except Exception as e:
            logger.error(
                "Failed to send ack email for ticket %s: %s", ticket_id, e
            )

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

        await self.ticket_client.append_timeline_event(
            ticket_id, event_payload
        )

        # Store the reply's Message-ID for future thread tracking
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
        try:
            uids = await self._fetch_unseen_uids()
        except ConnectionError as e:
            logger.error("Cannot poll IMAP: %s", e)
            return 0

        if not uids:
            return 0

        # Filter already-processed UIDs within this session
        new_uids = [uid for uid in uids if uid not in self._processed_uids]

        if not new_uids:
            logger.debug("All %d unseen UIDs already processed this session", len(uids))
            return 0

        logger.info("Processing %d new unseen emails", len(new_uids))
        processed = 0

        for uid in new_uids:
            try:
                raw_email = await self._fetch_email_by_uid(uid)
                if raw_email is None:
                    continue

                email_data = parse_email(raw_email)
                if email_data is None:
                    logger.warning("Failed to parse email UID %s, marking seen", uid)
                    await self._mark_as_seen(uid)
                    self._processed_uids.add(uid)
                    continue

                # Store message ID for the inbound email
                if email_data.message_id:
                    message_store.save_message_mapping(
                        email_data.message_id, "inbound"
                    )

                # Resolve thread: new or reply
                thread_type, ticket_id = resolve_thread(email_data)

                if thread_type == "new":
                    await self._process_new_email(email_data)
                elif thread_type == "reply" and ticket_id:
                    await self._process_reply_email(email_data, ticket_id)
                else:
                    logger.warning(
                        "Unhandled thread resolution: type=%s, ticket=%s",
                        thread_type,
                        ticket_id,
                    )

                await self._mark_as_seen(uid)
                self._processed_uids.add(uid)
                processed += 1

            except Exception as e:
                logger.error(
                    "Error processing email UID %s: %s", uid, e, exc_info=True
                )
                # Still mark as seen to avoid repeated failures
                try:
                    await self._mark_as_seen(uid)
                except Exception:
                    pass

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