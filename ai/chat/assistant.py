import logging
import re
import inspect
from collections.abc import Awaitable, Callable
from pathlib import Path

from ai.chat.escalation import (
    EscalationDecision,
    assess_escalation,
    guardrail_escalation,
    no_answer_escalation,
)
from ai.chat.session import ChatSession, SessionStore, session_store
from ai.config.constants import TicketPrefillCategory
from ai.kb.retriever import RetrievalResult, search
from ai.llm.router import GenerationResult, async_generate_response_with_provider
from ai.schemas.chat import (
    ChatEscalationRequest,
    ChatEscalationTicketPrefill,
    ChatRequest,
    ChatResponse,
    TicketPrefill,
)
from ai.services.backend_client import BackendAPIError, get_backend_client

logger = logging.getLogger(__name__)


PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "chat_system.txt"
FORBIDDEN_RESPONSE_PATTERNS = (
    r"\bi (?:have |just )?(?:granted|approved|assigned|unlocked|reset)\b",
    r"\byour (?:access|request|role|permission) (?:has been|is) approved\b",
    r"\byour (?:admin|root|privileged) (?:password|account).{0,30}(?:reset|unlocked)\b",
    r"\b(?:security )?incident (?:is|has been) closed\b",
    r"\bi (?:searched|checked|used) (?:the )?internet\b",
)

Retriever = Callable[[str, int | None], list[RetrievalResult]]
Generator = Callable[[str, str], GenerationResult | Awaitable[GenerationResult]]


class ResponseGuardrailError(ValueError):
    """Raised when generated text violates grounding or safety rules."""


def _source_label(result: RetrievalResult) -> str:
    document_name = Path(result.document_name).stem
    return f"{document_name}, {result.section}"


def _unique_sources(results: list[RetrievalResult]) -> list[str]:
    return list(dict.fromkeys(_source_label(result) for result in results))


async def _try_create_escalation_ticket(
    request: ChatRequest,
    decision: EscalationDecision,
) -> ChatResponse:
    if not request.requester_email:
        logger.info(
            "Skipping auto-ticket creation for session %s because requester_email is missing",
            request.session_id,
        )
        return ChatResponse(
            response=decision.response,
            sources=[],
            escalate=True,
            ticket_prefill=decision.ticket_prefill,
            ticket_number=None,
            ticket_id=None,
        )

    backend_client = get_backend_client()
    prefill = _build_escalation_prefill(decision)

    try:
        data = await backend_client.create_ticket(
            prefill=prefill,
            requester_email=request.requester_email,
        )
        ticket_number = data.get("ticket_number")
        ticket_id = data.get("id")
        logger.info(
            "Auto-created escalation ticket %s (id=%s) for session %s",
            ticket_number,
            ticket_id,
            request.session_id,
        )
        return ChatResponse(
            response=f"This requires a support agent. I've created ticket {ticket_number} for you — a support agent will be with you shortly.",
            sources=[],
            escalate=True,
            ticket_prefill=None,
            ticket_number=ticket_number,
            ticket_id=str(ticket_id) if ticket_id is not None else None,
        )
    except BackendAPIError as exc:
        logger.warning("Failed to auto-create escalation ticket: %s", exc)
        return ChatResponse(
            response=decision.response,
            sources=[],
            escalate=True,
            ticket_prefill=decision.ticket_prefill,
            ticket_number=None,
            ticket_id=None,
        )


def _build_escalation_prefill(decision: EscalationDecision) -> ChatEscalationTicketPrefill:
    if decision.ticket_prefill is not None:
        source = decision.ticket_prefill.source
        subject = decision.ticket_prefill.subject
        description = decision.ticket_prefill.description
        category = decision.ticket_prefill.category
    else:
        source = "chat"
        subject = "Support request from AI chat"
        description = decision.response
        category = TicketPrefillCategory.GENERAL_IT

    risk_level = "high" if category == TicketPrefillCategory.CYBERSECURITY else "standard"
    team = _team_for_category(category)

    return ChatEscalationTicketPrefill(
        source=source,
        subject=subject,
        description=description,
        category=category,
        risk_level=risk_level,
        team=team,
    )


