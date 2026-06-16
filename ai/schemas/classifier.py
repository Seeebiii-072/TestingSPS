from pydantic import BaseModel, Field

from ai.config.constants import RiskLevel, SupportTeam, TicketCategory, TicketPriority


class ClassifierRequest(BaseModel):
    subject: str = Field(min_length=1, max_length=500)
    description: str = Field(min_length=1, max_length=20_000)


class ClassifierResponse(BaseModel):
    category: TicketCategory
    priority: TicketPriority
    risk_level: RiskLevel
    team: SupportTeam
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str | None = None