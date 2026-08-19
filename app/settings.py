"""Typed application settings loaded from the environment."""

from enum import StrEnum
from functools import lru_cache
from typing import Self

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(StrEnum):
    """Supported runtime environments."""

    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"


class Settings(BaseSettings):
    """Validated settings with secret-safe representations."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="FINRAG_",
        env_ignore_empty=True,
        case_sensitive=False,
        extra="ignore",
        frozen=True,
        hide_input_in_errors=True,
    )

    app_name: str = "FinRAG Agent Platform"
    environment: Environment = Environment.DEVELOPMENT
    database_url: SecretStr | None = None
    api_key: SecretStr | None = None
    readiness_timeout_seconds: float = Field(default=2.0, gt=0, le=2.0)

    @model_validator(mode="after")
    def require_production_secrets(self) -> Self:
        """Reject production startup when required secrets are absent."""

        if self.environment is not Environment.PRODUCTION:
            return self

        missing_fields = [
            field_name
            for field_name in ("api_key", "database_url")
            if getattr(self, field_name) is None
        ]
        if missing_fields:
            missing = ", ".join(missing_fields)
            raise ValueError(f"Production configuration requires: {missing}")

        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load and cache one immutable settings instance per process."""

    return Settings()
