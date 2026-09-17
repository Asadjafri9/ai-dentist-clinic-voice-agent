"""Application configuration loaded from environment variables.

Startup fails fast when required production configuration is missing.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_env: Literal["development", "staging", "production"] = "development"
    api_base_url: str = "http://localhost:8000"
    frontend_origins: str = "http://localhost:3000"

    mongodb_uri: str = ""
    mongodb_database: str = "ai_dentist_voice_agent"

    auth_cookie_name: str = "ai_voice_session"
    auth_session_ttl_hours: int = 24
    auth_csrf_secret: str = ""
    auth_cookie_secure: bool = True

    vapi_api_key: str = ""
    vapi_server_credential_mode: Literal["hmac", "bearer"] = "hmac"
    vapi_server_credential_secret: str = ""
    vapi_server_credential_header: str = "x-signature"
    vapi_server_timestamp_header: str = "x-timestamp"
    vapi_bearer_header: str = "authorization"
    vapi_max_replay_skew_seconds: int = 300
    vapi_tool_timeout_seconds: float = 4.0
    vapi_api_base: str = "https://api.vapi.ai"

    offer_token_secret: str = ""
    offer_token_ttl_seconds: int = 300
    booking_horizon_days: int = 90
    slot_increment_minutes: int = 30

    transcript_retention_days: int = 30
    log_level: str = "INFO"

    seed_admin_email: str = "admin@brightsmile.test"
    seed_admin_password: str = ""

    worker_poll_seconds: float = 1.0
    worker_lease_seconds: int = 60
    worker_max_attempts: int = 5

    @field_validator("frontend_origins")
    @classmethod
    def _no_trailing_space(cls, v: str) -> str:
        return v.strip()

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def frontend_origin_list(self) -> list[str]:
        return [o.strip() for o in self.frontend_origins.split(",") if o.strip()]

    def validate_required(self) -> list[str]:
        """Return a list of missing required settings for the current env."""
        missing: list[str] = []
        if not self.mongodb_uri:
            missing.append("MONGODB_URI")
        if self.is_production:
            if not self.auth_csrf_secret:
                missing.append("AUTH_CSRF_SECRET")
            if not self.offer_token_secret:
                missing.append("OFFER_TOKEN_SECRET")
            if not self.vapi_server_credential_secret:
                missing.append("VAPI_SERVER_CREDENTIAL_SECRET")
        return missing


@lru_cache
def get_settings() -> Settings:
    settings = Settings()  # type: ignore[call-arg]
    missing = settings.validate_required()
    if missing:
        raise RuntimeError(
            f"Missing required configuration: {', '.join(missing)} "
            f"(APP_ENV={os.environ.get('APP_ENV', 'development')})"
        )
    return settings
