import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum as SQLEnum, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base

if TYPE_CHECKING:
    from models.attachment import Attachment
    from models.audit_log import AuditLog
    from models.ticket import Ticket
    from models.timeline_event import TimelineEvent


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class UserRole(str, Enum):
    INTERN = "intern"
    EMPLOYEE = "employee"
    AGENT = "agent"
    SECURITY_ADMIN = "security_admin"
    MANAGER = "manager"
    ADMINISTRATOR = "administrator"


def enum_values(enum_class: type[Enum]) -> list[str]:
    return [member.value for member in enum_class]


ROLE_LEVELS: dict[UserRole, int] = {
    UserRole.INTERN: 1,
    UserRole.EMPLOYEE: 2,
    UserRole.AGENT: 3,
    UserRole.SECURITY_ADMIN: 4,
    UserRole.MANAGER: 5,
    UserRole.ADMINISTRATOR: 6,
}


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        SQLEnum(
            UserRole,
            name="user_role",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=enum_values,
        ),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    requested_tickets: Mapped[list["Ticket"]] = relationship(
        back_populates="requester",
        foreign_keys="Ticket.requester_id",
    )
    assigned_tickets: Mapped[list["Ticket"]] = relationship(
        back_populates="assigned_agent",
        foreign_keys="Ticket.assigned_agent_id",
    )
    timeline_events: Mapped[list["TimelineEvent"]] = relationship(back_populates="actor")
    attachments: Mapped[list["Attachment"]] = relationship(back_populates="uploader")
    audit_logs: Mapped[list["AuditLog"]] = relationship(back_populates="actor")
