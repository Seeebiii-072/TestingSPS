from pydantic import BaseModel, Field


class SummariserMessage(BaseModel):
    role: str = Field(min_length=1, max_length=64)
    content: str = Field(min_length=1, max_length=20_000)


class SummariserRequest(BaseModel):
    subject: str = Field(min_length=1, max_length=500)
    description: str = Field(min_length=1, max_length=20_000)
    messages: list[SummariserMessage] = Field(default_factory=list, max_length=100)


class SummariserResponse(BaseModel):
    summary: str = Field(min_length=1, max_length=5_000)
