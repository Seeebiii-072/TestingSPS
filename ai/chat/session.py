import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from threading import RLock

from ai.config.settings import get_settings
from ai.schemas.chat import ChatMessage


MAX_SESSION_MESSAGES = 50
CONTEXT_MESSAGE_LIMIT = 6


class SessionOwnershipError(PermissionError):
    """Raised when a session belongs to a different user."""


def normalize_question(message: str) -> str:
    normalized = re.sub(r"[^\w\s]", " ", message.casefold())
    return " ".join(normalized.split())


@dataclass
class ChatSession:
    session_id: str
    user_id: str
    messages: list[ChatMessage] = field(default_factory=list)
    question_counts: Counter[str] = field(default_factory=Counter)
    lock: RLock = field(default_factory=RLock, repr=False)
    last_activity: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def add_message(self, role: str, content: str) -> None:
        now = datetime.now(timezone.utc)
        self.messages.append(ChatMessage(role=role, content=content, created_at=now))
        if role == "user":
            self.question_counts[normalize_question(content)] += 1
        while len(self.messages) > MAX_SESSION_MESSAGES:
            removed = self.messages.pop(0)
            if removed.role == "user":
                normalized = normalize_question(removed.content)
                self.question_counts[normalized] -= 1
                if self.question_counts[normalized] <= 0:
                    del self.question_counts[normalized]
        self.last_activity = now

    def repeated_question_count(self, message: str) -> int:
        return self.question_counts[normalize_question(message)]

    def short_context(self, *, exclude_latest_user: bool = False) -> str:
        messages = self.messages
        if exclude_latest_user and messages and messages[-1].role == "user":
            messages = messages[:-1]
        return "\n".join(
            f"{message.role.title()}: {message.content}"
            for message in messages[-CONTEXT_MESSAGE_LIMIT:]
        )

    def is_expired(self) -> bool:
        timeout = timedelta(
            seconds=get_settings().chat_session_timeout_seconds
        )
        return datetime.now(timezone.utc) - self.last_activity > timeout


class SessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, ChatSession] = {}
        self._lock = RLock()

    def get_or_create(self, session_id: str, user_id: str) -> ChatSession:
        with self._lock:
            self._remove_expired_locked()
            session = self._sessions.get(session_id)
            if session is None:
                session = ChatSession(session_id=session_id, user_id=user_id)
                self._sessions[session_id] = session
            elif session.user_id != user_id:
                raise SessionOwnershipError(
                    "This chat session belongs to a different user."
                )
            return session

    def clear(self) -> None:
        with self._lock:
            self._sessions.clear()

    def _remove_expired_locked(self) -> None:
        expired_ids = [
            session_id
            for session_id, session in self._sessions.items()
            if session.is_expired()
        ]
        for session_id in expired_ids:
            del self._sessions[session_id]


session_store = SessionStore()
