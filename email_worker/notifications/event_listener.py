"""Backend event listener that polls for email events and sends outbound notifications."""

from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional, Set

from email_worker.api_client.ticket_client import TicketClient
from email_worker.config.settings import settings
from email_worker.models.event_models import BackendEvent, TimelineEventPayload
from email_worker.smtp.sender import EmailSender
from email_worker.utils.logger import logger


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
        self._processed_event_ids: Set[str] = set()
        self._poll_interval: int = 10  # Poll every 10 seconds

    async def _process_event(self, event: Dict[str, Any]) -> None:
        """Process a single backend event and send the appropriate email.

        Args:
            event: The event dictionary from the backend.
        """
        event_id = event.get("id", "")
        if event_id and event_id in self._processed_event_ids:
            return

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
        requester_email = data.get("requester_email", "")
        requester_name = data.get("requester_name", "")
        subject = data.get("subject", "Ticket Update")

        try:
            if backend_event.event_type == "ticket_created":
                if requester_email:
                    await self.email_sender.send_ack_email(
                        to_email=requester_email,
                        ticket_id=backend_event.ticket_id,
                        subject=subject,
                        requester_name=requester_name,
                    )
                    logger.info(
                        "ACK email sent for ticket %s", backend_event.ticket_id
                    )

            elif backend_event.event_type == "agent_reply":
                agent_name = data.get("agent_name", "Support Agent")
                reply_content = data.get("content", "")

                if requester_email:
                    await self.email_sender.send_agent_reply_email(
                        to_email=requester_email,
                        ticket_id=backend_event.ticket_id,
                        original_subject=subject,
                        agent_name=agent_name,
                        reply_content=reply_content,
                        requester_name=requester_name,
                    )

                    # Log the sent email event to the timeline
                    timeline_payload = TimelineEventPayload(
                        event_type="agent_reply_email",
                        content=f"Agent reply notification sent to {requester_email}",
                    )
                    try:
                        await self.ticket_client.append_timeline_event(
                            backend_event.ticket_id, timeline_payload
                        )
                    except Exception as e:
                        logger.warning(
                            "Failed to log agent_reply_email event: %s", e
                        )

                    logger.info(
                        "Agent reply email sent for ticket %s",
                        backend_event.ticket_id,
                    )

            elif backend_event.event_type == "status_changed":
                new_status = data.get("new_status", data.get("status", "Updated"))

                if requester_email:
                    await self.email_sender.send_status_change_email(
                        to_email=requester_email,
                        ticket_id=backend_event.ticket_id,
                        subject=subject,
                        new_status=new_status,
                        requester_name=requester_name,
                    )
                    logger.info(
                        "Status change email sent for ticket %s -> %s",
                        backend_event.ticket_id,
                        new_status,
                    )

            elif backend_event.event_type == "approval_required":
                approver_email = data.get(
                    "approver_email", data.get("requester_email", "")
                )
                approval_url = data.get(
                    "approval_url",
                    f"{settings.portal_url}/tickets/{backend_event.ticket_id}/approve",
                )

                if approver_email:
                    await self.email_sender.send_approval_request_email(
                        to_email=approver_email,
                        ticket_id=backend_event.ticket_id,
                        subject=subject,
                        requester_name=requester_name,
                        approval_url=approval_url,
                    )
                    logger.info(
                        "Approval request email sent for ticket %s to %s",
                        backend_event.ticket_id,
                        approver_email,
                    )

            else:
                logger.warning(
                    "Unknown event type: %s", backend_event.event_type
                )

        except Exception as e:
            logger.error(
                "Failed to send email for event %s: %s",
                backend_event.event_type,
                e,
                exc_info=True,
            )

        # Mark as processed
        if event_id:
            self._processed_event_ids.add(event_id)
            self._last_event_id = event_id

    async def poll_events(self) -> int:
        """Poll the backend for new email events and process them.

        Returns:
            The number of events processed.
        """
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