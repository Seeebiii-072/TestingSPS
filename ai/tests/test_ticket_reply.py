"""Tests for the AI ticket auto-reply endpoint."""

import unittest
from unittest.mock import patch

from ai.api.ticket_reply import _unique_sources, ticket_reply
from ai.kb.retriever import RetrievalResult
from ai.llm.router import GenerationResult
from ai.schemas.ticket_reply import TicketReplyRequest, TicketReplyResponse


def _make_kb_result(content: str, document_name: str = "faq.pdf", section: str = "General") -> RetrievalResult:
    return RetrievalResult(
        content=content,
        score=0.85,
        document_name=document_name,
        section=section,
        chunk_id="chunk-1",
        source_path="/kb/faq.pdf",
        created_at="2026-01-01",
    )


class TestUniqueSources(unittest.TestCase):
    """Tests for the _unique_sources helper."""

    def test_deduplicates_same_source(self):
        results = [
            _make_kb_result("Content A", "faq.pdf", "General"),
            _make_kb_result("Content B", "faq.pdf", "General"),
        ]
        sources = _unique_sources(results)
        self.assertEqual(sources, ["faq, General"])

    def test_multiple_sources(self):
        results = [
            _make_kb_result("Content A", "faq.pdf", "General"),
            _make_kb_result("Content B", "guide.pdf", "Setup"),
        ]
        sources = _unique_sources(results)
        self.assertEqual(sources, ["faq, General", "guide, Setup"])


class TestTicketReply(unittest.IsolatedAsyncioTestCase):
    """Tests for the ticket_reply endpoint function."""

    @patch("ai.api.ticket_reply.search")
    @patch("ai.api.ticket_reply.async_generate_response_with_provider")
    async def test_confident_kb_match_returns_grounded_reply(
        self, mock_generate, mock_search
    ):
        """A confident KB match should return a grounded answer."""
        mock_search.return_value = [
            _make_kb_result(
                "To reset your password, visit the account settings page.",
                "faq.pdf",
                "Password Reset",
            )
        ]
        mock_generate.return_value = GenerationResult(
            text="You can reset your password by visiting the account settings page.\n\nSource: faq, Password Reset",
            provider="test",
        )

        request = TicketReplyRequest(
            subject="How to reset password?",
            description="I need to reset my password.",
            category="general_it",
        )
        response = await ticket_reply(request)
        self.assertTrue(response.confident)
        self.assertFalse(response.escalate)
        self.assertIn("reset your password", response.answer)
        self.assertIn("Source: faq, Password Reset", response.answer)

    @patch("ai.api.ticket_reply.search")
    async def test_no_kb_match_returns_escalate(self, mock_search):
        """No KB results should return escalate=True."""
        mock_search.return_value = []

        request = TicketReplyRequest(
            subject="Unknown topic",
            description="Something not in the KB.",
            category="general_it",
        )
        response = await ticket_reply(request)
        self.assertFalse(response.confident)
        self.assertTrue(response.escalate)
        self.assertEqual(response.answer, "")

    @patch("ai.api.ticket_reply.search")
    @patch("ai.api.ticket_reply.async_generate_response_with_provider")
    async def test_guardrail_violation_returns_escalate(
        self, mock_generate, mock_search
    ):
        """A guardrail-violating response should escalate."""
        mock_search.return_value = [
            _make_kb_result(
                "Admins can approve access requests.",
                "admin.pdf",
                "Access Control",
            )
        ]
        mock_generate.return_value = GenerationResult(
            text="I have approved your access request.\n\nSource: admin, Access Control",
            provider="test",
        )

        request = TicketReplyRequest(
            subject="Approve my access",
            description="Please approve my admin access.",
            category="identity_access",
        )
        response = await ticket_reply(request)
        self.assertFalse(response.confident)
        self.assertTrue(response.escalate)
        self.assertEqual(response.answer, "")

    @patch("ai.api.ticket_reply.search")
    @patch("ai.api.ticket_reply.async_generate_response_with_provider")
    async def test_empty_response_escalates(self, mock_generate, mock_search):
        """An empty LLM response should escalate."""
        mock_search.return_value = [
            _make_kb_result("Some KB content.", "faq.pdf", "General")
        ]
        mock_generate.return_value = GenerationResult(
            text="",
            provider="test",
        )

        request = TicketReplyRequest(
            subject="Test",
            description="Test description.",
            category="general_it",
        )
        response = await ticket_reply(request)
        self.assertFalse(response.confident)
        self.assertTrue(response.escalate)

    @patch("ai.api.ticket_reply.search")
    @patch("ai.api.ticket_reply.async_generate_response_with_provider")
    async def test_citation_outside_kb_escalates(self, mock_generate, mock_search):
        """A response citing a source outside the retrieved KB should escalate."""
        mock_search.return_value = [
            _make_kb_result("KB content.", "faq.pdf", "General")
        ]
        mock_generate.return_value = GenerationResult(
            text="Some answer.\n\nSource: unknown, Outside",
            provider="test",
        )

        request = TicketReplyRequest(
            subject="Test",
            description="Test description.",
            category="general_it",
        )
        response = await ticket_reply(request)
        self.assertFalse(response.confident)
        self.assertTrue(response.escalate)