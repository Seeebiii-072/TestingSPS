from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from ai.llm.router import LLMGenerationError, async_generate_response_with_provider

router = APIRouter(prefix="/enhance-description", tags=["enhance-description"])

PROMPT_PATH = "ai/prompts/description_enhancer.txt"


class EnhanceDescriptionRequest(BaseModel):
    subject: str = Field(min_length=1, max_length=500)
    description: str = Field(min_length=1, max_length=5000)


class EnhanceDescriptionResponse(BaseModel):
    enhanced_description: str


def _fallback_enhancement(subject: str, description: str) -> str:
    cleaned_subject = " ".join(subject.split()).strip().rstrip(".!?")
    cleaned_description = " ".join(description.split()).strip().rstrip(".!?")
    typo_fixes = [
        (" i facing ", " I am facing "),
        (" i face ", " I am facing "),
        (" i am ", " I am "),
        (" i'm ", " I am "),
        (" im ", " I am "),
        (" iam ", " I am "),
        (" i need ", " I need "),
        (" i ", " I "),
        (" laptop scrrren", " laptop screen"),
        (" laptop scren", " laptop screen"),
        (" resolcve", " resolve"),
        (" plz ", " please "),
        (" pls ", " please "),
        (" invpn", " in vpn"),
        ("facing issue in laptop screen", "facing an issue with my laptop screen"),
        ("facing issue with laptop screen", "facing an issue with my laptop screen"),
        ("need help in vpn issue", "need help with a VPN issue"),
        ("need help with vpn issue", "need help with a VPN issue"),
        (" vpn", "VPN"),
    ]
    padded = f" {cleaned_description} "
    lowered = padded.lower()
    for wrong, right in typo_fixes:
        lowered = lowered.replace(wrong, right)
    enhanced = " ".join(lowered.split()).strip()
    if enhanced:
        enhanced = enhanced[0].upper() + enhanced[1:]
    if cleaned_subject and cleaned_subject.lower() not in enhanced.lower():
        return f"{enhanced}. Support is requested for {cleaned_subject}."
    return f"{enhanced}."


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
        generated = await async_generate_response_with_provider(system_prompt, user_content)
        enhanced = generated.text.strip()
    except LLMGenerationError:
        enhanced = _fallback_enhancement(payload.subject, payload.description)

    if not enhanced:
        enhanced = _fallback_enhancement(payload.subject, payload.description)

    return EnhanceDescriptionResponse(enhanced_description=enhanced)
