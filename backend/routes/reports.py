from collections import Counter
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from middleware.auth_middleware import require_roles
from models.ticket import RiskLevel, Ticket, TicketCategory, TicketSource, TicketStatus
from models.user import User, UserRole
from schemas.ticket import ReportSummary

router = APIRouter(prefix="/reports", tags=["reports"])

REPORT_ROLES = {UserRole.MANAGER, UserRole.ADMINISTRATOR}


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


@router.get("/summary", response_model=ReportSummary)
async def summary_report(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(REPORT_ROLES))],
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> ReportSummary:
    statement = select(Ticket)
    if date_from:
        statement = statement.where(Ticket.created_at >= date_from)
    if date_to:
        statement = statement.where(Ticket.created_at <= date_to)

    result = await db.execute(statement)
    tickets = list(result.scalars().all())

    by_source = Counter(ticket.source.value for ticket in tickets)
    by_status = Counter(ticket.status.value for ticket in tickets)
    by_category = Counter(ticket.category.value for ticket in tickets)
    now = datetime.now(timezone.utc)
    resolved_tickets = [ticket for ticket in tickets if ticket.status in {TicketStatus.RESOLVED, TicketStatus.CLOSED}]
    resolution_hours = [
        (_as_utc(ticket.updated_at) - _as_utc(ticket.created_at)).total_seconds() / 3600
        for ticket in resolved_tickets
        if ticket.updated_at and ticket.created_at
    ]

    return ReportSummary(
        total_tickets=len(tickets),
        by_source={source.value: by_source.get(source.value, 0) for source in TicketSource},
        by_status={status.value: by_status.get(status.value, 0) for status in TicketStatus},
        by_category={category.value: by_category.get(category.value, 0) for category in TicketCategory},
        high_risk_total=sum(1 for ticket in tickets if ticket.risk_level == RiskLevel.HIGH),
        high_risk_pending_approval=sum(
            1 for ticket in tickets if ticket.risk_level == RiskLevel.HIGH and ticket.status == TicketStatus.WAITING_APPROVAL
        ),
        sla_breached=sum(
            1
            for ticket in tickets
            if ticket.sla_due_at and _as_utc(ticket.sla_due_at) < now and ticket.status not in {TicketStatus.RESOLVED, TicketStatus.CLOSED}
        ),
        avg_resolution_hours=round(sum(resolution_hours) / len(resolution_hours), 2) if resolution_hours else 0.0,
    )
