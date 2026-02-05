from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Core
    database_url: str = "sqlite+aiosqlite:///./app.db"
    allowed_cors_origins: str = "*"

    # Auth (optional)
    secret_key: str = "dev-secret"
    admin_api_token: str = "dev-admin-token"

    # LLM
    openai_api_key: str | None = None
    master_prompt: str = (
        "You are a domain-restricted assistant. "
        "Only answer questions within the allowed domain. "
        "If the user asks outside the domain, say you can't help with that."
    )

    # Defaults
    default_text_model: str = "gpt-4o-mini"
    default_vision_model: str = "gpt-4o-mini"


settings = Settings()

