import re
from collections.abc import Callable
from pathlib import Path

from ai.llm.router import GenerationResult, LLMGenerationError, generate_response_with_provider
from ai.schemas.summariser import SummariserRequest, SummariserResponse


PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "summariser.txt"
Generator = Callable[[str, str], GenerationResult]
SENTENCE_PATTERN = re.compile(r"(?<=[.!?])\s+")
FACT_MARKER_PATTERN = re.compile(
    r"\b\d+(?::\d+)?(?:%|am|pm)?\b|"
    r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b|"
    r"https?://\S+",
    re.IGNORECASE,
)


def _ticket_content(request: SummariserRequest) -> str:
    messages = "\n".join(
        f"{message.role}: {message.content}" for message in request.messages
    )
    return (
        f"Subject: {request.subject}\n"
        f"Description: {request.description}\n"
        f"Messages:\n{messages or 'None'}"
    )


def _sentence_count(text: str) -> int:
    return len(
        [
            sentence
            for sentence in SENTENCE_PATTERN.split(text.strip())
            if sentence.strip()
        ]
    )


def _clean_summary(text: str, source: str) -> str:
    summary = text.strip()
    if summary.startswith("```") or summary.endswith("```"):
        raise ValueError("Summariser returned markdown.")
    if _sentence_count(summary) not in {2, 3}:
        raise ValueError("Summariser must return two or three sentences.")
    source_markers = {
        marker.casefold() for marker in FACT_MARKER_PATTERN.findall(source)
    }
    summary_markers = {
        marker.casefold() for marker in FACT_MARKER_PATTERN.findall(summary)
    }
    if not summary_markers.issubset(source_markers):
        raise ValueError("Summariser introduced factual markers absent from the ticket.")
    return summary


def _fallback_summary(request: SummariserRequest) -> str:
    description = " ".join(request.description.split()).rstrip(".!?")
    first = f"{description}."
    context = " ".join(message.content for message in request.messages).strip()
    if context:
        context = " ".join(context.split()).rstrip(".!?")
        second = f"Additional ticket context: {context}."
    else:
        second = f"Support review is requested for: {request.subject.strip()}."
    return f"{first} {second}"


def summarise_text(
    request: SummariserRequest,
    *,
    generator: Generator = generate_response_with_provider,
) -> SummariserResponse:
    system_prompt = PROMPT_PATH.read_text(encoding="utf-8").strip()
    ticket_content = _ticket_content(request)
    try:
        generated = generator(system_prompt, ticket_content)
        summary = _clean_summary(generated.text, ticket_content)
    except (LLMGenerationError, ValueError):
        summary = _fallback_summary(request)
    return SummariserResponse(summary=summary)
