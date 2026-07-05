"""Tests for the AI auto-reply orchestration in the email poller."""

import unittest
from unittest.mock import AsyncMock

from email_worker.imap.poller import IMAPPoller
from email_worker.models.email_models import ParsedEmail
from email_worker.models.event_models import ClassifyResponse


def _make_parsed_email(
    subject: str = "Test subject",
    body: str = "Test body",
    from_address: str = "user@example.com",
) -> ParsedEmail:
    return ParsedEmail(
        message_id="<test@example.com>",
        from_address=from_address,
        subject=subject,
        plain_text_body=body,
        html_body="",
        attachments=[],
    )


class TestAutoReplyOrchestration(unittest.IsolatedAsyncioTestCase):
    """Tests for the auto-reply logic in _process_new_email."""

    async def test_standard_ticket_triggers_auto_reply(self):
        """A standard (non-critical, non-high-risk) ticket should trigger
        the AI auto-reply flow."""
        poller = IMAPPoller()
        poller.ticket_client = AsyncMock()

        poller.ticket_client.classify_email.return_value = ClassifyResponse(
            category="general_it",
            priority="medium",
            risk_level="standard",
            team="it",
        )

        poller.ticket_client.create_ticket.return_value = {
            "id": "test-ticket-id-123",
            "ticket_number": "SPS-2026-001",
        }

        poller.ticket_client.request_ticket_reply.return_value = {
            "answer": "Here is the solution.",
            "sources": ["faq, General"],
            "confident": True,
            "escalate": False,
        }

        poller.ticket_client.resolve_ticket_with_ai.return_value = {
            "status": "resolved",
            "ticket_id": "test-ticket-id-123",
            "ticket_number": "SPS-2026-001",
        }

        email_data = _make_parsed_email()
        await poller._process_new_email(email_data)

        poller.ticket_client.request_ticket_reply.assert_awaited_once()
        poller.ticket_client.resolve_ticket_with_ai.assert_awaited_once_with(
            ticket_id="test-ticket-id-123",
            answer="Here is the solution.",
            sources=["faq, General"],
        )

    async def test_critical_ticket_skips_auto_reply(self):
        """A critical-priority ticket should NOT trigger the auto-reply flow."""
        poller = IMAPPoller()
        poller.ticket_client = AsyncMock()

        poller.ticket_client.classify_email.return_value = ClassifyResponse(
            category="cybersecurity",
            priority="critical",
            risk_level="high",
            team="security",
        )

        poller.ticket_client.create_ticket.return_value = {
            "id": "test-ticket-id-456",
            "ticket_number": "SPS-2026-002",
        }

        email_data = _make_parsed_email()
        await poller._process_new_email(email_data)

        poller.ticket_client.request_ticket_reply.assert_not_awaited()
        poller.ticket_client.resolve_ticket_with_ai.assert_not_awaited()

    async def test_high_risk_ticket_skips_auto_reply(self):
        """A high-risk (but not critical) ticket should NOT trigger auto-reply."""
        poller = IMAPPoller()
        poller.ticket_client = AsyncMock()

        poller.ticket_client.classify_email.return_value = ClassifyResponse(
            category="identity_access",
            priority="medium",
            risk_level="high",
            team="security",
        )

        poller.ticket_client.create_ticket.return_value = {
            "id": "test-ticket-id-789",
            "ticket_number": "SPS-2026-003",
        }

        email_data = _make_parsed_email()
        await poller._process_new_email(email_data)

        poller.ticket_client.request_ticket_reply.assert_not_awaited()
        poller.ticket_client.resolve_ticket_with_ai.assert_not_awaited()

    async def test_auto_reply_failure_does_not_block_ticket_creation(self):
        """If the AI service is down, the ticket should still be created
        and left OPEN — the error should be logged, not raised."""
        poller = IMAPPoller()
        poller.ticket_client = AsyncMock()

        poller.ticket_client.classify_email.return_value = ClassifyResponse(
            category="general_it",
            priority="low",
            risk_level="standard",
            team="it",
        )

        poller.ticket_client.create_ticket.return_value = {
            "id": "test-ticket-id-101",
            "ticket_number": "SPS-2026-004",
        }

        poller.ticket_client.request_ticket_reply.side_effect = Exception(
            "AI service unreachable"
        )

        email_data = _make_parsed_email()
        await poller._process_new_email(email_data)

        poller.ticket_client.create_ticket.assert_awaited_once()
        poller.ticket_client.resolve_ticket_with_ai.assert_not_awaited()

    async def test_not_confident_does_not_resolve(self):
        """If the AI is not confident, the ticket should remain OPEN."""
        poller = IMAPPoller()
        poller.ticket_client = AsyncMock()

        poller.ticket_client.classify_email.return_value = ClassifyResponse(
            category="general_it",
            priority="medium",
            risk_level="standard",
            team="it",
        )

        poller.ticket_client.create_ticket.return_value = {
            "id": "test-ticket-id-202",
            "ticket_number": "SPS-2026-005",
        }

        poller.ticket_client.request_ticket_reply.return_value = {
            "answer": "",
            "sources": [],
            "confident": False,
            "escalate": True,
        }

        email_data = _make_parsed_email()
        await poller._process_new_email(email_data)

        poller.ticket_client.request_ticket_reply.assert_awaited_once()
        poller.ticket_client.resolve_ticket_with_ai.assert_not_awaited()