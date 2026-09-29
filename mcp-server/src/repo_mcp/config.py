# generated-by: generate-mcp source_hash=a333806c00d6
"""Environment-based configuration. Values come from the process environment only."""
from __future__ import annotations

from functools import lru_cache
from urllib.parse import urlparse

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    target_api_base_url: str = Field(alias="TARGET_API_BASE_URL")
    target_api_token: SecretStr | None = Field(default=None, alias="TARGET_API_TOKEN")
    target_api_timeout_seconds: float = Field(default=15.0, alias="TARGET_API_TIMEOUT_SECONDS", gt=0, le=300)
    max_response_bytes: int = Field(default=262_144, alias="MAX_RESPONSE_BYTES", gt=0)

    @field_validator("target_api_base_url")
    @classmethod
    def _http_only(cls, v: str) -> str:
        u = urlparse(v)
        if u.scheme not in {"http", "https"} or not u.netloc:
            raise ValueError("TARGET_API_BASE_URL must be an http or https URL")
        return v.rstrip("/")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
