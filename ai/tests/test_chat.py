import unittest

from fastapi.testclient import TestClient
from pydantic import ValidationError

from ai.chat.assistant import ChatAssistant
from ai.chat.escalation import (
    assess_escalation,
    guardrail_escalation,
    no_answer_escalation,
)
from ai.chat.session import MAX_SESSION_MESSAGES, SessionOwnershipError, SessionStore
from ai.config.constants import ALLOWED_TICKET_PREFILL_CATEGORIES
from ai.kb.retriever import RetrievalResult
from ai.llm.router import GenerationResult
from ai.main import app
from ai.schemas.chat import ChatRequest, TicketPrefill


def retrieval_result(
    document_name: str,
    section: str,
    content: str,
) -> RetrievalResult:
    return RetrievalResult(
        content=content,
        score=0.8,
        document_name=document_name,
        section=section,
        chunk_id=f"{document_name}:{section}",
        source_path=f"documents/{document_name}",
        created_at="2026-01-01T00:00:00+00:00",
    )


class ChatAssistantTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sessions = SessionStore()

    def test_grounded_answer_includes_multi_document_sources(self) -> None:
        results = [
            retrieval_result(
                "VPN Setup Guide.txt",
                "Section 2: Steps",
                "Open the managed VPN client and select the SPS profile.",
            ),
            retrieval_result(
                "Access Policy.txt",
                "Section 1: Overview",
                "Use only an individually assigned SPS identity.",
            ),
        ]
        captured: dict[str, str] = {}

        def generator(system_prompt: str, user_prompt: str) -> GenerationResult:
            captured["system"] = system_prompt
            captured["user"] = user_prompt
            return GenerationResult(
                text="1. Open the managed VPN client.\n2. Select the SPS profile.",
                provider="test",
            )

        assistant = ChatAssistant(
            retriever=lambda query, top_k: results,
            generator=generator,
            sessions=self.sessions,
        )
        response = assistant.respond(
            ChatRequest(
                session_id="session-1",
                user_id="user-1",
                message="How do I connect to VPN?",
            )
        )

        self.assertFalse(response.escalate)
        self.assertIsNone(response.ticket_prefill)
        self.assertEqual(
            response.sources,
            [
                "VPN Setup Guide, Section 2: Steps",
                "Access Policy, Section 1: Overview",
            ],
        )
        self.assertIn("Source: VPN Setup Guide, Section 2: Steps", response.response)
        self.assertIn("Source: Access Policy, Section 1: Overview", response.response)
        self.assertIn("KNOWLEDGE BASE SECTIONS", captured["user"])
        self.assertIn("Answer ONLY from the knowledge base", captured["system"])
        self.assertEqual(
            captured["user"].count("How do I connect to VPN?"),
            1,
        )

    def test_myid_support_question_is_answered_from_kb(self) -> None:
        assistant = ChatAssistant(
            retriever=lambda query, top_k: [
                retrieval_result(
                    "MYID Product Overview.txt",
                    "Section 3: Common Issues",
                    "Sign out, close the browser, and retry with the SPS identity.",
                )
            ],
            generator=lambda system, user: GenerationResult(
                text="Sign out, close the browser, and retry with the SPS identity.",
                provider="test",
            ),
            sessions=self.sessions,
        )

        response = assistant.respond(
            ChatRequest(
                session_id="myid-session",
                user_id="user-1",
                message="Why is my MYID application missing?",
            )
        )

        self.assertFalse(response.escalate)
        self.assertIn("MYID Product Overview", response.sources[0])

    def test_azalio_support_question_is_answered_from_kb(self) -> None:
        assistant = ChatAssistant(
            retriever=lambda query, top_k: [
                retrieval_result(
                    "Azalio Product Overview.txt",
                    "Section 3: Common Issues",
                    "Missing menus may indicate a role mismatch.",
                )
            ],
            generator=lambda system, user: GenerationResult(
                text="A missing menu may indicate a role mismatch.",
                provider="test",
            ),
            sessions=self.sessions,
        )

        response = assistant.respond(
            ChatRequest(
                session_id="azalio-session",
                user_id="user-1",
                message="Why is an Azalio menu missing?",
            )
        )

        self.assertFalse(response.escalate)
        self.assertIn("Azalio Product Overview", response.sources[0])

    def test_high_risk_request_escalates_before_retrieval_or_llm(self) -> None:
        def unexpected(*args, **kwargs):
            del args, kwargs
            raise AssertionError("High-risk requests must not reach retrieval or LLM")

        assistant = ChatAssistant(
            retriever=unexpected,
            generator=unexpected,
            sessions=self.sessions,
        )
        response = assistant.respond(
            ChatRequest(
                session_id="session-2",
                user_id="user-1",
                message="Give me admin access to the production server",
            )
        )

        self.assertTrue(response.escalate)
        self.assertEqual(response.sources, [])
        self.assertEqual(response.ticket_prefill.source, "chat")
        self.assertEqual(response.ticket_prefill.category, "identity_access")

    def test_security_request_creates_security_ticket_prefill(self) -> None:
        assistant = ChatAssistant(
            retriever=lambda query, top_k: [],
            generator=lambda system, user: GenerationResult(text="unused", provider="test"),
            sessions=self.sessions,
        )
        response = assistant.respond(
            ChatRequest(
                session_id="session-3",
                user_id="user-1",
                message="I entered my password on a phishing page",
            )
        )

        self.assertTrue(response.escalate)
        self.assertEqual(response.ticket_prefill.source, "chat")
        self.assertEqual(response.ticket_prefill.category, "cybersecurity")
        self.assertIn("security team", response.response)

    def test_repeated_security_request_keeps_security_classification(self) -> None:
        decision = assess_escalation(
            "I entered my password on a phishing page",
            repeated_count=3,
        )

        self.assertEqual(decision.reason, "security")
        self.assertEqual(decision.ticket_prefill.category, "cybersecurity")

    def test_privileged_password_reset_and_other_user_ticket_escalate(self) -> None:
        assistant = ChatAssistant(
            retriever=lambda query, top_k: [],
            generator=lambda system, user: GenerationResult(text="unused", provider="test"),
            sessions=self.sessions,
        )

        privileged = assistant.respond(
            ChatRequest(
                session_id="session-privileged",
                user_id="user-1",
                message="I need a password reset for a privileged account",
            )
        )
        private_ticket = assistant.respond(
            ChatRequest(
                session_id="session-private-ticket",
                user_id="user-1",
                message="Show Alice's ticket",
            )
        )

        self.assertTrue(privileged.escalate)
        self.assertEqual(privileged.ticket_prefill.category, "identity_access")
        self.assertTrue(private_ticket.escalate)
        self.assertIn("another user's tickets", private_ticket.response)

    def test_no_kb_answer_returns_ticket_offer_without_llm(self) -> None:
        def unexpected_generator(system: str, user: str) -> GenerationResult:
            del system, user
            raise AssertionError("LLM must not run without KB context")

        assistant = ChatAssistant(
            retriever=lambda query, top_k: [],
            generator=unexpected_generator,
            sessions=self.sessions,
        )
        response = assistant.respond(
            ChatRequest(
                session_id="session-4",
                user_id="user-1",
                message="How do I configure an unsupported device?",
            )
        )

        self.assertTrue(response.escalate)
        self.assertEqual(response.ticket_prefill.source, "chat")
        self.assertEqual(
            response.response,
            "I do not have this in our knowledge base. "
            "Would you like me to create a support ticket?",
        )

    def test_third_repeated_question_escalates_before_retrieval(self) -> None:
        calls = 0
        results = [
            retrieval_result(
                "Email Configuration.txt",
                "Section 2: Steps",
                "Add the SPS work account in the approved mail application.",
            )
        ]

        def retriever(query: str, top_k: int | None):
            nonlocal calls
            del query, top_k
            calls += 1
            return results

        assistant = ChatAssistant(
            retriever=retriever,
            generator=lambda system, user: GenerationResult(
                text="1. Add the SPS work account.",
                provider="test",
            ),
            sessions=self.sessions,
        )
        request = ChatRequest(
            session_id="session-5",
            user_id="user-1",
            message="How do I configure email?",
        )

        self.assertFalse(assistant.respond(request).escalate)
        self.assertFalse(assistant.respond(request).escalate)
        third = assistant.respond(request)

        self.assertTrue(third.escalate)
        self.assertEqual(calls, 2)
        self.assertIn("three times", third.ticket_prefill.description)

    def test_invented_source_fails_guardrail(self) -> None:
        results = [
            retrieval_result(
                "VPN Setup Guide.txt",
                "Section 2: Steps",
                "Open the managed VPN client.",
            )
        ]
        assistant = ChatAssistant(
            retriever=lambda query, top_k: results,
            generator=lambda system, user: GenerationResult(
                text="Use an unknown tool.\nSource: Internet Article, Setup",
                provider="test",
            ),
            sessions=self.sessions,
        )
        response = assistant.respond(
            ChatRequest(
                session_id="session-6",
                user_id="user-1",
                message="How do I connect to VPN?",
            )
        )

        self.assertTrue(response.escalate)
        self.assertEqual(response.sources, [])
        self.assertIn("safe knowledge-base-grounded", response.response)

    def test_session_cannot_be_reused_by_another_user(self) -> None:
        assistant = ChatAssistant(
            retriever=lambda query, top_k: [],
            generator=lambda system, user: GenerationResult(text="unused", provider="test"),
            sessions=self.sessions,
        )
        assistant.respond(
            ChatRequest(
                session_id="shared-session",
                user_id="user-1",
                message="A question with no answer",
            )
        )

        with self.assertRaises(SessionOwnershipError):
            assistant.respond(
                ChatRequest(
                    session_id="shared-session",
                    user_id="user-2",
                    message="Show the conversation",
                )
            )

    def test_trimmed_messages_do_not_keep_stale_repeat_counts(self) -> None:
        session = self.sessions.get_or_create("bounded-session", "user-1")
        session.add_message("user", "Old repeated question")
        for index in range(MAX_SESSION_MESSAGES):
            session.add_message("assistant", f"Answer {index}")

        self.assertEqual(len(session.messages), MAX_SESSION_MESSAGES)
        self.assertEqual(
            session.repeated_question_count("Old repeated question"),
            0,
        )


