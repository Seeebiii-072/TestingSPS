import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base

if TYPE_CHECKING:
    from models.attachment import Attachment
    from models.timeline_event import TimelineEvent
    from models.user import User


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TicketSource(str, Enum):
    EMAIL = "email"
    PORTAL_FORM = "portal_form"
    CHAT = "chat"


class TicketCategory(str, Enum):
    CLOUD = "cloud"
    CYBERSECURITY = "cybersecurity"
    IDENTITY_ACCESS = "identity_access"
    DEVOPS = "devops"
    INTERNSHIP_HR = "internship_hr"
    GENERAL_IT = "general_it"


class TicketPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RiskLevel(str, Enum):
    STANDARD = "standard"
    HIGH = "high"


class TicketTeam(str, Enum):
    IT = "it"
    SECURITY = "security"
    DEVOPS = "devops"
    HR = "hr"
    MANAGEMENT = "management"


class TicketStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    WAITING_APPROVAL = "waiting_approval"
    WAITING_USER = "waiting_user"
    RESOLVED = "resolved"
    CLOSED = "closed"


def enum_values(enum_class: type[Enum]) -> list[str]:
    return [member.value for member in enum_class]


class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticket_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    source: Mapped[TicketSource] = mapped_column(
        SQLEnum(
            TicketSource,
            name="ticket_source",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=enum_values,
        ),
        nullable=False,
    )
    requester_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )
    requester_email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    subject: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[TicketCategory] = mapped_column(
        SQLEnum(
            TicketCategory,
            name="ticket_category",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=enum_values,
        ),
        nullable=False,
    )
    priority: Mapped[TicketPriority] = mapped_column(
        SQLEnum(
            TicketPriority,
            name="ticket_priority",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=enum_values,
        ),
        nullable=False,
        default=TicketPriority.MEDIUM,
    )
    risk_level: Mapped[RiskLevel] = mapped_column(
        SQLEnum(
            RiskLevel,
            name="risk_level",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=enum_values,
        ),
        nullable=False,
    )
    team: Mapped[TicketTeam] = mapped_column(
        SQLEnum(
            TicketTeam,
            name="ticket_team",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=enum_values,
        ),
        nullable=False,
    )
    status: Mapped[TicketStatus] = mapped_column(
        SQLEnum(
            TicketStatus,
            name="ticket_status",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=enum_values,
        ),
        nullable=False,
    )
    assigned_agent_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )
    ai_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    sla_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    requester: Mapped["User | None"] = relationship(
        back_populates="requested_tickets",
        foreign_keys=[requester_id],
    )
    assigned_agent: Mapped["User | None"] = relationship(
        back_populates="assigned_tickets",
        foreign_keys=[assigned_agent_id],
    )
    timeline_events: Mapped[list["TimelineEvent"]] = relationship(
        back_populates="ticket",
        cascade="all, delete-orphan",
        order_by="TimelineEvent.created_at",
    )
    attachments: Mapped[list["Attachment"]] = relationship(
        back_populates="ticket",
        cascade="all, delete-orphan",
        order_by="Attachment.created_at",
    )
