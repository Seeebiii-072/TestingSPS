import json
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models.ticket import RiskLevel, Ticket, TicketCategory, TicketStatus, TicketTeam
from models.timeline_event import TimelineEvent, TimelineEventType
from models.user import ROLE_LEVELS, User, UserRole
from schemas.ticket import ApprovalRequest, TicketCreate, TicketUpdate, TimelineEventCreate
from services.audit_service import write_audit_log
from services.sla_service import compute_sla_due_at


SELF_SERVICE_ROLES = {UserRole.INTERN, UserRole.EMPLOYEE}
STAFF_ROLES = {UserRole.AGENT, UserRole.SECURITY_ADMIN, UserRole.MANAGER, UserRole.ADMINISTRATOR}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def user_can_view_all_tickets(user: User) -> bool:
    return user.role in STAFF_ROLES


def user_can_view_ticket(user: User, ticket: Ticket) -> bool:
    return user_can_view_all_tickets(user) or ticket.requester_id == user.id


def _default_risk_level(category: TicketCategory) -> RiskLevel:
    return RiskLevel.HIGH if category == TicketCategory.IDENTITY_ACCESS else RiskLevel.STANDARD


def _default_team(category: TicketCategory) -> TicketTeam:
    return {
        TicketCategory.CLOUD: TicketTeam.IT,
        TicketCategory.CYBERSECURITY: TicketTeam.SECURITY,
        TicketCategory.IDENTITY_ACCESS: TicketTeam.SECURITY,
        TicketCategory.DEVOPS: TicketTeam.DEVOPS,
        TicketCategory.INTERNSHIP_HR: TicketTeam.HR,
        TicketCategory.GENERAL_IT: TicketTeam.IT,
    }[category]


def _json_safe(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return value


async def generate_ticket_number(db: AsyncSession, year: int) -> str:
    # Locks matching ticket-number rows in PostgreSQL, then a unique retry handles the empty-year race.
    prefix = f"SPS-{year}-"
    result = await db.execute(select(Ticket.ticket_number).where(Ticket.ticket_number.startswith(prefix)).with_for_update())
    highest = 0
    for ticket_number in result.scalars():
        suffix = ticket_number.removeprefix(prefix)
        if suffix.isdigit():
            highest = max(highest, int(suffix))
    return f"{prefix}{highest + 1:03d}"


async def get_ticket_by_id(db: AsyncSession, ticket_id: uuid.UUID) -> Ticket | None:
    result = await db.execute(
        select(Ticket)
        .options(selectinload(Ticket.timeline_events), selectinload(Ticket.attachments))
        .where(Ticket.id == ticket_id)
    )
    return result.scalar_one_or_none()


async def create_ticket(
    db: AsyncSession,
    payload: TicketCreate,
    actor: User | None,
    *,
    ip_address: str | None = None,
) -> Ticket:
    if actor and actor.role in SELF_SERVICE_ROLES and payload.requester_email.lower() != actor.email.lower():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Self-service users can only create tickets for their own email address",
        )

    created_at = utc_now()
    risk_level = _default_risk_level(payload.category)
    ticket_status = TicketStatus.WAITING_APPROVAL if risk_level == RiskLevel.HIGH else TicketStatus.OPEN
    requester_id = actor.id if actor and payload.requester_email.lower() == actor.email.lower() else None

    for attempt in range(5):
        ticket_number = await generate_ticket_number(db, created_at.year)
        ticket = Ticket(
            ticket_number=ticket_number,
            source=payload.source,
            requester_id=requester_id,
            requester_email=payload.requester_email,
            subject=payload.subject,
            description=payload.description,
            category=payload.category,
            priority=payload.priority,
            risk_level=risk_level,
            team=_default_team(payload.category),
            status=ticket_status,
            ai_summary=payload.ai_summary,
            sla_due_at=compute_sla_due_at(created_at, payload.priority),
            created_at=created_at,
            updated_at=created_at,
        )
        db.add(ticket)
        try:
            await db.flush()
        except IntegrityError:
            await db.rollback()
            if attempt == 4:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Could not allocate a unique ticket number",
                ) from None
            continue

        db.add(
            TimelineEvent(
                ticket_id=ticket.id,
                event_type=TimelineEventType.TICKET_CREATED,
                actor_id=actor.id if actor else None,
                actor_email=actor.email if actor else payload.requester_email,
                content=f"Ticket {ticket.ticket_number} created",
                is_public=True,
                channel=payload.source.value,
                created_at=created_at,
            )
        )
        await write_audit_log(
            db,
            ticket_id=ticket.id,
            actor_id=actor.id if actor else None,
            action="ticket.created",
            channel=payload.source.value,
            details={"ticket_number": ticket.ticket_number, "risk_level": risk_level.value},
            ip_address=ip_address,
        )
        await db.commit()
        created_ticket = await get_ticket_by_id(db, ticket.id)
        if created_ticket:
            return created_ticket

    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Ticket creation failed")


