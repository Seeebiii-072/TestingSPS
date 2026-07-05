"""Schemas for the AI ticket auto-reply endpoint."""

from pydantic import BaseModel, Field


class TicketReplyRequest(BaseModel):
    """Request to generate an AI reply for a support ticket."""

    subject: str = Field(min_length=1, max_length=500)
    description: str = Field(min_length=1, max_length=20_000)
    category: str = Field(min_length=1, max_length=50)


class TicketReplyResponse(BaseModel):
    """Response from the AI ticket auto-reply endpoint.

    If confident is True, the answer is grounded in the KB and can be
    sent as an auto-reply. If confident is False, the AI could not
    confidently answer and the ticket should remain in the human queue.
    """

    answer: str = ""
    sources: list[str] = Field(default_factory=list)
    confident: bool = False
    escalate: bool = False