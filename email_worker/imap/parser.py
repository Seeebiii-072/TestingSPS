"""Email parsing utilities for converting raw MIME email data into structured models."""

from __future__ import annotations

import email
import re
from email.message import Message
from email.header import decode_header
from typing import List, Optional

from email_worker.models.email_models import EmailAttachment, ParsedEmail
from email_worker.utils.logger import logger


def _decode_mime_header(value: str) -> str:
    """Decode a MIME encoded header value to plain text.

    Args:
        value: The raw header value, possibly MIME-encoded.

    Returns:
        Decoded UTF-8 string.
    """
    if not value:
        return ""
    decoded_parts = decode_header(value)
    result = []
    for part, charset in decoded_parts:
        if isinstance(part, bytes):
            try:
                result.append(
                    part.decode(charset or "utf-8", errors="replace")
                )
            except (LookupError, UnicodeDecodeError):
                result.append(part.decode("utf-8", errors="replace"))
        else:
            result.append(str(part))
    return " ".join(result)


def _get_body_from_message(msg: Message) -> tuple[str, str, list[EmailAttachment]]:
    """Extract plain text, HTML body, and attachments from an email message.

    Args:
        msg: The email.message.Message object.

    Returns:
        A tuple of (plain_text, html_text, attachments).
    """
    plain_text = ""
    html_text = ""
    attachments: List[EmailAttachment] = []

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(
                part.get("Content-Disposition", "")
            ).lower()

            # Skip attachments
            if "attachment" in content_disposition:
                filename = part.get_filename()
                if filename:
                    decoded_filename = _decode_mime_header(filename)
                    payload = part.get_payload(decode=True)
                    attachments.append(
                        EmailAttachment(
                            filename=decoded_filename,
                            content_type=content_type,
                            size=len(payload) if payload else 0,
                            content=payload,
                        )
                    )
                continue

            charset = part.get_content_charset() or "utf-8"
            payload = part.get_payload(decode=True)

            if payload is None:
                continue

            try:
                decoded = payload.decode(charset, errors="replace")
            except (LookupError, UnicodeDecodeError):
                decoded = payload.decode("utf-8", errors="replace")

            if content_type == "text/plain":
                plain_text += decoded
            elif content_type == "text/html":
                html_text += decoded
    else:
        # Single part message
        content_type = msg.get_content_type()
        charset = msg.get_content_charset() or "utf-8"
        payload = msg.get_payload(decode=True)
        if payload:
            try:
                decoded = payload.decode(charset, errors="replace")
            except (LookupError, UnicodeDecodeError):
                decoded = payload.decode("utf-8", errors="replace")

            if content_type == "text/plain":
                plain_text = decoded
            elif content_type == "text/html":
                html_text = decoded
            else:
                plain_text = decoded

    return plain_text.strip(), html_text.strip(), attachments


def parse_email(raw_email: bytes) -> Optional[ParsedEmail]:
    """Parse raw MIME email bytes into a structured ParsedEmail model.

    Args:
        raw_email: The raw email bytes as received from IMAP.

    Returns:
        A ParsedEmail instance if parsing succeeds, otherwise None.
    """
    if not raw_email:
        logger.warning("Attempted to parse empty email content")
        return None

    try:
        msg = email.message_from_bytes(raw_email)
    except Exception as e:
        logger.error("Failed to parse MIME email: %s", e)
        return None

    # Extract headers
    message_id = _decode_mime_header(msg.get("Message-ID", "")).strip()
    in_reply_to_raw = msg.get("In-Reply-To", "")
    in_reply_to = _decode_mime_header(in_reply_to_raw).strip() if in_reply_to_raw else None
    from_raw = msg.get("From", "")
    from_address = _decode_mime_header(from_raw).strip()
    to_raw = msg.get("To", "")
    to_address = _decode_mime_header(to_raw).strip() if to_raw else None
    subject = _decode_mime_header(msg.get("Subject", "")).strip()

    if not from_address:
        logger.warning("Email is missing 'From' header, skipping")
        return None

    # Extract body and attachments
    plain_text, html_text, attachments = _get_body_from_message(msg)

    # Clean up email address: sometimes it's "Name <email>" format
    email_match = re.search(r"<([^>]+)>", from_address)
    if email_match:
        from_address_clean = email_match.group(1)
    else:
        from_address_clean = from_address

    parsed = ParsedEmail(
        message_id=message_id,
        in_reply_to=in_reply_to,
        from_address=from_address_clean,
        to_address=to_address,
        subject=subject,
        plain_text_body=plain_text,
        html_body=html_text,
        attachments=attachments,
    )

    logger.debug(
        "Parsed email: msg_id=%s, from=%s, subject=%s, has_attachments=%s",
        message_id[:50] if message_id else "(none)",
        from_address_clean,
        subject[:50] if subject else "(empty)",
        len(attachments) > 0,
    )

    return parsed