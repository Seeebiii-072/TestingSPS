"""Tests for the JSON-based message store persistence."""

import json
import os
import tempfile

import pytest

from email_worker.storage.message_store import MessageStore


class TestMessageStore:
    """Tests for the MessageStore class."""

    @pytest.fixture
    def store(self, tmp_path):
        """Create a MessageStore with a temp file path."""
        file_path = os.path.join(tmp_path, "test_store.json")
        s = MessageStore(file_path=file_path)
        yield s
        # Clean up
        if os.path.exists(file_path):
            os.remove(file_path)

    def test_save_and_lookup(self, store: MessageStore):
        """Test saving a mapping and looking it up."""
        store.save_message_mapping("<msg1@example.com>", "SPS-2026-001")
        result = store.lookup_message_id("<msg1@example.com>")
        assert result == "SPS-2026-001"

    def test_lookup_non_existent(self, store: MessageStore):
        """Test looking up a non-existent Message-ID returns None."""
        result = store.lookup_message_id("<nonexistent@example.com>")
        assert result is None

    def test_delete_mapping(self, store: MessageStore):
        """Test deleting a mapping."""
        store.save_message_mapping("<to-delete@example.com>", "SPS-2026-002")
        store.delete_mapping("<to-delete@example.com>")
        result = store.lookup_message_id("<to-delete@example.com>")
        assert result is None

    def test_empty_message_id(self, store: MessageStore):
        """Test saving with an empty message ID does nothing."""
        store.save_message_mapping("", "SPS-2026-003")
        assert store.count == 0

    def test_empty_ticket_id(self, store: MessageStore):
        """Test saving with an empty ticket ID does nothing."""
        store.save_message_mapping("<msg@example.com>", "")
        assert store.count == 0

    def test_persistence_across_instances(self, tmp_path):
        """Test mappings persist across different store instances (same file)."""
        file_path = os.path.join(tmp_path, "persist_test.json")

        store1 = MessageStore(file_path=file_path)
        store1.save_message_mapping("<persist@example.com>", "SPS-2026-100")
        assert store1.count == 1

        store2 = MessageStore(file_path=file_path)
        result = store2.lookup_message_id("<persist@example.com>")
        assert result == "SPS-2026-100"

        os.remove(file_path)

    def test_corrupted_file_handling(self, tmp_path):
        """Test handling of a corrupted JSON file."""
        file_path = os.path.join(tmp_path, "corrupted.json")
        with open(file_path, "w") as f:
            f.write("this is not valid json")

        store = MessageStore(file_path=file_path)
        # Should start with an empty store rather than crashing
        assert store.count == 0

        os.remove(file_path)

    def test_multiple_mappings(self, store: MessageStore):
        """Test storing and retrieving multiple mappings."""
        mappings = {
            "<a@example.com>": "SPS-2026-001",
            "<b@example.com>": "SPS-2026-002",
            "<c@example.com>": "SPS-2026-003",
        }
        for msg_id, ticket_id in mappings.items():
            store.save_message_mapping(msg_id, ticket_id)

        assert store.count == 3

        for msg_id, expected_ticket in mappings.items():
            assert store.lookup_message_id(msg_id) == expected_ticket