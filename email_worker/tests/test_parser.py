"""Tests for the IMAP email parser module."""

import email.mime.multipart
import email.mime.text
from datetime import datetime

import pytest

from email_worker.imap.parser import parse_email, _decode_mime_header


def _build_raw_email(
    subject: str = "Test Subject",
    body: str = "Hello World",
    from_addr: str = "user@example.com",
    to_addr: str = "helpdesk@sps.com",
    message_id: str = "<abc123@example.com>",
    in_reply_to: str = "",
    html: bool = False,
) -> bytes:
    """Build a raw MIME email for testing."""
    msg = email.mime.multipart.MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg["Message-ID"] = message_id
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to

    msg.attach(email.mime.text.MIMEText(body, "html" if html else "plain", "utf-8"))
    return msg.as_bytes()


class TestParseEmail:
    """Test suite for parse_email function."""

    def test_parse_simple_text_email(self):
        """Test parsing a basic plain text email."""
        raw = _build_raw_email(
            subject="Help with VPN",
            body="I cannot connect to the VPN.",
            from_addr="john@example.com",
        )
        result = parse_email(raw)
        assert result is not None
        assert result.subject == "Help with VPN"
        assert result.from_address == "john@example.com"
        assert "I cannot connect to the VPN." in result.plain_text_body
        assert result.message_id == "<abc123@example.com>"

    def test_parse_with_in_reply_to(self):
        """Test parsing an email with In-Reply-To header."""
        raw = _build_raw_email(
            subject="Re: [SPS-2026-001] Test",
            body="This is a reply.",
            from_addr="john@example.com",
            in_reply_to="<original.msg@example.com>",
        )
        result = parse_email(raw)
        assert result is not None
        assert result.in_reply_to == "<original.msg@example.com>"

    def test_parse_html_email(self):
        """Test parsing an HTML email extracts HTML body."""
        raw = _build_raw_email(
            subject="HTML Email",
            body="<html><body><h1>Hello</h1></body></html>",
            from_addr="user@example.com",
            html=True,
        )
        result = parse_email(raw)
        assert result is not None
        assert "<h1>Hello</h1>" in result.html_body

    def test_parse_email_with_name_in_from(self):
        """Test that 'Name <email>' format is cleaned to just email."""
        raw = _build_raw_email(
            from_addr="John Doe <john.doe@example.com>",
        )
        result = parse_email(raw)
        assert result is not None
        assert result.from_address == "john.doe@example.com"

    def test_parse_empty_email_returns_none(self):
        """Test parsing empty bytes returns None."""
        result = parse_email(b"")
        assert result is None

    def test_parse_missing_from_returns_none(self):
        """Test an email without a From header returns None."""
        msg = email.mime.multipart.MIMEMultipart("alternative")
        msg["Subject"] = "No From"
        msg["To"] = "helpdesk@sps.com"
        msg["Message-ID"] = "<no-from@test.com>"
        msg.attach(email.mime.text.MIMEText("Body", "plain", "utf-8"))
        result = parse_email(msg.as_bytes())
        assert result is None

    def test_parse_subject_with_special_chars(self):
        """Test parsing subjects with special/encoded characters."""
        raw = _build_raw_email(
            subject="=?utf-8?B?w4ZydW5k?= subject",
            body="Body",
        )
        result = parse_email(raw)
        assert result is not None
        assert result.subject


class TestDecodeMimeHeader:
    """Tests for the _decode_mime_header helper."""

    def test_plain_text(self):
        """Test decoding a plain text header."""
        assert _decode_mime_header("Hello World") == "Hello World"

    def test_empty_string(self):
        """Test decoding an empty string."""
        assert _decode_mime_header("") == ""

    def test_encoded_subject(self):
        """Test decoding an encoded UTF-8 subject."""
        result = _decode_mime_header("=?utf-8?B?w4ZydW5k?=")
        assert len(result) > 0