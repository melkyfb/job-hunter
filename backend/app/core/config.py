from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMProvider(str, Enum):
    OPENAI = "openai"
    LOCAL = "local"  # Any OpenAI-compatible endpoint (Ollama, LM Studio, vLLM, …)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Provider ──────────────────────────────────────────────────────────────
    llm_provider: LLMProvider = Field(
        default=LLMProvider.LOCAL,
        description="'openai' uses the official API. 'local' uses any OpenAI-compatible server.",
    )

    # ── OpenAI ────────────────────────────────────────────────────────────────
    openai_api_key: Optional[str] = Field(default=None)
    openai_model: str = Field(default="gpt-4o-mini")

    # ── Local / OpenAI-compatible (Ollama, LM Studio, vLLM, any third-party) ─
    local_base_url: str = Field(
        default="http://localhost:11434/v1",
        description=(
            "Base URL of any OpenAI-compatible server.\n"
            "  Ollama default  : http://localhost:11434/v1\n"
            "  LM Studio       : http://localhost:1234/v1\n"
            "  vLLM            : http://localhost:8080/v1\n"
            "  Remote server   : https://my-llm.example.com/v1"
        ),
    )
    local_api_key: str = Field(
        default="ollama",
        description="Most local servers accept any non-empty string.",
    )
    local_model: str = Field(
        default="llama3.2",
        description="Model name as listed by the local server (e.g. 'llama3.2', 'mistral', 'phi-4').",
    )

    # ── Job Search ────────────────────────────────────────────────────────────
    search_provider: str = Field(
        default="mock",
        description="'adzuna' for real jobs, 'mock' for development without API keys.",
    )
    adzuna_app_id: Optional[str] = Field(default=None)
    adzuna_api_key: Optional[str] = Field(default=None)
    adzuna_country: str = Field(default="de", description="ISO country code: de, gb, us…")

    # ── Search cache ──────────────────────────────────────────────────────────
    search_cache_ttl_hours: int = Field(
        default=2,
        ge=0,
        description="How long (hours) to cache job search results. Set 0 to disable.",
    )

    # ── Shared parameters ─────────────────────────────────────────────────────
    llm_temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    llm_max_retries: int = Field(default=3, ge=1, le=10)

    # ── Validation ────────────────────────────────────────────────────────────
    @model_validator(mode="after")
    def require_api_key_for_openai(self) -> Settings:
        if self.llm_provider == LLMProvider.OPENAI and not self.openai_api_key:
            raise ValueError(
                "LLM_PROVIDER=openai requires OPENAI_API_KEY. "
                "Add it to your .env file or set the environment variable."
            )
        return self

    # ── Convenience properties (used by llm.py and ingestion.py) ─────────────
    @property
    def active_model(self) -> str:
        return (
            self.openai_model
            if self.llm_provider == LLMProvider.OPENAI
            else self.local_model
        )

    @property
    def active_base_url(self) -> Optional[str]:
        """None → SDK uses api.openai.com. Set → any compatible endpoint."""
        return (
            None
            if self.llm_provider == LLMProvider.OPENAI
            else self.local_base_url
        )

    @property
    def active_api_key(self) -> str:
        return (
            self.openai_api_key  # type: ignore[return-value]
            if self.llm_provider == LLMProvider.OPENAI
            else self.local_api_key
        )


settings = Settings()
