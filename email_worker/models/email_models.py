"""Pydantic models for email parsing, content, and envelope data."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class EmailAttachment(BaseModel):
    """Represents a single email attachment."""

    filename: str
    content_type: str
    size: int
    content: Optional[bytes] = None


class ParsedEmail(BaseModel):
    """Fully parsed inbound email with headers and body."""

    model_config = ConfigDict(populate_by_name=True)

    message_id: str = Field(default="", alias="Message-ID")
    in_reply_to: Optional[str] = Field(default=None, alias="In-Reply-To")
    from_address: str
    to_address: Optional[str] = None
    subject: str = ""
    plain_text_body: str = ""
    html_body: str = ""
    attachments: List[EmailAttachment] = []
    received_at: datetime = Field(default_factory=datetime.utcnow)


class OutboundEmail(BaseModel):
    """Payload for building and sending an outbound email."""

    to_email: str
    subject: str
    html_body: str
    plain_text_body: str
    ticket_id: Optional[str] = None
    message_id: Optional[str] = None


class EmailTemplateData(BaseModel):
    """Variables passed to Jinja2 email templates."""

    ticket_id: str
    subject: str
    requester_name: str = "Valued Customer"
    requester_email: str = ""
    description: str = ""
    status: str = ""
    category: str = ""
    priority: str = ""
    team: str = ""
    agent_name: str = ""
    reply_content: str = ""
    portal_url: str = ""
    approval_url: str = ""
    current_year: int = Field(default_factory=lambda: datetime.utcnow().year)