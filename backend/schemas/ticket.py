import html
import re
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from models.ticket import RiskLevel, TicketCategory, TicketPriority, TicketSource, TicketStatus, TicketTeam
from models.timeline_event import TimelineEventType


def strip_html(value: str) -> str:
    """Remove HTML tags from user input to prevent XSS."""
    return re.sub(r"<[^>]*>", "", html.unescape(value))


def sanitize_string(value: str) -> str:
    """Strip, remove HTML, and limit to safe characters."""
    cleaned = strip_html(value.strip())
    # Remove null bytes and control characters except newlines/tabs
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", cleaned)
    return cleaned


class TicketCreate(BaseModel):
    source: TicketSource
    subject: str = Field(min_length=1, max_length=500)
    description: str | None = Field(None, max_length=5000)
    category: TicketCategory
    priority: TicketPriority = TicketPriority.MEDIUM
    risk_level: RiskLevel | None = None
    requester_email: EmailStr
    ai_summary: str | None = Field(None, max_length=2000)

    @field_validator("requester_email", mode="before")
    @classmethod
    def normalize_requester_email(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("subject")
    @classmethod
    def sanitize_subject(cls, value: str) -> str:
        return sanitize_string(value)

    @field_validator("description", mode="before")
    @classmethod
    def sanitize_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return sanitize_string(value)

    @field_validator("ai_summary", mode="before")
    @classmethod
    def sanitize_ai_summary(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return sanitize_string(value)


class TicketUpdate(BaseModel):
    status: TicketStatus | None = None
    category: TicketCategory | None = None
    priority: TicketPriority | None = None
    risk_level: RiskLevel | None = None
    team: TicketTeam | None = None
    assigned_agent_id: uuid.UUID | None = None
    ai_summary: str | None = Field(None, max_length=2000)

    @field_validator("ai_summary", mode="before")
    @classmethod
    def sanitize_ai_summary(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return sanitize_string(value)


class TimelineEventCreate(BaseModel):
    event_type: TimelineEventType
    content: str = Field(min_length=1, max_length=50000)
    is_public: bool = True
    channel: str = Field(min_length=1, max_length=20, default="email")

    @field_validator("content")
    @classmethod
    def sanitize_content(cls, value: str) -> str:
        return sanitize_string(value)

    @field_validator("channel")
    @classmethod
    def normalize_channel(cls, value: str) -> str:
        return value.strip().lower()


class TimelineEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ticket_id: uuid.UUID
    event_type: TimelineEventType
    actor_id: uuid.UUID | None
    actor_email: str | None
    content: str | None
    is_public: bool
    channel: str | None
    created_at: datetime


class AttachmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ticket_id: uuid.UUID
    uploaded_by: uuid.UUID | None
    filename: str
    file_path: str
    file_size: int
    mime_type: str
    created_at: datetime


class TicketRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ticket_number: str
    source: TicketSource
    requester_id: uuid.UUID | None
    requester_email: EmailStr
    subject: str
    description: str | None
    category: TicketCategory
    priority: TicketPriority
    risk_level: RiskLevel
    team: TicketTeam
    status: TicketStatus
    assigned_agent_id: uuid.UUID | None
    ai_summary: str | None
    sla_due_at: datetime | None
    created_at: datetime
    updated_at: datetime


class TicketDetailRead(TicketRead):
    timeline_events: list[TimelineEventRead] = Field(default_factory=list)
    attachments: list[AttachmentRead] = Field(default_factory=list)


class ApprovalRequest(BaseModel):
    decision: str = Field(pattern="^(approved|rejected)$")
    reason: str = Field(min_length=1)


class TicketEscalation(BaseModel):
    team: TicketTeam
    note: str = Field(min_length=1)
    actor_id: uuid.UUID | None = None
