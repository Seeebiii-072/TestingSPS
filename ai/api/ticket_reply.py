"""POST /api/ticket-reply — AI-powered auto-reply for support tickets.

Reuses the existing KB retriever, escalation assessment, and guardrail
validation from the chat assistant to decide whether an incoming ticket
can be confidently answered by the AI (and thus auto-resolved) or needs
to go to a human agent.
"""

import logging
import re
from pathlib import Path

from fastapi import APIRouter

from ai.chat.assistant import FORBIDDEN_RESPONSE_PATTERNS
from ai.chat.escalation import assess_escalation, guardrail_escalation, no_answer_escalation
from ai.kb.retriever import RetrievalResult, search
from ai.llm.router import async_generate_response_with_provider
from ai.schemas.ticket_reply import TicketReplyRequest, TicketReplyResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ticket-reply"])

PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "chat_system.txt"


def _source_label(result: RetrievalResult) -> str:
    document_name = Path(result.document_name).stem
    return f"{document_name}, {result.section}"


def _unique_sources(results: list[RetrievalResult]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for result in results:
        label = _source_label(result)
        if label not in seen:
            seen.add(label)
            unique.append(label)
    return unique


@router.post("/api/ticket-reply", response_model=TicketReplyResponse)
async def ticket_reply(request: TicketReplyRequest) -> TicketReplyResponse:
    """Generate an AI auto-reply for a support ticket, reusing KB and
    escalation logic from the web chat assistant.

    Returns a grounded answer with confident=True if the KB confidently
    answers the question; otherwise returns escalate=True with no answer.
    """
    # Build a composite query from category, subject, and description for KB search
    query = f"{request.category}\n{request.subject}\n{request.description}"

    escalation = assess_escalation(query)
    if escalation.required:
        logger.info(
            "Ticket reply: escalation required by assess_escalation for subject=%s",
            request.subject[:60],
        )
        return TicketReplyResponse(escalate=True, confident=False)

    results = search(query)
    if not results:
        no_answer = no_answer_escalation(query)
        logger.info(
            "Ticket reply: no KB results for subject=%s, escalation=%s",
            request.subject[:60],
            no_answer.reason,
        )
        return TicketReplyResponse(escalate=True, confident=False)

    sources = _unique_sources(results)
    system_prompt = PROMPT_PATH.read_text(encoding="utf-8").strip()

    kb_context = "\n\n".join(
        f"Source: {source}\n{result.content}"
        for result, source in zip(results, sources)
    )

    user_prompt = (
        "KNOWLEDGE BASE SECTIONS:\n"
        f"{kb_context}\n\n"
        "TICKET SUBJECT:\n"
        f"{request.subject}\n\n"
        "TICKET DESCRIPTION:\n"
        f"{request.description}\n\n"
        "Answer only from the knowledge base sections above. Cite every "
        "source used on its own line using the exact Source label provided."
    )

    generated = await async_generate_response_with_provider(
        system_prompt, user_prompt
    )
    response_text = generated.text.strip()

    if not response_text:
        no_answer = no_answer_escalation(query)
        logger.info(
            "Ticket reply: LLM returned empty response, escalation=%s",
            no_answer.reason,
        )
        return TicketReplyResponse(escalate=True, confident=False)

    if any(
        re.search(pattern, response_text, flags=re.IGNORECASE)
        for pattern in FORBIDDEN_RESPONSE_PATTERNS
    ):
        guardrail = guardrail_escalation(query)
        logger.info(
            "Ticket reply: guardrail violation in response, escalation=%s",
            guardrail.reason,
        )
        return TicketReplyResponse(escalate=True, confident=False)

    # Validate that cited sources are from the retrieved KB
    claimed_sources = re.findall(
        r"(?im)^\s*Source:\s*(.+?)\s*$",
        response_text,
    )
    allowed_sources = {source.casefold() for source in sources}
    if any(
        s.strip().casefold() not in allowed_sources for s in claimed_sources
    ):
        logger.info(
            "Ticket reply: LLM cited source outside retrieved KB, escalating"
        )
        return TicketReplyResponse(escalate=True, confident=False)

    # Extract the grounded body (remove citation lines)
    grounded_lines = [
        line
        for line in response_text.splitlines()
        if not line.strip().lower().startswith("source:")
    ]
    grounded_body = "\n".join(grounded_lines).strip()
    if not grounded_body:
        no_answer = no_answer_escalation(query)
        logger.info(
            "Ticket reply: no grounded answer body, escalation=%s",
            no_answer.reason,
        )
        return TicketReplyResponse(escalate=True, confident=False)

    citations = "\n".join(f"Source: {source}" for source in sources)
    final_answer = f"{grounded_body}\n\n{citations}"

    logger.info(
        "Ticket reply: confident KB match for subject=%s", request.subject[:60]
    )
    return TicketReplyResponse(
        answer=final_answer,
        sources=sources,
        confident=True,
        escalate=False,
    )