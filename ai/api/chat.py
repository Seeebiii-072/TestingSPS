from fastapi import APIRouter, HTTPException, status

from ai.chat.session import SessionOwnershipError
from ai.llm.router import LLMGenerationError
from ai.schemas.chat import (
    ChatEscalationRequest,
    ChatEscalationResponse,
    ChatRequest,
    ChatResponse,
)
from ai.services.chat_escalation_service import ChatEscalationService
from ai.services.chat_service import ChatService


router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    try:
        return ChatService().respond(request)
    except SessionOwnershipError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    except LLMGenerationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc


@router.post(
    "/escalate",
    response_model=ChatEscalationResponse,
    response_model_exclude_none=True,
)
def escalate_chat(request: ChatEscalationRequest) -> ChatEscalationResponse:
    try:
        return ChatEscalationService().create_ticket(request)
    except SessionOwnershipError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
