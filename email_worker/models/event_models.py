"""Pydantic models for backend event polling and event payloads."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional, Literal

from pydantic import BaseModel, Field


EventType = Literal[
    "ticket_created",
    "agent_reply",
    "status_changed",
    "approval_required",
]


class BackendEvent(BaseModel):
    """An event received from the backend email events feed."""

    event_type: EventType
    ticket_id: str
    data: Dict[str, Any] = {}
    occurred_at: datetime = Field(default_factory=datetime.utcnow)


class TicketCreatePayload(BaseModel):
    """Payload for creating a new ticket via the backend API."""

    source: str = "email"
    subject: str
    description: str
    requester_email: str
    category: str = ""
    priority: str = ""
    team: str = ""


class TimelineEventPayload(BaseModel):
    """Payload for appending an event to a ticket's timeline."""

    event_type: str
    content: str


class ClassifyResponse(BaseModel):
    """Response from the AI classification endpoint."""

    category: str
    priority: str
    team: str