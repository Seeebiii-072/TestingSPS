"""Thread resolver determines whether an incoming email is a new ticket or a reply.

Uses two methods in priority order:
1. Subject tag detection: [SPS-YYYY-NNN]
2. In-Reply-To header lookup via MessageStore
"""

from __future__ import annotations

import re
from typing import Optional, Tuple

from email_worker.models.email_models import ParsedEmail
from email_worker.storage.message_store import message_store
from email_worker.utils.logger import logger

# Regex to detect ticket tags in subjects: [SPS-2026-001]
TICKET_TAG_PATTERN = re.compile(r"\[SPS-(\d{4})-(\d{3,})\]")

ThreadType = str
ThreadResult = Tuple[ThreadType, Optional[str]]
# ("new", None) or ("reply", "SPS-2026-001")


def extract_ticket_tag(subject: str) -> Optional[str]:
    """Extract a ticket ID tag from a subject line.

    Args:
        subject: The email subject line.

    Returns:
        The ticket ID (e.g. SPS-2026-001) if found, otherwise None.
    """
    if not subject:
        return None
    match = TICKET_TAG_PATTERN.search(subject)
    if match:
        year = match.group(1)
        number = match.group(2)
        ticket_id = f"SPS-{year}-{number}"
        logger.debug("Extracted ticket tag from subject: %s", ticket_id)
        return ticket_id
    return None


def resolve_thread(email: ParsedEmail) -> ThreadResult:
    """Determine whether an email is a new ticket or a reply to an existing one.

    Priority order:
    1. Subject tag detection ([SPS-YYYY-NNN])
    2. In-Reply-To header lookup

    Args:
        email: The parsed inbound email.

    Returns:
        A tuple of (thread_type, ticket_id).
        thread_type is "new" or "reply".
        ticket_id is the resolved ticket ID or None for new threads.
    """
    # Method 1: Subject tag detection (highest priority)
    tag_ticket_id = extract_ticket_tag(email.subject)
    if tag_ticket_id:
        logger.info(
            "Resolved as reply via subject tag: %s -> %s",
            email.subject,
            tag_ticket_id,
        )
        return ("reply", tag_ticket_id)

    # Method 2: In-Reply-To header lookup
    if email.in_reply_to:
        # Try the exact In-Reply-To value
        ticket_id = message_store.lookup_message_id(email.in_reply_to)
        if ticket_id:
            logger.info(
                "Resolved as reply via In-Reply-To: %s -> %s",
                email.in_reply_to,
                ticket_id,
            )
            return ("reply", ticket_id)

        # Some clients strip angle brackets; try with and without
        stripped = email.in_reply_to.strip("<> ")
        if stripped != email.in_reply_to:
            ticket_id = message_store.lookup_message_id(stripped)
            if ticket_id:
                logger.info(
                    "Resolved as reply via In-Reply-To (stripped): %s -> %s",
                    stripped,
                    ticket_id,
                )
                return ("reply", ticket_id)

        # Also try with angle brackets added
        with_brackets = f"<{stripped}>"
        if with_brackets != email.in_reply_to:
            ticket_id = message_store.lookup_message_id(with_brackets)
            if ticket_id:
                logger.info(
                    "Resolved as reply via In-Reply-To (bracketed): %s -> %s",
                    with_brackets,
                    ticket_id,
                )
                return ("reply", ticket_id)

    # Neither method matched — this is a new ticket request
    logger.info(
        "No thread match found for email. Classifying as new: subject=%s",
        email.subject,
    )
    return ("new", None)