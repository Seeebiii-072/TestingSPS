"""POST /tickets/{ticket_id}/ai-resolve — Internal endpoint for AI auto-resolve.

Protected by X-Internal-Api-Key (not JWT), following the same pattern as
events_feed.py. The AI Support Agent user is used as the actor for audit
and timeline purposes.
"""

import logging
import os
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.ticket import Ticket, TicketStatus
from models.timeline_event import TimelineEvent, TimelineEventType
from models.user import User
from schemas.ticket import TicketUpdate
from services.ticket_service import update_ticket

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tickets", tags=["tickets"])

AI_AGENT_EMAIL = "ai-agent@sps.com"


class AiResolveRequest(BaseModel):
    """Request payload for AI auto-resolve."""

    answer: str = Field(min_length=1, max_length=100_000)
    sources: list[str] = Field(default_factory=list)


def _internal_api_key() -> str:
    return os.getenv("INTERNAL_API_KEY", "")


def _require_internal_api_key(x_internal_api_key: str | None) -> None:
    expected_key = _internal_api_key()
    if not expected_key or x_internal_api_key != expected_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid internal API key",
        )


@router.post("/{ticket_id}/ai-resolve", status_code=status.HTTP_200_OK)
async def ai_resolve_ticket(
    ticket_id: uuid.UUID,
    payload: AiResolveRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    x_internal_api_key: Annotated[
        str | None, Header(alias="X-Internal-Api-Key")
    ] = None,
) -> dict:
    """AI support agent resolves a ticket with an auto-generated reply.

    This is an internal service-to-service endpoint (protected by
    X-Internal-Api-Key, not JWT/OAuth).

    1. Looks up the AI Support Agent user for audit identity.
    2. Appends an agent-reply timeline event (which triggers outbound email).
    3. Sets ticket status to RESOLVED.

    Rejects (403) if the ticket is currently WAITING_APPROVAL — AI must
    never resolve a ticket pending human approval.
    """
    _require_internal_api_key(x_internal_api_key)

    # Look up the AI Support Agent system user
    result = await db.execute(
        select(User).where(User.email == AI_AGENT_EMAIL)
    )
    ai_agent = result.scalar_one_or_none()
    if not ai_agent:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AI Support Agent user not found in database",
        )

    # Verify the ticket exists
    ticket_result = await db.execute(
        select(Ticket).where(Ticket.id == ticket_id)
    )
    ticket = ticket_result.scalar_one_or_none()
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found",
        )

    # Never resolve a ticket that's pending human approval
    if ticket.status == TicketStatus.WAITING_APPROVAL:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot resolve a ticket that is pending human approval",
        )

    # Only allow resolving OPEN or IN_PROGRESS tickets
    if ticket.status not in (TicketStatus.OPEN, TicketStatus.IN_PROGRESS):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot resolve ticket with status '{ticket.status.value}'",
        )

    # Build the content for the timeline event: answer text + sources
    content_parts = [payload.answer]
    if payload.sources:
        content_parts.append(
            "\n\n**Sources:** " + ", ".join(payload.sources)
        )
    timeline_content = "\n".join(content_parts)

    # Append an agent_reply_portal timeline event (triggers outbound email flow
    # via the existing events_feed mechanism).
    timeline_event = TimelineEvent(
        ticket_id=ticket.id,
        event_type=TimelineEventType.AGENT_REPLY_PORTAL,
        actor_id=ai_agent.id,
        actor_email=ai_agent.email,
        content=timeline_content,
        is_public=True,
        channel="system",
    )
    db.add(timeline_event)

    # Update ticket to RESOLVED — update_ticket allows any AGENT to change
    # status on an OPEN/IN_PROGRESS ticket, so this will succeed.
    update_payload = TicketUpdate(status=TicketStatus.RESOLVED)
    updated_ticket = await update_ticket(
        db, ticket_id, update_payload, ai_agent
    )

    logger.info(
        "AI Support Agent resolved ticket %s (id=%s)",
        updated_ticket.ticket_number,
        ticket_id,
    )

    return {
        "status": "resolved",
        "ticket_id": str(ticket_id),
        "ticket_number": updated_ticket.ticket_number,
    }