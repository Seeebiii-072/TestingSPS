from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator

from ai.config.constants import (
    RiskLevel,
    SLAStatus,
    SupportTeam,
    TicketCategory,
    TicketPriority,
    TicketSource,
    TicketStatus,
    TimelineEventType,
)


class RequesterIdentity(BaseModel):
    account_id: str | None = Field(default=None, min_length=1, max_length=128)
    email: str | None = Field(default=None, min_length=3, max_length=320)
    display_name: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def require_identity(self) -> "RequesterIdentity":
        if not self.account_id and not self.email:
            raise ValueError("Requester must have an account_id or email.")
        return self


class SourceSnapshot(BaseModel):
    external_id: str | None = Field(default=None, max_length=256)
    subject: str | None = Field(default=None, max_length=500)
    content: str = Field(min_length=1, max_length=100_000)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SLA(BaseModel):
    status: SLAStatus = SLAStatus.ON_TRACK
    response_due_at: datetime | None = None
    resolution_due_at: datetime | None = None
    responded_at: datetime | None = None
    resolved_at: datetime | None = None


class TimelineEvent(BaseModel):
    event_id: str
    event_type: TimelineEventType
    created_at: datetime
    actor_id: str | None = None
    body: str | None = None
    visible_to_requester: bool = False
    details: dict[str, Any] = Field(default_factory=dict)


class TicketCreate(BaseModel):
    source: TicketSource
    requester: RequesterIdentity
    subject: str = Field(min_length=1, max_length=500)
    description: str = Field(min_length=1, max_length=20_000)
    category: TicketCategory = TicketCategory.OTHER
    priority: TicketPriority = TicketPriority.MEDIUM
    risk: RiskLevel = RiskLevel.LOW
    team: SupportTeam = SupportTeam.SERVICE_DESK
    ai_summary: str | None = Field(default=None, max_length=5_000)
    source_snapshot: SourceSnapshot
    sla: SLA = Field(default_factory=SLA)


class Ticket(BaseModel):
    ticket_id: str
    source: TicketSource
    requester: RequesterIdentity
    subject: str
    description: str
    category: TicketCategory
    priority: TicketPriority
    risk: RiskLevel
    team: SupportTeam
    status: TicketStatus
    sla: SLA
    ai_summary: str | None = None
    assigned_agent_id: str | None = None
    escalation_note: str | None = None
    created_at: datetime
    updated_at: datetime
    timeline: list[TimelineEvent] = Field(default_factory=list)


class TicketUpdate(BaseModel):
    category: TicketCategory | None = None
    priority: TicketPriority | None = None
    risk: RiskLevel | None = None
    team: SupportTeam | None = None
    ai_summary: str | None = Field(default=None, max_length=5_000)

    @model_validator(mode="after")
    def reject_null_classification_fields(self) -> "TicketUpdate":
        for field in ("category", "priority", "risk", "team"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null.")
        return self


class AssignmentRequest(BaseModel):
    agent_id: str = Field(min_length=1, max_length=128)
    actor_id: str = Field(min_length=1, max_length=128)
    note: str | None = Field(default=None, max_length=2_000)


class EscalationRequest(BaseModel):
    actor_id: str = Field(min_length=1, max_length=128)
    note: str = Field(min_length=1, max_length=2_000)
    team: SupportTeam | None = None


class ResolveRequest(BaseModel):
    actor_id: str = Field(min_length=1, max_length=128)
    resolution: str = Field(min_length=1, max_length=5_000)


class ReplyRequest(BaseModel):
    actor_id: str = Field(min_length=1, max_length=128)
    message: str = Field(min_length=1, max_length=20_000)
