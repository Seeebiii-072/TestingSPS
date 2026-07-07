from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from ai.llm.router import LLMGenerationError, generate_response_with_provider

router = APIRouter(prefix="/enhance-description", tags=["enhance-description"])

PROMPT_PATH = "ai/prompts/description_enhancer.txt"


class EnhanceDescriptionRequest(BaseModel):
    subject: str = Field(min_length=1, max_length=500)
    description: str = Field(min_length=1, max_length=5000)


class EnhanceDescriptionResponse(BaseModel):
    enhanced_description: str


@router.post("", response_model=EnhanceDescriptionResponse)
async def enhance_description(payload: EnhanceDescriptionRequest) -> EnhanceDescriptionResponse:
    try:
        with open(PROMPT_PATH, "r", encoding="utf-8") as f:
            system_prompt = f.read().strip()
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="Enhancer prompt not configured") from None

    user_content = (
        f"Subject: {payload.subject}\n"
        f"Description: {payload.description}\n\n"
        "Rewrite the description above following the instructions in the system prompt."
    )

    try:
        generated = generate_response_with_provider(system_prompt, user_content)
        enhanced = generated.text.strip()
    except LLMGenerationError:
        raise HTTPException(status_code=502, detail="AI description enhancement failed") from None

    if not enhanced:
        raise HTTPException(status_code=502, detail="AI returned an empty enhancement")

    return EnhanceDescriptionResponse(enhanced_description=enhanced)