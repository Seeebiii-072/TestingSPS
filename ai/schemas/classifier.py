from enum import Enum

import re

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ai.config.constants import TicketPrefillCategory, TicketPriority


class ClassifierRisk(str, Enum):
    STANDARD = "standard"
    HIGH = "high"


class ClassifierTeam(str, Enum):
    IT = "it"
    SECURITY = "security"
    DEVOPS = "devops"
    HR = "hr"
    MANAGEMENT = "management"


class ClassifierRequest(BaseModel):
    subject: str = Field(min_length=1, max_length=500)
    description: str = Field(min_length=1, max_length=20_000)


class ClassifierResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: TicketPrefillCategory
    priority: TicketPriority
    risk_level: ClassifierRisk
    team: ClassifierTeam
    reasoning: str = Field(min_length=1, max_length=1_000)

    @field_validator("reasoning")
    @classmethod
    def require_one_sentence(cls, value: str) -> str:
        reasoning = value.strip()
        sentences = [
            item for item in re.split(r"(?<=[.!?])\s+", reasoning) if item
        ]
        if len(sentences) != 1:
            raise ValueError("reasoning must contain exactly one sentence.")
        return reasoning
