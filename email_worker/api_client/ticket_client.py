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
    """Async HTTP client for interacting with the backend ticket API
    and the AI classification service.

    Uses two separate HTTP clients:
    - backend_client: pointed at backend_api_url for tickets, events, etc.
    - ai_client: pointed at ai_service_url for email classification.
    """

    def __init__(
        self,
        backend_url: Optional[str] = None,
        ai_url: Optional[str] = None,
    ) -> None:
        self.backend_url = (backend_url or settings.backend_api_url).rstrip("/")
        self.ai_url = (ai_url or settings.ai_service_url).rstrip("/")
        self._backend_client: Optional[httpx.AsyncClient] = None
        self._ai_client: Optional[httpx.AsyncClient] = None

    async def _get_backend_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client for the backend API."""
        if self._backend_client is None or self._backend_client.is_closed:
            self._backend_client = httpx.AsyncClient(
                base_url=self.backend_url,
                timeout=httpx.Timeout(30.0),
            )
        return self._backend_client

    async def _get_ai_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client for the AI service."""
        if self._ai_client is None or self._ai_client.is_closed:
            self._ai_client = httpx.AsyncClient(
                base_url=self.ai_url,
                timeout=httpx.Timeout(30.0),
            )
        return self._ai_client

    async def close(self) -> None:
        """Close all underlying HTTP clients."""
        if self._backend_client and not self._backend_client.is_closed:
            await self._backend_client.aclose()
        if self._ai_client and not self._ai_client.is_closed:
            await self._ai_client.aclose()

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
        client = await self._get_backend_client()
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
        client = await self._get_backend_client()
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
        """Classify an email via the AI classification service.

        Calls POST /api/classify on the AI service (ai_service:8001),
        NOT on the backend API.

        Args:
            subject: The email subject.
            description: The email body / description.

        Returns:
            A ClassifyResponse with category, priority, and team.
        """
        client = await self._get_ai_client()
        logger.info(
            "Classifying email (via AI service): subject=%s", subject
        )
        response = await client.post(
            "/api/classify",
            json={"subject": subject, "description": description},
        )
        response.raise_for_status()
        raw: Dict[str, Any] = response.json()
        return ClassifyResponse(**raw)

    @async_retry(max_attempts=3, base_delay=1.0)
    async def fetch_events(
        self, last_event_id: Optional[str] = None
    ) -> list:
        """Fetch email events from the backend events feed.

        Args:
            last_event_id: Optional cursor for pagination.

        Returns:
            A list of event dictionaries.
        """
        client = await self._get_backend_client()
        params: Dict[str, str] = {}
        if last_event_id:
            params["since_event_id"] = last_event_id
        headers = {}
        if settings.internal_api_key:
            headers["X-Internal-Api-Key"] = settings.internal_api_key
        response = await client.get("/events/email", params=params, headers=headers)
        response.raise_for_status()
        events: list = response.json()
        return events

    @async_retry(max_attempts=2, base_delay=0.5)
    async def request_ticket_reply(
        self, subject: str, description: str, category: str
    ) -> Dict[str, Any]:
        """Call the AI service's /api/ticket-reply endpoint.

        Args:
            subject: The ticket subject.
            description: The ticket body / description.
            category: The ticket category.

        Returns:
            The API response dict with keys: answer, sources, confident, escalate.
        """
        client = await self._get_ai_client()
        logger.info(
            "Requesting AI ticket reply for subject=%s", subject[:60]
        )
        response = await client.post(
            "/api/ticket-reply",
            json={
                "subject": subject,
                "description": description,
                "category": category,
            },
        )
        response.raise_for_status()
        return response.json()

    @async_retry(max_attempts=2, base_delay=0.5)
    async def resolve_ticket_with_ai(
        self, ticket_id: str, answer: str, sources: list[str]
    ) -> Dict[str, Any]:
        """Call the backend's POST /tickets/{ticket_id}/ai-resolve endpoint.

        Args:
            ticket_id: The ticket ID (UUID) to resolve.
            answer: The AI-generated answer text.
            sources: List of KB source labels.

        Returns:
            The API response dict.
        """
        client = await self._get_backend_client()
        headers = {}
        if settings.internal_api_key:
            headers["X-Internal-Api-Key"] = settings.internal_api_key
        logger.info(
            "Resolving ticket %s with AI reply (len=%d chars)",
            ticket_id,
            len(answer),
        )
        response = await client.post(
            f"/tickets/{ticket_id}/ai-resolve",
            json={"answer": answer, "sources": sources},
            headers=headers,
        )
        response.raise_for_status()
        return response.json()

    async def health_check(self) -> bool:
        """Check if the backend API is reachable.

        Returns:
            True if the backend responds successfully.
        """
        try:
            client = await self._get_backend_client()
            response = await client.get("/health")
            return response.status_code < 500
        except Exception as e:
            logger.warning("Backend health check failed: %s", e)
            return False
