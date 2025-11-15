"""Configuration system for mover-status application.

This module implements the main configuration schema using Pydantic for
validation, with support for environment variable resolution and fail-fast
validation with actionable error messages.
"""

from collections.abc import Sequence
from pathlib import Path
from typing import Annotated, NotRequired, ReadOnly, TypedDict

from pydantic import BaseModel, Field, field_validator, model_validator


class MonitoringRuntimeConfig(TypedDict):
    """Immutable runtime configuration for monitoring (ReadOnly fields).

    This TypedDict represents runtime-only configuration that should not be
    modified during execution. Uses ReadOnly to enforce immutability at type level.
    """

    pid_file: ReadOnly[Path]
    process_timeout: ReadOnly[int]


class MonitoringConfig(BaseModel):
    """Configuration for mover process monitoring.

    Defines monitoring behavior including PID file location, sampling intervals,
    timeout values, and directory exclusion rules for progress calculation.
    """

    pid_file: Annotated[Path, Field(description="Path to mover PID file")]
    sampling_interval: Annotated[
        int,
        Field(
            gt=0,
            description="Disk usage sampling interval in seconds",
        ),
    ] = 60
    process_timeout: Annotated[
        int,
        Field(
            gt=0,
            description="Timeout for process detection in seconds",
        ),
    ] = 300
    exclusion_paths: Annotated[
        Sequence[Path],
        Field(
            description="Directory paths to exclude from progress calculations",
        ),
    ] = []

    @field_validator("pid_file", mode="after")
    @classmethod
    def validate_pid_file_parent_exists(cls, v: Path) -> Path:
        """Validate that PID file parent directory exists.

        Args:
            v: PID file path

        Returns:
            Validated path

        Raises:
            ValueError: If parent directory does not exist
        """
        if not v.parent.exists():
            msg = f"PID file parent directory does not exist: {v.parent}"
            raise ValueError(msg)
        return v

    @field_validator("exclusion_paths", mode="after")
    @classmethod
    def validate_exclusion_paths_exist(cls, v: Sequence[Path]) -> Sequence[Path]:
        """Validate that exclusion paths exist.

        Args:
            v: Sequence of exclusion paths

        Returns:
            Validated paths

        Raises:
            ValueError: If any exclusion path does not exist
        """
        for path in v:
            if not path.exists():
                msg = f"Exclusion path does not exist: {path}"
                raise ValueError(msg)
        return v


class NotificationsConfig(BaseModel):
    """Configuration for notification delivery behavior.

    Defines notification thresholds, completion behavior, and retry logic
    for notification dispatch to all enabled providers.
    """

    thresholds: Annotated[
        Sequence[float],
        Field(
            description="Progress percentage thresholds for notifications",
        ),
    ] = [0.0, 25.0, 50.0, 75.0, 100.0]
    completion_enabled: Annotated[
        bool,
        Field(
            description="Whether to send completion notification",
        ),
    ] = True
    retry_attempts: Annotated[
        int,
        Field(
            ge=0,
            description="Maximum retry attempts for failed notifications",
        ),
    ] = 5

    @field_validator("thresholds", mode="after")
    @classmethod
    def validate_threshold_percentages(cls, v: Sequence[float]) -> Sequence[float]:
        """Validate threshold percentages are between 0 and 100.

        Args:
            v: Sequence of threshold percentages

        Returns:
            Validated thresholds

        Raises:
            ValueError: If any threshold is not in range [0, 100]
        """
        for threshold in v:
            if not 0 <= threshold <= 100:
                msg = f"Threshold must be between 0 and 100, got: {threshold}"
                raise ValueError(msg)
        return v


class ProvidersRuntimeConfig(TypedDict):
    """Immutable runtime configuration for providers (ReadOnly fields).

    This TypedDict represents runtime-only provider enablement flags that
    should not be modified during execution.
    """

    discord_enabled: ReadOnly[bool]
    telegram_enabled: ReadOnly[bool]


class ProvidersConfig(BaseModel):
    """Configuration for notification provider enablement.

    Defines which notification providers are enabled for notification dispatch.
    Providers are loaded dynamically from the plugins directory when enabled.
    """

    discord_enabled: Annotated[
        bool,
        Field(
            description="Enable webhook service notifications",
        ),
    ] = False
    telegram_enabled: Annotated[
        bool,
        Field(
            description="Enable chat platform notifications",
        ),
    ] = False

    @model_validator(mode="after")
    def validate_at_least_one_provider(self) -> "ProvidersConfig":
        """Validate that at least one provider is enabled.

        Returns:
            Validated configuration

        Raises:
            ValueError: If no providers are enabled
        """
        if not (self.discord_enabled or self.telegram_enabled):
            msg = "At least one notification provider must be enabled"
            raise ValueError(msg)
        return self


class ApplicationRuntimeConfig(TypedDict):
    """Immutable runtime configuration for application (ReadOnly fields).

    This TypedDict represents runtime-only application settings that should
    not be modified during execution. Uses NotRequired for optional fields.
    """

    log_level: ReadOnly[str]
    dry_run: ReadOnly[bool]
    version_check: ReadOnly[bool]
    syslog_enabled: NotRequired[ReadOnly[bool]]


class ApplicationConfig(BaseModel):
    """Configuration for application-level settings.

    Defines operational behavior including logging level, dry-run mode,
    version checking, and syslog integration.
    """

    log_level: Annotated[
        str,
        Field(
            description="Logging level",
            pattern=r"^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$",
        ),
    ] = "INFO"
    dry_run: Annotated[
        bool,
        Field(
            description="Dry-run mode: log notifications without sending",
        ),
    ] = False
    version_check: Annotated[
        bool,
        Field(
            description="Check for application updates on startup",
        ),
    ] = True
    syslog_enabled: Annotated[
        bool,
        Field(
            description="Enable syslog integration",
        ),
    ] = True


class MainConfig(BaseModel):
    """Main application configuration schema.

    Top-level configuration container aggregating all configuration sections:
    - monitoring: Mover process monitoring settings
    - notifications: Notification delivery behavior
    - providers: Provider enablement flags
    - application: Application-level settings

    This model provides fail-fast validation at application startup with
    comprehensive field-level validation and actionable error messages.
    """

    monitoring: Annotated[
        MonitoringConfig,
        Field(
            description="Mover process monitoring configuration",
        ),
    ]
    notifications: Annotated[
        NotificationsConfig,
        Field(
            description="Notification delivery configuration",
        ),
    ]
    providers: Annotated[
        ProvidersConfig,
        Field(
            description="Provider enablement configuration",
        ),
    ]
    application: Annotated[
        ApplicationConfig,
        Field(
            description="Application-level configuration",
        ),
    ] = ApplicationConfig()

    def to_runtime_config(
        self,
    ) -> dict[str, MonitoringRuntimeConfig | ProvidersRuntimeConfig | ApplicationRuntimeConfig]:
        """Convert configuration to runtime format with ReadOnly TypedDict sections.

        Returns:
            Dictionary containing runtime configuration with immutable sections
        """
        return {
            "monitoring": MonitoringRuntimeConfig(
                pid_file=self.monitoring.pid_file,
                process_timeout=self.monitoring.process_timeout,
            ),
            "providers": ProvidersRuntimeConfig(
                discord_enabled=self.providers.discord_enabled,
                telegram_enabled=self.providers.telegram_enabled,
            ),
            "application": ApplicationRuntimeConfig(
                log_level=self.application.log_level,
                dry_run=self.application.dry_run,
                version_check=self.application.version_check,
                syslog_enabled=self.application.syslog_enabled,
            ),
        }
