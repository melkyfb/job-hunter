# backend/app/core/config.py
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
    llm_provider: LLMProvider = Field(default=LLMProvider.LOCAL)

    # ── OpenAI ────────────────────────────────────────────────────────────────
    openai_api_key: Optional[str] = Field(default=None)
    openai_model: str = Field(default="gpt-4o-mini")

    # ── Local / OpenAI-compatible ─────────────────────────────────────────────
    local_base_url: str = Field(default="http://localhost:11434/v1")
    local_api_key: str = Field(default="ollama")
    local_model: str = Field(default="llama3.2")

    # ── Job Search ────────────────────────────────────────────────────────────
    search_provider: str = Field(default="mock")
    adzuna_app_id: Optional[str] = Field(default=None)
    adzuna_api_key: Optional[str] = Field(default=None)
    adzuna_country: str = Field(default="de")

    # ── Search cache ──────────────────────────────────────────────────────────
    search_cache_ttl_hours: int = Field(default=2, ge=0)

    # ── Shared parameters ─────────────────────────────────────────────────────
    llm_temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    llm_max_retries: int = Field(default=3, ge=1, le=10)

    # ── Output language (set via POST /config/update from frontend) ───────────
    cv_language: str = Field(default="English")
    cl_language: str = Field(default="English")

    # ── Prompt overrides (None = use prompt_defaults module values) ────────────
    cv_prompt_override: Optional[str] = Field(default=None)
    cl_prompt_override: Optional[str] = Field(default=None)

    # ── Validation ────────────────────────────────────────────────────────────
    @model_validator(mode="after")
    def require_api_key_for_openai(self) -> Settings:
        if self.llm_provider == LLMProvider.OPENAI and not self.openai_api_key:
            # In Tauri mode config comes via POST /config/update — skip .env validation
            pass
        return self

    # ── Convenience properties ────────────────────────────────────────────────
    @property
    def active_model(self) -> str:
        return (
            self.openai_model
            if self.llm_provider == LLMProvider.OPENAI
            else self.local_model
        )

    @property
    def active_base_url(self) -> Optional[str]:
        return None if self.llm_provider == LLMProvider.OPENAI else self.local_base_url

    @property
    def active_api_key(self) -> str:
        return (
            self.openai_api_key or ""
            if self.llm_provider == LLMProvider.OPENAI
            else self.local_api_key
        )

    # ── Runtime mutation (called by POST /config/update) ─────────────────────
    def update_from_config(
        self,
        *,
        llm_provider: str,
        llm_model: str,
        llm_api_key: Optional[str],
        llm_base_url: Optional[str],
        llm_temperature: float,
        adzuna_app_id: Optional[str],
        adzuna_api_key: Optional[str],
        adzuna_country: str,
        search_provider: str,
        cv_prompt: Optional[str],
        cl_prompt: Optional[str],
        cv_language: str,
        cl_language: str,
    ) -> None:
        provider = LLMProvider(llm_provider)
        self.llm_provider = provider
        if provider == LLMProvider.OPENAI:
            if llm_api_key:
                self.openai_api_key = llm_api_key
            if llm_model:
                self.openai_model = llm_model
        else:
            self.local_model = llm_model or self.local_model
            self.local_base_url = llm_base_url or self.local_base_url
            self.local_api_key = llm_api_key or self.local_api_key
        self.llm_temperature = llm_temperature
        self.adzuna_app_id = adzuna_app_id or self.adzuna_app_id
        self.adzuna_api_key = adzuna_api_key or self.adzuna_api_key
        self.adzuna_country = adzuna_country or self.adzuna_country
        self.search_provider = search_provider
        self.cv_prompt_override = cv_prompt or None
        self.cl_prompt_override = cl_prompt or None
        self.cv_language = cv_language or "English"
        self.cl_language = cl_language or "English"


settings = Settings()
