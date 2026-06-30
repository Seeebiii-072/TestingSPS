import json
import logging
import os
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

import httpx
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models.ticket import RiskLevel, Ticket, TicketCategory, TicketPriority, TicketSource, TicketStatus, TicketTeam
from models.timeline_event import TimelineEvent, TimelineEventType
from models.user import ROLE_LEVELS, User, UserRole
from schemas.ticket import ApprovalRequest, TicketCreate, TicketUpdate, TimelineEventCreate
from services.audit_service import write_audit_log
from services.notification_service import create_notifications_for_new_ticket
from services.sla_service import compute_sla_due_at


logger = logging.getLogger(__name__)

AI_SERVICE_URL = os.getenv("AI_SERVICE_URL", "http://ai_service:8001")

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


async def _add_approval_request(
    db: AsyncSession,
    ticket: Ticket,
    *,
    actor: User | None,
    actor_email: str,
    channel: str,
    ip_address: str | None,
    created_at: datetime | None = None,
) -> None:
    db.add(
        TimelineEvent(
            ticket_id=ticket.id,
            event_type=TimelineEventType.APPROVAL_REQUESTED,
            actor_id=actor.id if actor else None,
            actor_email=actor.email if actor else actor_email,
            content=f"High-risk ticket {ticket.ticket_number} requires approval",
            is_public=False,
            channel="system",
            created_at=created_at or utc_now(),
        )
    )
    await write_audit_log(
        db,
        ticket_id=ticket.id,
        actor_id=actor.id if actor else None,
        action="ticket.approval_requested",
        channel=channel,
        details={"ticket_number": ticket.ticket_number, "risk_level": RiskLevel.HIGH.value},
        ip_address=ip_address,
    )


