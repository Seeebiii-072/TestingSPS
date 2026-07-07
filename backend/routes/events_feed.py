"""GET /events/email — Polling feed for the email_worker outbound notification system.

The email_worker calls this endpoint every ~10 seconds to discover new events
that require an outbound email to be sent (e.g. ticket created, agent reply,
status change, approval required).

Auth decision: This endpoint requires an X-Internal-Api-Key shared by the
backend and email_worker containers because the feed includes requester
identity and ticket metadata.
"""

import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database import get_db
from models.ticket import RiskLevel, Ticket, TicketStatus
from models.timeline_event import TimelineEvent, TimelineEventType
from models.user import User, UserRole

router = APIRouter(tags=["events"])

# Maximum number of events returned per poll cycle to prevent unbounded
# memory/resource usage. The email_worker polls every ~10 seconds, so at
# most 100 events are processed per cycle. Cursor-based pagination via
# since_event_id ensures no events are skipped across cycles.
DEFAULT_PAGE_LIMIT = 100

EVENT_TYPE_MAP: dict[TimelineEventType, str] = {
    TimelineEventType.TICKET_CREATED: "ticket_created",
    TimelineEventType.AGENT_REPLY_PORTAL: "agent_reply",
    TimelineEventType.AGENT_REPLY_EMAIL: "agent_reply",
    TimelineEventType.STATUS_CHANGE: "status_changed",
    TimelineEventType.APPROVAL_REQUESTED: "approval_required",
    TimelineEventType.DUPLICATE_ATTEMPT: "duplicate_detected",
}

# The event_types we should forward to the email_worker
FORWARDED_EVENT_TYPES = {
    TimelineEventType.TICKET_CREATED,
    TimelineEventType.AGENT_REPLY_PORTAL,
    TimelineEventType.AGENT_REPLY_EMAIL,
    TimelineEventType.STATUS_CHANGE,
    TimelineEventType.APPROVAL_REQUESTED,
    TimelineEventType.DUPLICATE_ATTEMPT,
}

APPROVER_ROLES = {UserRole.SECURITY_ADMIN, UserRole.MANAGER, UserRole.ADMINISTRATOR}


def _internal_api_key() -> str:
    return os.getenv("INTERNAL_API_KEY", "")


def _require_internal_api_key(x_internal_api_key: str | None) -> None:
    expected_key = _internal_api_key()
    if not expected_key or x_internal_api_key != expected_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid internal API key")


def _build_event_data(event: TimelineEvent, ticket: Ticket) -> dict[str, Any]:
    requester_name = (
        ticket.requester.full_name if ticket.requester else ticket.requester_email
    )
    base = {
        "requester_email": ticket.requester_email,
        "requester_name": requester_name,
        "subject": ticket.subject,
        "ticket_number": ticket.ticket_number,
    }

    mapped_type = EVENT_TYPE_MAP.get(event.event_type, "")

    if mapped_type == "agent_reply":
        base["agent_name"] = (event.actor.full_name if event.actor else None) or event.actor_email or "Support Agent"
        base["content"] = event.content or ""

    elif mapped_type == "status_changed":
        try:
            changes = json.loads(event.content) if event.content else {}
            if "status" in changes:
                base["new_status"] = changes["status"].get("to", "Updated")
            else:
                base["new_status"] = "Updated"
        except (json.JSONDecodeError, TypeError):
            base["new_status"] = "Updated"

    elif mapped_type == "approval_required":
        pass  # handled separately below

    return base


def _build_event_output(
    event: TimelineEvent,
    ticket: Ticket,
    approver_email: str = "",
) -> dict[str, Any]:
    data = _build_event_data(event, ticket)
    mapped_type = EVENT_TYPE_MAP.get(event.event_type, "")

    if mapped_type == "approval_required" and approver_email:
        data["approver_email"] = approver_email
        data["approval_url"] = (
            f"http://localhost:5173/tickets/{ticket.id}/approve"
        )

    return {
        "id": str(event.id),
        "event_type": mapped_type,
        "ticket_id": str(event.ticket_id),
        "ticket_number": ticket.ticket_number,
        "data": data,
    }


@router.get("/events/email")
async def email_events_feed(
    x_internal_api_key: Annotated[str | None, Header(alias="X-Internal-Api-Key")] = None,
    db: AsyncSession = Depends(get_db),
    since_event_id: str | None = Query(
        None,
        alias="since_event_id",
        description="Return only events newer than this UUID (sequential by created_at)",
    ),
) -> list[dict[str, Any]]:
    """Return email events that the email_worker needs to send notifications for."""
    _require_internal_api_key(x_internal_api_key)

    query = (
        select(TimelineEvent)
        .options(
            selectinload(TimelineEvent.ticket).selectinload(Ticket.requester),
            selectinload(TimelineEvent.ticket).selectinload(Ticket.timeline_events),
            selectinload(TimelineEvent.actor),
        )
        .where(TimelineEvent.event_type.in_(FORWARDED_EVENT_TYPES))
        .order_by(TimelineEvent.created_at.asc(), TimelineEvent.id.asc())
        .limit(DEFAULT_PAGE_LIMIT)
    )

    if since_event_id:
        try:
            cursor_uuid = uuid.UUID(since_event_id)
            cursor_event = await db.get(TimelineEvent, cursor_uuid)
            if cursor_event:
                query = query.where(
                    TimelineEvent.created_at > cursor_event.created_at
                )
        except (ValueError, AttributeError):
            pass
    else:
        # When no cursor is provided (e.g. email_worker just restarted),
        # only return events from the last 24 hours to prevent re-sending
        # notifications for old events.
        query = query.where(
            TimelineEvent.created_at >= datetime.now(timezone.utc) - timedelta(hours=24)
        )

    result = await db.execute(query)
    events = result.scalars().all()

    approver_emails: dict[uuid.UUID, str] = {}
    for ev in events:
        if ev.event_type == TimelineEventType.APPROVAL_REQUESTED:
            ticket_id = ev.ticket_id
            if ticket_id not in approver_emails:
                approver_result = await db.execute(
                    select(User).where(User.role.in_(APPROVER_ROLES), User.is_active.is_(True))
                )
                approvers = approver_result.scalars().all()
                first_approver = next(iter(approvers), None)
                approver_emails[ticket_id] = (
                    first_approver.email if first_approver else ""
                )

    output = []
    for ev in events:
        ticket = ev.ticket
        if not ticket:
            continue

        # Only forward public replies
        if ev.event_type in (
            TimelineEventType.AGENT_REPLY_PORTAL,
            TimelineEventType.AGENT_REPLY_EMAIL,
        ) and not ev.is_public:
            continue

        mapped_type = EVENT_TYPE_MAP.get(ev.event_type, "")
        if not mapped_type:
            continue

        approver_email = ""
        if mapped_type == "approval_required":
            approver_email = approver_emails.get(ev.ticket_id, "")

        output.append(_build_event_output(ev, ticket, approver_email))

    return output