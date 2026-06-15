"""Tests for SOC routing logic and duplicate detection."""

import pytest

from email_worker.imap.poller import _soc_routing_rule
from email_worker.models.event_models import ClassifyResponse
from email_worker.storage.message_store import MessageStore


class TestSOCRoutingDetailed:
    """Comprehensive SOC routing tests."""

    def test_cybersecurity_critical_security(self):
        """Cybersecurity + critical = security team."""
        classify = ClassifyResponse(
            category="cybersecurity",
            priority="critical",
            team="it-support",
        )
        team = _soc_routing_rule(classify)
        assert team == "security"

    def test_cybersecurity_high_not_security(self):
        """Cybersecurity + high (not critical) should not override."""
        classify = ClassifyResponse(
            category="cybersecurity",
            priority="high",
            team="it-support",
        )
        team = _soc_routing_rule(classify)
        assert team == "it-support"

    def test_networking_critical_no_override(self):
        """Networking + critical does NOT trigger SOC rule."""
        classify = ClassifyResponse(
            category="networking",
            priority="critical",
            team="network-team",
        )
        team = _soc_routing_rule(classify)
        assert team == "network-team"

    def test_security_critical_override(self):
        """capitalization: Cybersecurity + Critical still triggers."""
        classify = ClassifyResponse(
            category="Cybersecurity",
            priority="Critical",
            team="infrastructure",
        )
        team = _soc_routing_rule(classify)
        assert team == "security"

    def test_normal_ticket_no_override(self):
        """Normal ticket keeps its assigned team."""
        classify = ClassifyResponse(
            category="hardware",
            priority="low",
            team="hardware-team",
        )
        team = _soc_routing_rule(classify)
        assert team == "hardware-team"

    def test_empty_category_no_override(self):
        """Empty category with critical should not override."""
        classify = ClassifyResponse(
            category="",
            priority="critical",
            team="default-team",
        )
        team = _soc_routing_rule(classify)
        assert team == "default-team"


class TestDuplicateDetection:
    """Tests for duplicate email processing prevention."""

    def test_in_memory_uid_dedup(self):
        """Test that the in-memory UID tracking prevents duplicates."""
        from email_worker.imap.poller import IMAPPoller

        poller = IMAPPoller()
        assert "uid-1" not in poller._processed_uids

        poller._processed_uids.add("uid-1")
        assert "uid-1" in poller._processed_uids

        # Simulate checking for duplicates
        uids = ["uid-1", "uid-2", "uid-3"]
        new_uids = [uid for uid in uids if uid not in poller._processed_uids]
        assert "uid-1" not in new_uids
        assert len(new_uids) == 2

    def test_store_dedup_via_message_id(self):
        """Test that the message store helps prevent duplicate processing."""
        store = MessageStore()
        # Two different emails with the same Message-ID
        store.save_message_mapping("<dup@example.com>", "SPS-2026-001")

        # Looking up should find it
        result = store.lookup_message_id("<dup@example.com>")
        assert result == "SPS-2026-001"

        # A different Message-ID should not be found
        result2 = store.lookup_message_id("<different@example.com>")
        assert result2 is None

        store.delete_mapping("<dup@example.com>")