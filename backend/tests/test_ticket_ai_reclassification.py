import asyncio
import sys
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import models  # noqa: F401, E402
from database import Base  # noqa: E402
from models.audit_log import AuditLog  # noqa: E402
from models.ticket import RiskLevel, TicketCategory, TicketPriority, TicketSource, TicketStatus, TicketTeam  # noqa: E402
from models.timeline_event import TimelineEventType  # noqa: E402
from models.user import User, UserRole  # noqa: E402
from schemas.ticket import TicketCreate  # noqa: E402
from services import ticket_service  # noqa: E402


def test_ai_reclassified_high_risk_ticket_waits_for_approval(tmp_path, monkeypatch):
    db_path = tmp_path / "ticket-ai-reclassification.db"
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_path.as_posix()}",
        connect_args={"check_same_thread": False},
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async def fake_classifier(subject: str, description: str):
        return {
            "category": "identity_access",
            "priority": "high",
            "risk_level": "high",
            "team": "security",
            "reasoning": "Access request requires approval",
        }

    async def run_case():
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        async with session_factory() as session:
            requester = User(
                email="employee@sps.com",
                full_name="Employee User",
                hashed_password="not-used",
                role=UserRole.EMPLOYEE,
            )
            session.add(requester)
            await session.commit()
            await session.refresh(requester)

            ticket = await ticket_service.create_ticket(
                session,
                TicketCreate(
                    source=TicketSource.PORTAL_FORM,
                    subject="Need access to admin console",
                    description="Please provision admin console permissions",
                    category=TicketCategory.GENERAL_IT,
                    priority=TicketPriority.MEDIUM,
                    requester_email=requester.email,
                ),
                requester,
            )

            approval_audits = await session.execute(
                select(AuditLog).where(
                    AuditLog.ticket_id == ticket.id,
                    AuditLog.action == "ticket.approval_requested",
                )
            )
            return ticket, list(approval_audits.scalars().all())

    monkeypatch.setattr(ticket_service, "_call_ai_classifier", fake_classifier)

    try:
        ticket, approval_audits = asyncio.run(run_case())
    finally:
        asyncio.run(engine.dispose())

    assert ticket.category == TicketCategory.IDENTITY_ACCESS
    assert ticket.priority == TicketPriority.HIGH
    assert ticket.risk_level == RiskLevel.HIGH
    assert ticket.team == TicketTeam.SECURITY
    assert ticket.status == TicketStatus.WAITING_APPROVAL
    assert TimelineEventType.APPROVAL_REQUESTED in {event.event_type for event in ticket.timeline_events}
    assert len(approval_audits) == 1
