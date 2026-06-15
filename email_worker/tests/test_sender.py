"""Tests for the SMTP email sender module."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from email_worker.smtp.sender import EmailSender


class TestEmailSender:
    """Tests for the EmailSender class (mocked SMTP)."""

    @pytest.fixture
    def sender(self) -> EmailSender:
        """Create an EmailSender with _render_template stubbed."""
        s = EmailSender()
        s._render_template = lambda template_name, data: "<html>Test</html>"  # type: ignore[method-assign]
        return s

    @pytest.mark.asyncio
    async def test_send_ack_email_basic(self, sender: EmailSender):
        """Test that send_ack_email builds and sends correctly."""
        with patch.object(sender, "_send_smtp", new_callable=AsyncMock) as mock_send:
            mid = await sender.send_ack_email(
                to_email="user@example.com",
                ticket_id="SPS-2026-001",
                subject="VPN Issue",
                requester_name="John",
            )
            assert mid is not None
            assert "SPS" in mid
            mock_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_agent_reply_email(self, sender: EmailSender):
        """Test that send_agent_reply_email works."""
        with patch.object(sender, "_send_smtp", new_callable=AsyncMock) as mock_send:
            mid = await sender.send_agent_reply_email(
                to_email="user@example.com",
                ticket_id="SPS-2026-001",
                original_subject="VPN Issue",
                agent_name="Agent Smith",
                reply_content="We fixed it.",
            )
            assert mid is not None
            mock_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_status_change_email(self, sender: EmailSender):
        """Test that send_status_change_email works."""
        with patch.object(sender, "_send_smtp", new_callable=AsyncMock) as mock_send:
            mid = await sender.send_status_change_email(
                to_email="user@example.com",
                ticket_id="SPS-2026-001",
                subject="VPN Issue",
                new_status="Resolved",
            )
            assert mid is not None
            mock_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_approval_request(self, sender: EmailSender):
        """Test that send_approval_request_email works."""
        with patch.object(sender, "_send_smtp", new_callable=AsyncMock) as mock_send:
            mid = await sender.send_approval_request_email(
                to_email="approver@example.com",
                ticket_id="SPS-2026-001",
                subject="Access Request",
                requester_name="John",
            )
            assert mid is not None
            mock_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_message_id_format(self, sender: EmailSender):
        """Test Message-ID generation format."""
        mid = sender._generate_message_id(ticket_id="SPS-2026-001")
        assert mid.startswith("<")
        assert mid.endswith(">")
        assert "SPS-2026-001" in mid
        assert "@" in mid

    @pytest.mark.asyncio
    async def test_send_email_with_stored_mapping(self, sender: EmailSender):
        """Test that send_email stores the Message-ID mapping."""
        from email_worker.storage.message_store import message_store

        with patch.object(sender, "_send_smtp", new_callable=AsyncMock):
            mid = await sender.send_email(
                to_email="user@example.com",
                subject="Test",
                html_body="<html></html>",
                plain_text_body="Test",
                ticket_id="SPS-2026-005",
            )
            # Verify the mapping was stored
            result = message_store.lookup_message_id(mid)
            assert result == "SPS-2026-005"
            # Clean up
            message_store.delete_mapping(mid)