def _team_for_category(category: TicketPrefillCategory) -> str:
    mapping = {
        TicketPrefillCategory.CYBERSECURITY: "security",
        TicketPrefillCategory.IDENTITY_ACCESS: "security",
        TicketPrefillCategory.CLOUD: "devops",
        TicketPrefillCategory.DEVOPS: "devops",
        TicketPrefillCategory.INTERNSHIP_HR: "hr",
        TicketPrefillCategory.GENERAL_IT: "it",
    }
    return mapping.get(category, "it")


def _build_user_prompt(
    request: ChatRequest,
    session: ChatSession,
    results: list[RetrievalResult],
) -> str:
    context = (
        session.short_context(exclude_latest_user=True)
        or "No previous conversation."
    )
    kb_context = "\n\n".join(
        f"Source: {_source_label(result)}\n{result.content}" for result in results
    )
    return (
        "SESSION CONTEXT (same user only):\n"
        f"{context}\n\n"
        "KNOWLEDGE BASE SECTIONS:\n"
        f"{kb_context}\n\n"
        "USER QUESTION:\n"
        f"{request.message}\n\n"
        "Answer only from the knowledge base sections above. Cite every source used "
        "on its own line using the exact Source label provided."
    )


def _validate_and_cite_response(
    generated_text: str,
    sources: list[str],
) -> str:
    response = generated_text.strip()
    if not response:
        raise ResponseGuardrailError("The LLM returned an empty response")
    if not sources:
        raise ResponseGuardrailError("A grounded response requires KB sources")
    if any(
        re.search(pattern, response, flags=re.IGNORECASE)
        for pattern in FORBIDDEN_RESPONSE_PATTERNS
    ):
        raise ResponseGuardrailError("The LLM response contains a prohibited action")

    claimed_sources = re.findall(
        r"(?im)^\s*Source:\s*(.+?)\s*$",
        response,
    )
    allowed_sources = {source.casefold() for source in sources}
    if any(source.strip().casefold() not in allowed_sources for source in claimed_sources):
        raise ResponseGuardrailError("The LLM cited a source outside the retrieved KB")

    grounded_lines = [
        line for line in response.splitlines() if not line.strip().lower().startswith("source:")
    ]
    grounded_body = "\n".join(grounded_lines).strip()
    if not grounded_body:
        raise ResponseGuardrailError("The LLM response contains no answer text")
    if "source:" in grounded_body.casefold():
        raise ResponseGuardrailError("The LLM used an invalid citation format")

    citations = "\n".join(f"Source: {source}" for source in sources)
    return f"{grounded_body}\n\n{citations}"


class ChatAssistant:
    def __init__(
        self,
        *,
        retriever: Retriever = search,
        generator: Generator = async_generate_response_with_provider,
        sessions: SessionStore = session_store,
    ) -> None:
        self._retriever = retriever
        self._generator = generator
        self._sessions = sessions

    async def respond(self, request: ChatRequest) -> ChatResponse:
        session = self._sessions.get_or_create(request.session_id, request.user_id)
        with session.lock:
            session.add_message("user", request.message)

            escalation = assess_escalation(
                request.message,
                repeated_count=session.repeated_question_count(request.message),
            )
            if escalation.required:
                response = await _try_create_escalation_ticket(request, escalation)
                session.add_message("assistant", response.response)
                return response

            results = self._retriever(request.message, None)
            if not results:
                no_answer = no_answer_escalation(request.message)
                response = await _try_create_escalation_ticket(request, no_answer)
                session.add_message("assistant", response.response)
                return response

            sources = _unique_sources(results)
            system_prompt = PROMPT_PATH.read_text(encoding="utf-8").strip()
            user_prompt = _build_user_prompt(request, session, results)
            generated_result = self._generator(system_prompt, user_prompt)
            generated = await generated_result if inspect.isawaitable(generated_result) else generated_result

            try:
                grounded_response = _validate_and_cite_response(generated.text, sources)
            except ResponseGuardrailError:
                guardrail = guardrail_escalation(request.message)
                response = await _try_create_escalation_ticket(request, guardrail)
                session.add_message("assistant", response.response)
                return response

            response = ChatResponse(
                response=grounded_response,
                sources=sources,
                escalate=False,
                ticket_prefill=None,
            )
            session.add_message("assistant", response.response)
            return response