async def _call_ai_classifier(subject: str, description: str) -> dict[str, Any] | None:
    """Call the AI classifier service and return the classification result.

    Returns a dict with keys (category, priority, risk_level, team, reasoning)
    or None on any failure (timeout, connection error, HTTP error).
    """
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                f"{AI_SERVICE_URL}/api/classify",
                json={"subject": subject, "description": description},
            )
            response.raise_for_status()
            result = response.json()
            logger.info("AI classification result: %s", result)
            return result
    except httpx.TimeoutException:
        logger.warning("AI classifier timed out after 15s for subject=%s", subject[:60])
    except httpx.ConnectError:
        logger.warning("AI classifier unreachable at %s", AI_SERVICE_URL)
    except httpx.HTTPStatusError as exc:
        logger.warning("AI classifier returned HTTP %s for subject=%s", exc.response.status_code, subject[:60])
    except Exception:
        logger.exception("Unexpected error calling AI classifier for subject=%s", subject[:60])
    return None


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
        .execution_options(populate_existing=True)
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
    team = _default_team(payload.category)
    
    sla_due_at = compute_sla_due_at(created_at, payload.priority)

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
            team=team,
            status=ticket_status,
            ai_summary=payload.ai_summary,
            sla_due_at=sla_due_at,
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

        # If the ticket is high-risk, create an approval_required event so the
        # email_worker can notify approvers.
        if risk_level == RiskLevel.HIGH:
            await _add_approval_request(
                db,
                ticket,
                actor=actor,
                actor_email=payload.requester_email,
                channel=payload.source.value,
                ip_address=ip_address,
                created_at=created_at,
            )

        # Create notifications for all staff users
        await create_notifications_for_new_ticket(db, ticket, payload.requester_email)

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
            # Auto-classify portal_form and chat tickets via the AI service
            if payload.source in (TicketSource.PORTAL_FORM, TicketSource.CHAT):
                classification = await _call_ai_classifier(payload.subject, payload.description or "")
                if classification:
                    changes: dict[str, dict[str, Any]] = {}
                    for field_name in ("category", "priority", "risk_level", "team"):
                        ai_value = classification.get(field_name)
                        if ai_value is not None:
                            old_value = getattr(created_ticket, field_name)
                            new_value_str = str(ai_value).lower()
                            # Convert string to the appropriate enum
                            if field_name == "category":
                                try:
                                    new_value = TicketCategory(new_value_str)
                                except ValueError:
                                    continue
                            elif field_name == "priority":
                                try:
                                    new_value = TicketPriority(new_value_str)
                                except ValueError:
                                    continue
                            elif field_name == "risk_level":
                                try:
                                    new_value = RiskLevel(new_value_str)
                                except ValueError:
                                    continue
                            elif field_name == "team":
                                try:
                                    new_value = TicketTeam(new_value_str)
                                except ValueError:
                                    continue
                            if old_value != new_value:
                                changes[field_name] = {"from": _json_safe(old_value), "to": _json_safe(new_value)}
                                setattr(created_ticket, field_name, new_value)

                    if changes:
                        created_ticket.updated_at = utc_now()
                        if (
                            created_ticket.risk_level == RiskLevel.HIGH
                            and created_ticket.status
                            not in {TicketStatus.WAITING_APPROVAL, TicketStatus.RESOLVED, TicketStatus.CLOSED}
                        ):
                            old_status = created_ticket.status
                            created_ticket.status = TicketStatus.WAITING_APPROVAL
                            changes["status"] = {
                                "from": _json_safe(old_status),
                                "to": _json_safe(created_ticket.status),
                            }
                            await _add_approval_request(
                                db,
                                created_ticket,
                                actor=actor,
                                actor_email=payload.requester_email,
                                channel=payload.source.value,
                                ip_address=ip_address,
                            )
                        db.add(
                            TimelineEvent(
                                ticket_id=created_ticket.id,
                                event_type=TimelineEventType.FIELD_UPDATE,
                                actor_id=None,
                                actor_email="system",
                                content="Auto-classified by AI",
                                is_public=False,
                                channel="system",
                            )
                        )
                        await write_audit_log(
                            db,
                            ticket_id=created_ticket.id,
                            actor_id=None,
                            action="ticket.ai_classified",
                            channel=payload.source.value,
                            details={"changes": changes, "reasoning": classification.get("reasoning")},
                            ip_address=ip_address,
                        )
                        await db.commit()
                        # Re-fetch to get the updated ticket with timeline
                        created_ticket = await get_ticket_by_id(db, ticket.id)

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

    # High-risk tickets require explicit approval via /approve before any status changes.
    if ticket.status == TicketStatus.WAITING_APPROVAL and actor.role not in {
        UserRole.SECURITY_ADMIN,
        UserRole.MANAGER,
    }:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This ticket is pending approval. Only security_admin or manager can approve it.",
        )

    changes: dict[str, dict[str, Any]] = {}
    update_data = payload.model_dump(exclude_unset=True)

    if "assigned_agent_id" in update_data and update_data["assigned_agent_id"] is not None:
        assigned_agent = await db.get(User, update_data["assigned_agent_id"])
        if not assigned_agent or ROLE_LEVELS[assigned_agent.role] < ROLE_LEVELS[UserRole.AGENT]:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Assigned user must be an agent or above")

    old_sla_due_at = ticket.sla_due_at
    for field_name, new_value in update_data.items():
        old_value = getattr(ticket, field_name)
        if old_value != new_value:
            changes[field_name] = {"from": _json_safe(old_value), "to": _json_safe(new_value)}
            setattr(ticket, field_name, new_value)

    if not changes:
        return ticket

    ticket.updated_at = utc_now()
    if "priority" in changes:
        ticket.sla_due_at = compute_sla_due_at(ticket.updated_at, ticket.priority)
        if old_sla_due_at != ticket.sla_due_at:
            changes["sla_due_at"] = {"from": _json_safe(old_sla_due_at), "to": _json_safe(ticket.sla_due_at)}

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
    actor: User | None,
    *,
    ip_address: str | None = None,
) -> TimelineEvent:
    ticket = await get_ticket_by_id(db, ticket_id)
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")

    if actor and not user_can_view_ticket(actor, ticket):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    if not actor and payload.channel not in {"email", "chat"}:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required for this event channel")

    event = TimelineEvent(
        ticket_id=ticket_id,
        event_type=payload.event_type,
        actor_id=actor.id if actor else None,
        actor_email=actor.email if actor else None,
        content=payload.content,
        is_public=payload.is_public,
        channel=payload.channel,
    )
    db.add(event)
    await write_audit_log(
        db,
        ticket_id=ticket_id,
        actor_id=actor.id if actor else None,
        action="ticket.event_added",
        channel=payload.channel,
        details={"event_type": payload.event_type.value, "is_public": payload.is_public},
        ip_address=ip_address,
    )
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

    if ticket.status != TicketStatus.WAITING_APPROVAL:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ticket {ticket.ticket_number} is not pending approval",
        )

    if actor.role not in {UserRole.SECURITY_ADMIN, UserRole.MANAGER}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only security_admin or manager can approve/reject tickets",
        )

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


async def get_ticket_by_number_and_email(db: AsyncSession, ticket_number: str, email: str) -> Ticket | None:
    """
    Retrieve a ticket by ticket_number and verify email matches requester_email.
    Used for guest/public access without authentication.
    
    Returns the ticket if:
    - Ticket exists with the given ticket_number
    - Email (normalized) matches the ticket's requester_email (normalized)
    
    Returns None if ticket doesn't exist or email doesn't match.
    """
    result = await db.execute(
        select(Ticket)
        .options(selectinload(Ticket.timeline_events), selectinload(Ticket.attachments))
        .where(Ticket.ticket_number == ticket_number)
    )
    ticket = result.scalar_one_or_none()
    
    if not ticket:
        return None
    
    # Normalize both emails for comparison
    if ticket.requester_email.lower() != email.lower():
        return None
    
    return ticket
