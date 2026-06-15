from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from ai.config.constants import TicketPrefillCategory, TicketPriority


class ChatMessage(BaseModel):
    role: str = Field(pattern="^(user|assistant|system)$")
    content: str = Field(min_length=1, max_length=20_000)
    created_at: datetime | None = None


class ChatRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=128)
    user_id: str = Field(min_length=1, max_length=128)
    message: str = Field(min_length=1, max_length=20_000)


class TicketPrefill(BaseModel):
    source: Literal["chat"] = "chat"
    subject: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=2_000)
    category: TicketPrefillCategory


class ChatResponse(BaseModel):
    response: str
    sources: list[str] = Field(default_factory=list)
    escalate: bool = False
    ticket_prefill: TicketPrefill | None = None


class ChatEscalationTicketPrefill(BaseModel):
    source: Literal["chat"] = "chat"
    subject: str = Field(min_length=1, max_length=500)
    description: str = Field(min_length=1, max_length=20_000)
    category: TicketPrefillCategory
    priority: TicketPriority = TicketPriority.MEDIUM
    risk_level: Literal["standard", "high"] = "standard"
    team: Literal["it", "security", "devops", "hr", "management"] = "it"
    status: Literal["open"] = "open"
    sla: str = Field(default="standard", min_length=1, max_length=128)
    ai_summary: str | None = Field(default=None, max_length=5_000)
    timeline_note: str = Field(
        default="Chat escalation note: user requested support from AI chat.",
        min_length=1,
        max_length=5_000,
    )


class ChatEscalationRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=128)
    user_id: str = Field(min_length=1, max_length=128)
    requester: str | None = Field(default=None, min_length=1, max_length=320)
    ticket_prefill: ChatEscalationTicketPrefill


class ChatEscalationResponse(BaseModel):
    success: bool
    ticket_id: str | None = None
    message: str
    backend_response: dict | None = None
    error: str | None = None