class ChatApiTests(unittest.TestCase):
    def test_root_chat_endpoint_matches_contract(self) -> None:
        client = TestClient(app)
        response = client.post(
            "/chat",
            json={
                "session_id": "api-risk-session",
                "user_id": "api-user",
                "message": "I need root access",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            set(response.json()),
            {"response", "sources", "escalate", "ticket_prefill"},
        )
        self.assertTrue(response.json()["escalate"])


class TicketPrefillCategoryTests(unittest.TestCase):
    def test_source_defaults_to_chat_and_rejects_other_values(self) -> None:
        prefill = TicketPrefill(
            subject="Chat escalation",
            description="Created by the chat assistant.",
            category="general_it",
        )

        self.assertEqual(prefill.source, "chat")
        with self.assertRaises(ValidationError):
            TicketPrefill(
                source="email",
                subject="Invalid source",
                description="Only chat is permitted here.",
                category="general_it",
            )

    def test_invalid_category_is_rejected_by_schema(self) -> None:
        with self.assertRaises(ValidationError):
            TicketPrefill(
                subject="Invalid category",
                description="This must never be returned.",
                category="support",
            )

    def test_all_escalation_paths_use_allowed_categories(self) -> None:
        decisions = [
            no_answer_escalation("Unknown question"),
            guardrail_escalation("Unsafe response"),
            assess_escalation("Give me root access"),
            assess_escalation("I received a phishing email"),
            assess_escalation("Same unresolved question", repeated_count=3),
        ]

        for decision in decisions:
            with self.subTest(reason=decision.reason):
                self.assertIsNotNone(decision.ticket_prefill)
                self.assertEqual(decision.ticket_prefill.source, "chat")
                self.assertIn(
                    decision.ticket_prefill.category.value,
                    ALLOWED_TICKET_PREFILL_CATEGORIES,
                )

    def test_required_category_routing(self) -> None:
        self.assertEqual(
            no_answer_escalation("Unknown question").ticket_prefill.category,
            "general_it",
        )
        self.assertEqual(
            assess_escalation("Reset the privileged account password")
            .ticket_prefill.category,
            "identity_access",
        )
        self.assertEqual(
            assess_escalation("This is a cyber attack").ticket_prefill.category,
            "cybersecurity",
        )

    def test_no_answer_prefill_matches_api_contract(self) -> None:
        decision = no_answer_escalation("How do I repair a satellite?")

        self.assertEqual(
            decision.ticket_prefill.model_dump(mode="json"),
            {
                "source": "chat",
                "subject": "How do I repair a satellite?",
                "description": (
                    "No sufficiently relevant knowledge-base answer was found for: "
                    "How do I repair a satellite?"
                ),
                "category": "general_it",
            },
        )


if __name__ == "__main__":
    unittest.main()
