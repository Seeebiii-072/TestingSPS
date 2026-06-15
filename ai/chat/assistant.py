import re
from collections.abc import Callable
from pathlib import Path

from ai.chat.escalation import (
    EscalationDecision,
    assess_escalation,
    guardrail_escalation,
    no_answer_escalation,
)
from ai.chat.session import ChatSession, SessionStore, session_store
from ai.kb.retriever import RetrievalResult, search
from ai.llm.router import GenerationResult, generate_response_with_provider
from ai.schemas.chat import ChatRequest, ChatResponse


PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "chat_system.txt"
FORBIDDEN_RESPONSE_PATTERNS = (
    r"\bi (?:have |just )?(?:granted|approved|assigned|unlocked|reset)\b",
    r"\byour (?:access|request|role|permission) (?:has been|is) approved\b",
    r"\byour (?:admin|root|privileged) (?:password|account).{0,30}(?:reset|unlocked)\b",
    r"\b(?:security )?incident (?:is|has been) closed\b",
    r"\bi (?:searched|checked|used) (?:the )?internet\b",
)

Retriever = Callable[[str, int | None], list[RetrievalResult]]
Generator = Callable[[str, str], GenerationResult]


class ResponseGuardrailError(ValueError):
    """Raised when generated text violates grounding or safety rules."""


def _source_label(result: RetrievalResult) -> str:
    document_name = Path(result.document_name).stem
    return f"{document_name}, {result.section}"


def _unique_sources(results: list[RetrievalResult]) -> list[str]:
    return list(dict.fromkeys(_source_label(result) for result in results))


def _escalation_response(decision: EscalationDecision) -> ChatResponse:
    return ChatResponse(
        response=decision.response,
        sources=[],
        escalate=True,
        ticket_prefill=decision.ticket_prefill,
    )


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
        generator: Generator = generate_response_with_provider,
        sessions: SessionStore = session_store,
    ) -> None:
        self._retriever = retriever
        self._generator = generator
        self._sessions = sessions

    def respond(self, request: ChatRequest) -> ChatResponse:
        session = self._sessions.get_or_create(request.session_id, request.user_id)
        with session.lock:
            session.add_message("user", request.message)

            escalation = assess_escalation(
                request.message,
                repeated_count=session.repeated_question_count(request.message),
            )
            if escalation.required:
                response = _escalation_response(escalation)
                session.add_message("assistant", response.response)
                return response

            results = self._retriever(request.message, None)
            if not results:
                response = _escalation_response(no_answer_escalation(request.message))
                session.add_message("assistant", response.response)
                return response

            sources = _unique_sources(results)
            system_prompt = PROMPT_PATH.read_text(encoding="utf-8").strip()
            user_prompt = _build_user_prompt(request, session, results)
            generated = self._generator(system_prompt, user_prompt)

            try:
                grounded_response = _validate_and_cite_response(generated.text, sources)
            except ResponseGuardrailError:
                response = _escalation_response(guardrail_escalation(request.message))
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
