from __future__ import annotations

import warnings

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Core
    database_url: str = "" # Will be overridden by .env
    allowed_cors_origins: str = "*"

    # Auth - these have dev defaults but will warn if used
    secret_key: str = "dev-secret"
    admin_api_token: str = "dev-admin-token"

    @model_validator(mode="after")
    def _warn_insecure_defaults(self) -> "Settings":
        if self.secret_key == "dev-secret":
            warnings.warn(
                "SECRET_KEY is using insecure default 'dev-secret'. "
                "Set SECRET_KEY environment variable for production.",
                UserWarning,
                stacklevel=2,
            )
        if self.admin_api_token == "dev-admin-token":
            warnings.warn(
                "ADMIN_API_TOKEN is using insecure default 'dev-admin-token'. "
                "Set ADMIN_API_TOKEN environment variable for production.",
                UserWarning,
                stacklevel=2,
            )
        return self

    # LLM
    openai_api_key: str | None = None

    # Z.ai / Zhipu AI Settings
    zai_api_key: str = ""
    default_text_model: str = "glm-4-plus"
    default_vision_model: str = "glm-4.6v"

    # ImageKit Settings
    imagekit_private_key: str = ""
    imagekit_public_key: str = ""
    imagekit_url_endpoint: str = ""

    # Master Prompt
    master_prompt: str = (
        "You are a domain-restricted assistant. "
        "Only answer questions within the allowed domain. "
        "If the user asks outside the domain, say you can't help with that."
    )

    # Rate limiting
    rate_limit_session: str = "10/minute"  # Session creation
    rate_limit_chat: str = "20/minute"  # Chat requests
    rate_limit_chat_image: str = "5/minute"  # Image analysis (more expensive)


settings = Settings()
