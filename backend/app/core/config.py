"""Runtime configuration loaded from environment variables (see `.env.example`)."""

from __future__ import annotations

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    app_name: str = "TrustShield AI"
    environment: str = "development"

    # Database
    database_url: str = "postgresql://trustshield:trustshield@localhost:5432/trustshield"

    # Auth
    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 30
    refresh_token_days: int = 7
    jwt_issuer: str = "trustshield"
    jwt_audience: str = "trustshield-app"
    # Session cookies. `cookie_secure` defaults to True in production; set COOKIE_SECURE=true behind HTTPS elsewhere.
    cookie_secure: bool | None = None
    cookie_samesite: str = "lax"
    demo_user_password: str = "TrustShield-demo-2024"

    # LLM
    llm_provider: str = "mock"
    openai_api_key: str = ""
    openai_base_url: str = ""
    openai_model: str = "gpt-4o-mini"
    azure_openai_api_version: str = "2024-06-01"
    llm_timeout_seconds: float = 30.0

    # Embeddings / retrieval
    embedding_provider: str = "local"
    embedding_model: str = "text-embedding-3-small"
    retrieval_top_k: int = 5

    # Guardrails
    presidio_enabled: bool = True
    spacy_model: str = "en_core_web_sm"

    # Slack (optional). With these unset the built-in connected workspace still works.
    slack_enabled: bool = False
    slack_bot_token: str = ""
    slack_signing_secret: str = ""
    slack_app_token: str = ""
    slack_verification_token: str = ""
    slack_workspace_name: str = ""
    workspace_rate_limit_per_minute: int = 20
    public_app_url: str = "http://localhost:3000"

    # Background scheduler (compliance report schedules)
    scheduler_enabled: bool = True
    scheduler_interval_seconds: int = 60

    # HTTP
    cors_origins: str = "http://localhost:3000"

    @field_validator("database_url")
    @classmethod
    def _normalise_driver(cls, value: str) -> str:
        # Accept the conventional postgresql:// URL and use the psycopg3 driver.
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+psycopg://", 1)
        if value.startswith("postgres://"):
            return value.replace("postgres://", "postgresql+psycopg://", 1)
        return value

    @property
    def effective_llm_provider(self) -> str:
        """Fall back to the offline mock when a remote provider has no key."""
        if self.llm_provider in {"openai", "azure"} and not self.openai_api_key:
            return "mock"
        return self.llm_provider

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
