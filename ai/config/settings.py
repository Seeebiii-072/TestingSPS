from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


AI_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=AI_ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    service_name: str = "SPS SecureDesk AI"
    service_port: int = Field(default=8001, ge=1, le=65535)
    backend_api_url: str = "http://backend:8000"

    llm_provider: str = "anthropic"

    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-4-20250514"

    openrouter_api_key: str | None = None
    openrouter_model: str = "openrouter/auto"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    groq_api_key: str | None = None
    groq_model: str = "llama-3.3-70b-versatile"

    kb_store_path: Path = Path("./ai/kb/chroma_store")
    max_kb_results: int = Field(default=5, ge=3, le=5)
    kb_chunk_size: int = Field(default=800, ge=100)
    kb_chunk_overlap: int = Field(default=150, ge=0)
    kb_min_similarity_score: float = Field(default=0.35, ge=0.0, le=1.0)
    chat_session_timeout_seconds: int = Field(default=3600, ge=60)
    llm_timeout_seconds: float = Field(default=60.0, gt=0)

    @field_validator("llm_provider")
    @classmethod
    def validate_llm_provider(cls, value: str) -> str:
        provider = value.strip().lower()
        allowed = {"anthropic", "openrouter", "groq"}
        if provider not in allowed:
            raise ValueError(
                f"LLM_PROVIDER must be one of: {', '.join(sorted(allowed))}"
            )
        return provider

    @field_validator("kb_chunk_overlap")
    @classmethod
    def validate_chunk_overlap(cls, value: int, info) -> int:
        chunk_size = info.data.get("kb_chunk_size", 800)
        if value >= chunk_size:
            raise ValueError("KB_CHUNK_OVERLAP must be smaller than KB_CHUNK_SIZE")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()