async def list_tickets(
    db: AsyncSession,
    current_user: User,
    *,
    status_filter: TicketStatus | None = None,
    category: TicketCategory | None = None,
    team: TicketTeam | None = None,
    source: Any | None = None,
    assigned_to_me: bool = False,
) -> list[Ticket]:
    statement = select(Ticket)

    if not user_can_view_all_tickets(current_user):
        statement = statement.where(Ticket.requester_id == current_user.id)
    elif assigned_to_me:
        statement = statement.where(Ticket.assigned_agent_id == current_user.id)

    if status_filter:
        statement = statement.where(Ticket.status == status_filter)
    if category:
        statement = statement.where(Ticket.category == category)
    if team:
        statement = statement.where(Ticket.team == team)
    if source:
        statement = statement.where(Ticket.source == source)

    statement = statement.order_by(Ticket.created_at.desc())
    result = await db.execute(statement)
    return list(result.scalars().all())


async def update_ticket(
    db: AsyncSession,
    ticket_id: uuid.UUID,
    payload: TicketUpdate,
    actor: User,
    *,
    ip_address: str | None = None,
) -> Ticket:
    ticket = await get_ticket_by_id(db, ticket_id)
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")

    changes: dict[str, dict[str, Any]] = {}
    update_data = payload.model_dump(exclude_unset=True)

    if "assigned_agent_id" in update_data and update_data["assigned_agent_id"] is not None:
        assigned_agent = await db.get(User, update_data["assigned_agent_id"])
        if not assigned_agent or ROLE_LEVELS[assigned_agent.role] < ROLE_LEVELS[UserRole.AGENT]:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Assigned user must be an agent or above")

    for field_name, new_value in update_data.items():
        old_value = getattr(ticket, field_name)
        if old_value != new_value:
            changes[field_name] = {"from": _json_safe(old_value), "to": _json_safe(new_value)}
            setattr(ticket, field_name, new_value)

    if not changes:
        return ticket

    ticket.updated_at = utc_now()
    event_type = TimelineEventType.STATUS_CHANGE if "status" in changes else TimelineEventType.FIELD_UPDATE
    db.add(
        TimelineEvent(
            ticket_id=ticket.id,
            event_type=event_type,
            actor_id=actor.id,
            actor_email=actor.email,
            content=json.dumps(changes),
            is_public=False,
            channel="system",
        )
    )
    await write_audit_log(
        db,
        ticket_id=ticket.id,
        actor_id=actor.id,
        action="ticket.updated",
        channel="system",
        details={"changes": changes},
        ip_address=ip_address,
    )
    await db.commit()
    updated_ticket = await get_ticket_by_id(db, ticket.id)
    if not updated_ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    return updated_ticket


async def add_timeline_event(
    db: AsyncSession,
    ticket_id: uuid.UUID,
    payload: TimelineEventCreate,
    actor: User,
) -> TimelineEvent:
    ticket = await get_ticket_by_id(db, ticket_id)
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")

    event = TimelineEvent(
        ticket_id=ticket_id,
        event_type=payload.event_type,
        actor_id=actor.id,
        actor_email=actor.email,
        content=payload.content,
        is_public=payload.is_public,
        channel=payload.channel,
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)
    return event


async def resolve_approval(
    db: AsyncSession,
    ticket_id: uuid.UUID,
    payload: ApprovalRequest,
    actor: User,
    *,
    ip_address: str | None = None,
) -> Ticket:
    ticket = await get_ticket_by_id(db, ticket_id)
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")

    # Approval decisions are terminal for rejects and move approved tickets into the agent queue.
    ticket.status = TicketStatus.IN_PROGRESS if payload.decision == "approved" else TicketStatus.CLOSED
    ticket.updated_at = utc_now()
    details = {"decision": payload.decision, "reason": payload.reason}
    db.add(
        TimelineEvent(
            ticket_id=ticket.id,
            event_type=TimelineEventType.APPROVAL_RESOLVED,
            actor_id=actor.id,
            actor_email=actor.email,
            content=json.dumps(details),
            is_public=True,
            channel="system",
        )
    )
    await write_audit_log(
        db,
        ticket_id=ticket.id,
        actor_id=actor.id,
        action=f"ticket.approval.{payload.decision}",
        channel="system",
        details=details,
        ip_address=ip_address,
    )
    await db.commit()
    updated_ticket = await get_ticket_by_id(db, ticket.id)
    if not updated_ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    return updated_ticket
