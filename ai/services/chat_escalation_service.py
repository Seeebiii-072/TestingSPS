from typing import Any

import httpx

from ai.chat.session import SessionStore, session_store
from ai.config.settings import Settings, get_settings
from ai.schemas.chat import ChatEscalationRequest, ChatEscalationResponse


BACKEND_UNAVAILABLE_MESSAGE = (
    "Ticket could not be created because backend service is unavailable. "
    "Please try again later."
)


class ChatEscalationService:
    def __init__(
        self,
        *,
        settings: Settings | None = None,
        sessions: SessionStore | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._sessions = sessions or session_store

    def create_ticket(
        self,
        request: ChatEscalationRequest,
    ) -> ChatEscalationResponse:
        # This verifies session ownership without clearing or changing its messages.
        self._sessions.get_or_create(request.session_id, request.user_id)
        payload = self._build_payload(request)
        url = f"{self._settings.backend_api_url.rstrip('/')}/tickets"

        try:
            response = httpx.post(
                url,
                json=payload,
                timeout=self._settings.llm_timeout_seconds,
            )
            response.raise_for_status()
            backend_response = response.json()
            if not isinstance(backend_response, dict):
                raise ValueError("Backend returned a non-object JSON response.")
        except (httpx.HTTPError, ValueError) as exc:
            return ChatEscalationResponse(
                success=False,
                message=BACKEND_UNAVAILABLE_MESSAGE,
                error=str(exc),
            )

        ticket_id = self._ticket_id(backend_response)
        return ChatEscalationResponse(
            success=True,
            ticket_id=ticket_id,
            message="Ticket created successfully.",
            backend_response=backend_response,
        )

    @staticmethod
    def _build_payload(request: ChatEscalationRequest) -> dict[str, Any]:
        prefill = request.ticket_prefill
        timeline_message = (
            f"{prefill.timeline_note}\n\n"
            f"Original ticket prefill description: {prefill.description}"
        )
        return {
            "source": "chat",
            "requester": request.requester or request.user_id,
            "subject": prefill.subject,
            "description": prefill.description,
            "category": prefill.category.value,
            "priority": prefill.priority.value,
            "risk_level": prefill.risk_level,
            "team": prefill.team,
            "status": prefill.status,
            "sla": prefill.sla,
            "ai_summary": prefill.ai_summary,
            "timeline": [
                {
                    "type": "chat_escalation_note",
                    "message": timeline_message,
                    "session_id": request.session_id,
                    "created_by": "ai",
                }
            ],
        }

    @staticmethod
    def _ticket_id(backend_response: dict[str, Any]) -> str | None:
        ticket_id = backend_response.get("ticket_id")
        if ticket_id is None:
            ticket_id = backend_response.get("ticket_number")
        return str(ticket_id) if ticket_id is not None else None
