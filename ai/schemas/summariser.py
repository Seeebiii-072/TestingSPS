from pydantic import BaseModel, Field


class TimelineItem(BaseModel):
    event_type: str
    content: str
    created_at: str | None = None


class SummariserRequest(BaseModel):
    subject: str = Field(min_length=1, max_length=500)
    description: str = Field(min_length=1, max_length=100_000)
    timeline: list[TimelineItem] = Field(default_factory=list)


class SummariserResponse(BaseModel):
    summary: str
    key_points: list[str] = Field(default_factory=list)
    provider: str | None = None