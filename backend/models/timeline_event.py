import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum as SQLEnum, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base

if TYPE_CHECKING:
    from models.ticket import Ticket
    from models.user import User


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TimelineEventType(str, Enum):
    TICKET_CREATED = "ticket_created"
    EMAIL_RECEIVED = "email_received"
    AGENT_REPLY_PORTAL = "agent_reply_portal"
    AGENT_REPLY_EMAIL = "agent_reply_email"
    INTERNAL_NOTE = "internal_note"
    STATUS_CHANGE = "status_change"
    FIELD_UPDATE = "field_update"
    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_RESOLVED = "approval_resolved"
    FILE_UPLOADED = "file_uploaded"
    CHAT_ESCALATION = "chat_escalation"
    AI_CLASSIFIED = "ai_classified"


def enum_values(enum_class: type[Enum]) -> list[str]:
    return [member.value for member in enum_class]


class TimelineEvent(Base):
    __tablename__ = "timeline_events"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticket_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tickets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[TimelineEventType] = mapped_column(
        SQLEnum(
            TimelineEventType,
            name="timeline_event_type",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=enum_values,
        ),
        nullable=False,
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True)
    actor_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    channel: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    ticket: Mapped["Ticket"] = relationship(back_populates="timeline_events")
    actor: Mapped["User | None"] = relationship(back_populates="timeline_events")
