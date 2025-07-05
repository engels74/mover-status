"""Base configuration models and common types."""

from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel, Field, ConfigDict


class BaseConfig(BaseModel):
    """Base configuration model with common settings."""

    model_config: ConfigDict = ConfigDict(  # pyright: ignore[reportIncompatibleVariableOverride]
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
        frozen=False,
    )


class RetryConfig(BaseConfig):
    """Configuration for retry behavior."""

    max_attempts: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum number of retry attempts",
    )
    backoff_factor: float = Field(
        default=2.0,
        ge=0.0,
        le=10.0,
        description="Backoff factor for exponential backoff",
    )
    timeout: int = Field(
        default=30,
        ge=1,
        le=300,
        description="Timeout in seconds for each attempt",
    )


class RateLimitConfig(BaseConfig):
    """Configuration for rate limiting."""

    progress: int = Field(
        default=300,
        ge=0,
        le=3600,
        description="Seconds between progress notifications",
    )
    status: int = Field(
        default=60,
        ge=0,
        le=3600,
        description="Seconds between status notifications",
    )


class ConfigurableProvider(ABC):
    """Abstract base class for configurable providers."""

    @abstractmethod
    def validate_config(self, config: dict[str, object]) -> bool:
        """Validate provider-specific configuration."""
        pass

    @abstractmethod
    def get_config_schema(self) -> dict[str, object]:
        """Get JSON schema for provider configuration."""
        pass


class LogLevel(BaseConfig):
    """Valid log levels."""

    CRITICAL: str = "CRITICAL"
    ERROR: str = "ERROR"
    WARNING: str = "WARNING"
    INFO: str = "INFO"
    DEBUG: str = "DEBUG"


class NotificationEvent(BaseConfig):
    """Valid notification events."""

    STARTED: str = "started"
    PROGRESS: str = "progress"
    COMPLETED: str = "completed"
    FAILED: str = "failed"


class ProviderName(BaseConfig):
    """Valid provider names."""

    TELEGRAM: str = "telegram"
    DISCORD: str = "discord"