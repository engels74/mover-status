"""Monitoring configuration models."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator

from .base import BaseConfig


class MonitoringConfig(BaseConfig):
    """Configuration for monitoring behavior."""

    interval: int = Field(
        default=60,
        ge=1,
        le=3600,
        description="Interval between checks in seconds",
    )
    detection_timeout: int = Field(
        default=300,
        ge=1,
        le=3600,
        description="Maximum time to wait for process detection in seconds",
    )
    dry_run: bool = Field(
        default=False,
        description="Enable dry run mode (no actual notifications)",
    )


class ProcessConfig(BaseConfig):
    """Configuration for process detection."""

    name: str = Field(
        min_length=1,
        description="Name of the process to monitor",
    )
    paths: list[str] = Field(
        min_length=1,
        description="Path patterns to match for process detection",
    )

    @field_validator("paths")
    @classmethod
    def validate_paths(cls, v: list[str]) -> list[str]:
        """Validate that paths are not empty."""
        if not v:
            raise ValueError("At least one path pattern must be provided")
        for path in v:
            if not path.strip():
                raise ValueError("Path patterns cannot be empty")
        return v


class ProgressConfig(BaseConfig):
    """Configuration for progress tracking."""

    min_change_threshold: float = Field(
        default=5.0,
        ge=0.0,
        le=100.0,
        description="Minimum progress change to trigger notification (percentage)",
    )
    estimation_window: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Window size for ETC calculation (number of samples)",
    )
    exclusions: list[str] = Field(
        default_factory=list,
        description="Paths to exclude from size calculations",
    )

    @field_validator("exclusions")
    @classmethod
    def validate_exclusions(cls, v: list[str]) -> list[str]:
        """Validate exclusion patterns."""
        return [pattern.strip() for pattern in v if pattern.strip()]


class NotificationConfig(BaseConfig):
    """Configuration for notifications."""

    enabled_providers: list[Literal["telegram", "discord"]] = Field(
        default_factory=list,
        description="List of enabled providers",
    )
    events: list[Literal["started", "progress", "completed", "failed"]] = Field(
        default=["started", "progress", "completed", "failed"],
        description="Events that trigger notifications",
    )
    rate_limits: dict[str, int] = Field(
        default_factory=lambda: {"progress": 300, "status": 60},
        description="Rate limits for different notification types",
    )

    @field_validator("enabled_providers")
    @classmethod
    def validate_providers(cls, v: list[str]) -> list[str]:
        """Validate provider names."""
        valid_providers = {"telegram", "discord"}
        for provider in v:
            if provider not in valid_providers:
                raise ValueError(f"Invalid provider: {provider}")
        return v

    @field_validator("events")
    @classmethod
    def validate_events(cls, v: list[str]) -> list[str]:
        """Validate event names."""
        valid_events = {"started", "progress", "completed", "failed"}
        for event in v:
            if event not in valid_events:
                raise ValueError(f"Invalid event: {event}")
        return v

    @field_validator("rate_limits")
    @classmethod
    def validate_rate_limits(cls, v: dict[str, int]) -> dict[str, int]:
        """Validate rate limits."""
        required_keys = {"progress", "status"}
        missing_keys = required_keys - set(v.keys())
        if missing_keys:
            raise ValueError(f"Missing required rate limit keys: {missing_keys}")
        
        for key, value in v.items():
            if value < 0:
                raise ValueError(f"Rate limit for {key} must be non-negative")
        
        return v


class LoggingConfig(BaseConfig):
    """Configuration for logging."""

    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        description="Log level",
    )
    format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="Log format string",
    )
    file: str | None = Field(
        default=None,
        description="Log file path (null for console only)",
    )