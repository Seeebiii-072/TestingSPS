"""Application configuration loaded from environment variables."""

import os
from dataclasses import dataclass, field
from typing import Optional

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    """Immutable application settings populated from environment variables."""

    # IMAP
    imap_host: str = field(default_factory=lambda: os.getenv("IMAP_HOST", ""))
    imap_port: int = int(os.getenv("IMAP_PORT", "993"))
    imap_user: str = field(default_factory=lambda: os.getenv("IMAP_USER", ""))
    imap_password: str = field(
        default_factory=lambda: os.getenv("IMAP_PASSWORD", "")
    )
    imap_poll_interval_seconds: int = int(
        os.getenv("IMAP_POLL_INTERVAL_SECONDS", "30")
    )

    # SMTP
    smtp_host: str = field(
        default_factory=lambda: os.getenv("SMTP_HOST", "localhost")
    )
    smtp_port: int = int(os.getenv("SMTP_PORT", "1025"))
    smtp_user: str = field(default_factory=lambda: os.getenv("SMTP_USER", ""))
    smtp_password: str = field(
        default_factory=lambda: os.getenv("SMTP_PASSWORD", "")
    )
    email_from_address: str = field(
        default_factory=lambda: os.getenv(
            "EMAIL_FROM_ADDRESS", "helpdesk@sps.com"
        )
    )
    email_from_name: str = field(
        default_factory=lambda: os.getenv(
            "EMAIL_FROM_NAME", "SPS Helpdesk"
        )
    )

    # API
    backend_api_url: str = field(
        default_factory=lambda: os.getenv(
            "BACKEND_API_URL", "http://localhost:8000"
        )
    )
    portal_url: str = field(
        default_factory=lambda: os.getenv(
            "PORTAL_URL", "http://localhost:5173"
        )
    )

    # Internal
    message_store_path: str = field(
        default_factory=lambda: os.getenv(
            "MESSAGE_STORE_PATH",
            os.path.join(
                os.path.dirname(os.path.dirname(__file__)), "data"
            ),
        )
    )

    @property
    def is_mailhog(self) -> bool:
        """Detect if we are using Mailhog (localhost:1025 with no auth)."""
        return (
            self.smtp_host == "localhost"
            and self.smtp_port == 1025
            and not self.smtp_user
        )


settings = Settings()