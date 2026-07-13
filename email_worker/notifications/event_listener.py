"""Backend event listener that polls for email events and sends outbound notifications."""

from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional

from email_worker.api_client.ticket_client import TicketClient
from email_worker.config.settings import settings
from email_worker.models.event_models import BackendEvent, TimelineEventPayload
from email_worker.smtp.sender import EmailSender
from email_worker.utils.logger import logger


def _redirect_for_real_delivery(email: str) -> str:
    """Redirect placeholder @sps.com addresses to a real test inbox.

    Only affects placeholder @sps.com test addresses — real recipient
    domains (anything a real requester/approver actually typed in) are
    always left untouched, even when a redirect base is configured.
    """
    if not settings.email_test_redirect_base:
        return email

    local_part, separator, domain = email.partition("@")
    if not separator:
        return email
    if domain.lower() != "sps.com":
        return email

    redirect_base = settings.email_test_redirect_base.strip()
    if not redirect_base or "@" not in redirect_base:
        return email

    redirect_user, redirect_domain = redirect_base.split("@", 1)
    if not redirect_user or not redirect_domain:
        return email
    return f"{redirect_user}+{local_part}@{redirect_domain}"


class EventListener:
    """Polls the backend email events feed and sends appropriate email notifications."""

    def __init__(
        self,
        ticket_client: Optional[TicketClient] = None,
        email_sender: Optional[EmailSender] = None,
    ) -> None:
        self.ticket_client = ticket_client or TicketClient()
        self.email_sender = email_sender or EmailSender()
        self._running = False
        self._last_event_id: Optional[str] = None
        self._poll_interval: int = settings.imap_poll_interval_seconds

    async def _process_event(self, event: Dict[str, Any]) -> None:
        event_id = event.get("id", "")

        try:
            backend_event = BackendEvent(**event)
        except Exception as e:
            logger.warning("Failed to parse event: %s | data=%s", e, event)
            return

        logger.info(
            "Processing event: type=%s ticket=%s",
            backend_event.event_type,
            backend_event.ticket_id,
        )

        data = backend_event.data or {}
        requester_email = _redirect_for_real_delivery(data.get("requester_email", ""))
        requester_name = data.get("requester_name", "")
        subject = data.get("subject", "Ticket Update")
        # Use human-readable ticket number if available, fall back to UUID
        ticket_ref = data.get("ticket_number") or backend_event.ticket_id

        try:
            # Use ticket_number (SPS-2026-116) for user-facing emails instead of UUID
            ticket_ref = backend_event.ticket_number or backend_event.ticket_id

            if backend_event.event_type == "ticket_created":
                if str(data.get("source", "")).lower() == "email":
                    logger.info(
                        "Skipping duplicate ticket_created ACK in event listener for email-originated ticket %s",
                        ticket_ref,
                    )
                elif requester_email:
                    await self.email_sender.send_ack_email(
                        to_email=requester_email,
                        ticket_id=ticket_ref,
                        subject=subject,
                        requester_name=requester_name,
                    )
                    logger.info("ACK email sent for ticket %s", ticket_ref)

            elif backend_event.event_type == "agent_reply":
                agent_name = data.get("agent_name", "Support Agent")
                reply_content = data.get("content", "")

                if requester_email:
                    await self.email_sender.send_agent_reply_email(
                        to_email=requester_email,
                        ticket_id=ticket_ref,
                        original_subject=subject,
                        agent_name=agent_name,
                        reply_content=reply_content,
                        requester_name=requester_name,
                    )

                    timeline_payload = TimelineEventPayload(
                        event_type="internal_note",
                        content=f"Agent reply notification sent to {requester_email}",
                        is_public=False,
                        channel="system",
                    )
                    try:
                        await self.ticket_client.append_timeline_event(
                            backend_event.ticket_id, timeline_payload
                        )
                    except Exception as e:
                        logger.warning(
                            "Failed to log agent_reply_email event: %s", e
                        )

                    logger.info("Agent reply email sent for ticket %s", ticket_ref)

            elif backend_event.event_type == "status_changed":
                new_status = data.get("new_status", data.get("status", "Updated"))

                if requester_email:
                    await self.email_sender.send_status_change_email(
                        to_email=requester_email,
                        ticket_id=ticket_ref,
                        subject=subject,
                        new_status=new_status,
                        requester_name=requester_name,
                    )
                    logger.info(
                        "Status change email sent for ticket %s -> %s",
                        ticket_ref,
                        new_status,
                    )

            elif backend_event.event_type == "approval_required":
                approver_email = _redirect_for_real_delivery(
                    data.get("approver_email", data.get("requester_email", ""))
                )
                approval_url = data.get(
                    "approval_url",
                    f"{settings.portal_url}/tickets/{backend_event.ticket_id}/approve",
                )

                if approver_email:
                    await self.email_sender.send_approval_request_email(
                        to_email=approver_email,
                        ticket_id=ticket_ref,
                        subject=subject,
                        requester_name=requester_name,
                        approval_url=approval_url,
                    )
                    logger.info(
                        "Approval request email sent for ticket %s to %s",
                        ticket_ref,
                        approver_email,
                    )

            elif backend_event.event_type == "duplicate_detected":
                # Send duplicate notice to the requester informing them their
                # submission was received but is a duplicate of an existing ticket.
                if requester_email:
                    existing_ticket_number = data.get("ticket_number", ticket_ref)
                    existing_ticket_status = data.get("status", "duplicate")
                    existing_ticket_subject = data.get("subject", subject)
                    await self.email_sender.send_duplicate_notice_email(
                        to_email=requester_email,
                        to_name=requester_name,
                        existing_ticket_number=existing_ticket_number,
                        existing_ticket_status=existing_ticket_status,
                        existing_ticket_subject=existing_ticket_subject,
                    )
                    logger.info(
                        "Duplicate notice email sent for ticket %s to %s",
                        ticket_ref,
                        requester_email,
                    )

            else:
                logger.warning("Unknown event type: %s", backend_event.event_type)

            if event_id:
                self._last_event_id = event_id

        except Exception as e:
            logger.error(
                "Failed to send email for event %s: %s",
                backend_event.event_type,
                e,
                exc_info=True,
            )

    async def poll_events(self) -> int:
        """Poll the backend for new email events and process them."""
        try:
            events = await self.ticket_client.fetch_events(self._last_event_id)
        except Exception as e:
            logger.warning("Failed to fetch events: %s", e)
            return 0

        if not events:
            return 0

        logger.info("Fetched %d events from backend", len(events))
        count = 0

        for event in events:
            await self._process_event(event)
            count += 1

        return count

    async def start_listening(self) -> None:
        """Start the continuous event polling loop."""
        self._running = True
        logger.info(
            "Event listener started: polling every %d seconds",
            self._poll_interval,
        )

        while self._running:
            try:
                count = await self.poll_events()
                if count > 0:
                    logger.info("Event cycle complete: %d events processed", count)
            except Exception as e:
                logger.error(
                    "Event polling cycle failed: %s. Will retry.", e, exc_info=True
                )

            await asyncio.sleep(self._poll_interval)

        logger.info("Event listener stopped")

    async def stop(self) -> None:
        """Gracefully stop the event listener."""
        self._running = False
        await self.ticket_client.close()
        logger.info("Event listener shut down")
