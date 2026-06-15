"""Persistent JSON-based storage for Message-ID to ticket ID mappings.

Stores every outbound and inbound Message-ID so that In-Reply-To headers
can be resolved to ticket IDs across service restarts.
"""

from __future__ import annotations

import json
import os
from threading import Lock
from typing import Dict, Optional

from email_worker.config.settings import settings
from email_worker.utils.logger import logger


class MessageStore:
    """Thread-safe JSON file store mapping Message-IDs to ticket IDs."""

    def __init__(self, file_path: Optional[str] = None) -> None:
        self._file_path = file_path or os.path.join(
            settings.message_store_path, "message_store.json"
        )
        self._lock = Lock()
        self._store: Dict[str, str] = {}
        self._ensure_directory()
        self._load()

    def _ensure_directory(self) -> None:
        """Create the data directory if it does not exist."""
        directory = os.path.dirname(self._file_path)
        if not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)

    def _load(self) -> None:
        """Load mappings from the JSON file on disk."""
        if not os.path.exists(self._file_path):
            logger.info(
                "Message store file not found, starting fresh: %s",
                self._file_path,
            )
            self._store = {}
            return
        try:
            with open(self._file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._store = data if isinstance(data, dict) else {}
            logger.info(
                "Loaded %d message-ID mappings from %s",
                len(self._store),
                self._file_path,
            )
        except (json.JSONDecodeError, OSError) as e:
            logger.error(
                "Failed to load message store (corrupted?): %s. Starting fresh.",
                e,
            )
            self._store = {}

    def _save(self) -> None:
        """Persist the in-memory store to the JSON file."""
        try:
            with open(self._file_path, "w", encoding="utf-8") as f:
                json.dump(self._store, f, indent=2, ensure_ascii=False)
            logger.debug("Message store saved (%d entries)", len(self._store))
        except OSError as e:
            logger.error("Failed to write message store: %s", e)

    def save_message_mapping(
        self, message_id: str, ticket_id: str
    ) -> None:
        """Persist a Message-ID to ticket ID mapping.

        Args:
            message_id: The email Message-ID header value.
            ticket_id: The associated ticket ID (e.g. SPS-2026-001).
        """
        if not message_id or not ticket_id:
            logger.warning(
                "Skipping empty mapping: message_id=%s ticket_id=%s",
                message_id,
                ticket_id,
            )
            return
        with self._lock:
            self._store[message_id] = ticket_id
            self._save()
        logger.debug(
            "Stored mapping: %s -> %s", message_id, ticket_id
        )

    def lookup_message_id(self, message_id: str) -> Optional[str]:
        """Look up a ticket ID by Message-ID.

        Args:
            message_id: The email Message-ID header value.

        Returns:
            The associated ticket ID if found, otherwise None.
        """
        with self._lock:
            return self._store.get(message_id)

    def delete_mapping(self, message_id: str) -> None:
        """Remove a Message-ID mapping from the store.

        Args:
            message_id: The email Message-ID to remove.
        """
        with self._lock:
            if message_id in self._store:
                del self._store[message_id]
                self._save()

    @property
    def count(self) -> int:
        """Return the number of stored mappings."""
        with self._lock:
            return len(self._store)


# Singleton instance for application-wide use
message_store = MessageStore()