"""HTTP client for backend API communication with retry and error handling."""

from __future__ import annotations

from typing import Any, Dict, Optional

import httpx

from email_worker.config.settings import settings
from email_worker.models.event_models import (
    ClassifyResponse,
    TicketCreatePayload,
    TimelineEventPayload,
)
from email_worker.utils.logger import logger
from email_worker.utils.retry import async_retry


class TicketClient:
    """Async HTTP client for interacting with the backend ticket API."""

    def __init__(self, base_url: Optional[str] = None) -> None:
        self.base_url = (base_url or settings.backend_api_url).rstrip("/")
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(30.0),
            )
        return self._client

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    @async_retry(max_attempts=3, base_delay=1.0)
    async def create_ticket(self, payload: TicketCreatePayload) -> Dict[str, Any]:
        """Create a new ticket via the backend API.

        Args:
            payload: The ticket creation payload.

        Returns:
            The API response as a dictionary.

        Raises:
            httpx.HTTPError: If the API request fails after retries.
        """
        client = await self._get_client()
        logger.info(
            "Creating ticket: subject=%s, from=%s",
            payload.subject,
            payload.requester_email,
        )
        response = await client.post("/tickets", json=payload.model_dump())
        response.raise_for_status()
        data: Dict[str, Any] = response.json()
        logger.info("Ticket created successfully: id=%s", data.get("id"))
        return data

    @async_retry(max_attempts=3, base_delay=1.0)
    async def append_timeline_event(
        self, ticket_id: str, payload: TimelineEventPayload
    ) -> Dict[str, Any]:
        """Append an event to a ticket's timeline.

        Args:
            ticket_id: The ticket ID to append to.
            payload: The timeline event payload.

        Returns:
            The API response as a dictionary.
        """
        client = await self._get_client()
        logger.info(
            "Appending event to ticket %s: event_type=%s",
            ticket_id,
            payload.event_type,
        )
        response = await client.post(
            f"/tickets/{ticket_id}/events",
            json=payload.model_dump(),
        )
        response.raise_for_status()
        data: Dict[str, Any] = response.json()
        logger.info(
            "Timeline event appended to ticket %s", ticket_id
        )
        return data

    @async_retry(max_attempts=3, base_delay=1.0)
    async def classify_email(
        self, subject: str, description: str
    ) -> ClassifyResponse:
        """Classify an email via the AI classification endpoint.

        Args:
            subject: The email subject.
            description: The email body / description.

        Returns:
            A ClassifyResponse with category, priority, and team.
        """
        client = await self._get_client()
        logger.info(
            "Classifying email: subject=%s", subject
        )
        response = await client.post(
            "/ai/classify",
            json={"subject": subject, "description": description},
        )
        response.raise_for_status()
        raw: Dict[str, Any] = response.json()
        return ClassifyResponse(**raw)

    @async_retry(max_attempts=3, base_delay=1.0)
    async def fetch_events(
        self, last_event_id: Optional[str] = None
    ) -> list[Dict[str, Any]]:
        """Fetch email events from the backend events feed.

        Args:
            last_event_id: Optional cursor for pagination.

        Returns:
            A list of event dictionaries.
        """
        client = await self._get_client()
        params: Dict[str, str] = {}
        if last_event_id:
            params["after"] = last_event_id
        response = await client.get("/events/email", params=params)
        response.raise_for_status()
        events: list[Dict[str, Any]] = response.json()
        return events

    async def health_check(self) -> bool:
        """Check if the backend API is reachable.

        Returns:
            True if the backend responds successfully.
        """
        try:
            client = await self._get_client()
            response = await client.get("/health")
            return response.status_code < 500
        except Exception as e:
            logger.warning("Backend health check failed: %s", e)
            return False