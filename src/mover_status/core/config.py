"""Configuration system for mover-status application.

This module implements the main configuration schema using Pydantic for
validation, with support for environment variable resolution and fail-fast
validation with actionable error messages.
"""

import os
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Annotated, Final, NotRequired, ReadOnly, TypedDict

import yaml
from pydantic import BaseModel, Field, ValidationError, field_validator

# Regular expression pattern for environment variable references
# Matches ${VARIABLE_NAME} syntax where VARIABLE_NAME can contain letters, digits, and underscores
ENV_VAR_PATTERN: Final[re.Pattern[str]] = re.compile(r"\$\{([A-Z0-9_]+)\}")


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
    pid_check_interval: Annotated[
        int,
        Field(
            gt=0,
            description="PID file polling interval in seconds",
        ),
    ] = 1
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

    This TypedDict represents runtime-only provider enablement that
    should not be modified during execution.
    """

    enabled: ReadOnly[list[str]]


class ProvidersConfig(BaseModel):
    """Configuration for notification provider enablement.

    Defines which notification providers are enabled for notification dispatch.
    Providers are loaded dynamically from the plugins directory when enabled.
    """

    enabled: Annotated[
        list[str],
        Field(
            description="List of enabled notification provider identifiers",
        ),
    ]

    @field_validator("enabled", mode="after")
    @classmethod
    def validate_provider_identifiers(cls, v: list[str]) -> list[str]:
        """Validate provider identifiers against discovered plugins.

        Args:
            v: List of provider identifiers

        Returns:
            Validated provider identifiers

        Raises:
            ValueError: If any provider identifier is unknown
        """
        if not v:
            msg = "At least one notification provider must be enabled"
            raise ValueError(msg)

        # Import here to avoid circular dependency at module level
        from mover_status.plugins.discovery import discover_plugins

        # Discover all available plugins (regardless of enablement)
        all_plugins = discover_plugins(enabled_only=False, provider_flags={})
        available_identifiers = {plugin.identifier for plugin in all_plugins}

        # Check for unknown provider identifiers
        unknown = set(v) - available_identifiers
        if unknown:
            msg = (
                f"Unknown provider identifier(s): {', '.join(sorted(unknown))}. "
                f"Available providers: {', '.join(sorted(available_identifiers))}"
            )
            raise ValueError(msg)

        return v


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
                enabled=self.providers.enabled,
            ),
            "application": ApplicationRuntimeConfig(
                log_level=self.application.log_level,
                dry_run=self.application.dry_run,
                version_check=self.application.version_check,
                syslog_enabled=self.application.syslog_enabled,
            ),
        }


class EnvironmentVariableError(Exception):
    """Exception raised when environment variable resolution fails.

    This exception is raised when a required environment variable is missing
    or when environment variable syntax is invalid. It provides clear error
    messages without exposing secret values.
    """


def resolve_env_var(value: str) -> str:
    """Resolve environment variable references in a string value.

    Parses ${VARIABLE_NAME} syntax and replaces with environment variable values.
    Supports multiple environment variable references in a single string.

    Args:
        value: String potentially containing environment variable references

    Returns:
        String with environment variables resolved

    Raises:
        EnvironmentVariableError: If a required environment variable is missing

    Examples:
        >>> os.environ["TEST_VAR"] = "secret_value"
        >>> resolve_env_var("${TEST_VAR}")
        'secret_value'
        >>> resolve_env_var("prefix_${TEST_VAR}_suffix")
        'prefix_secret_value_suffix'
        >>> resolve_env_var("no variables here")
        'no variables here'
    """

    def replace_match(match: re.Match[str]) -> str:
        """Replace a single environment variable reference.

        Args:
            match: Regex match object for ${VARIABLE_NAME}

        Returns:
            Environment variable value

        Raises:
            EnvironmentVariableError: If environment variable is not set
        """
        var_name = match.group(1)
        env_value = os.environ.get(var_name)

        if env_value is None:
            msg = (
                f"Required environment variable '{var_name}' is not set. "
                f"Please set this variable before starting the application."
            )
            raise EnvironmentVariableError(msg)

        return env_value

    # Replace all environment variable references
    return ENV_VAR_PATTERN.sub(replace_match, value)


def resolve_env_vars_in_dict(data: Mapping[str, object]) -> dict[str, object]:
    """Recursively resolve environment variables in a dictionary.

    Traverses nested dictionaries and lists, resolving environment variable
    references in string values. Non-string values are preserved as-is.

    This function is designed to be used at the API boundary when loading
    YAML configuration files, before Pydantic validation. The use of `object`
    type reflects the unvalidated nature of YAML data.

    Args:
        data: Dictionary potentially containing environment variable references

    Returns:
        New dictionary with environment variables resolved

    Raises:
        EnvironmentVariableError: If a required environment variable is missing

    Examples:
        >>> os.environ["SECRET"] = "my_secret"
        >>> resolve_env_vars_in_dict({"key": "${SECRET}"})
        {'key': 'my_secret'}
        >>> resolve_env_vars_in_dict({"nested": {"key": "${SECRET}"}})
        {'nested': {'key': 'my_secret'}}
    """
    result: dict[str, object] = {}

    for key, value in data.items():
        if isinstance(value, str):
            # Resolve environment variables in string values
            result[key] = resolve_env_var(value)
        elif isinstance(value, dict):
            # Recursively resolve in nested dictionaries
            # YAML data is untyped at load time; validated by Pydantic after resolution
            result[key] = resolve_env_vars_in_dict(value)  # pyright: ignore[reportUnknownArgumentType]  # YAML boundary
        elif isinstance(value, list):
            # Recursively resolve in lists
            resolved_list: list[object] = []
            for item in value:  # pyright: ignore[reportUnknownVariableType]  # YAML list items
                if isinstance(item, str):
                    resolved_list.append(resolve_env_var(item))
                elif isinstance(item, dict):
                    # YAML data is untyped at load time; validated by Pydantic after resolution
                    resolved_list.append(resolve_env_vars_in_dict(item))  # pyright: ignore[reportUnknownArgumentType]  # YAML boundary
                else:
                    # Non-string, non-dict items preserved as-is (e.g., int, float, bool, None)
                    resolved_list.append(item)  # pyright: ignore[reportUnknownArgumentType]  # YAML primitives
            result[key] = resolved_list
        else:
            # Preserve non-string, non-dict, non-list values as-is
            result[key] = value

    return result


class ConfigurationError(Exception):
    """Exception raised when configuration loading or validation fails.

    This exception provides detailed, actionable error messages for configuration
    issues including file not found, YAML parsing errors, and validation failures.
    """


def load_main_config(config_path: Path) -> MainConfig:
    """Load and validate main application configuration from YAML file.

    Loads the main configuration file, resolves environment variables, and
    validates against the MainConfig schema. Provides fail-fast validation
    with actionable error messages.

    Args:
        config_path: Path to main configuration YAML file

    Returns:
        Validated MainConfig instance

    Raises:
        ConfigurationError: If configuration file cannot be loaded or is invalid
        EnvironmentVariableError: If required environment variable is missing

    Examples:
        >>> config = load_main_config(Path("config/mover-status.yaml"))
        >>> print(config.monitoring.pid_file)
        /var/run/mover.pid
    """
    # Validate file exists
    if not config_path.exists():
        msg = (
            f"Configuration file not found: {config_path}\n"
            f"Please create a configuration file at this location.\n"
            f"See documentation for configuration file format."
        )
        raise ConfigurationError(msg)

    # Load YAML file
    try:
        with config_path.open("r") as f:
            raw_data: object = yaml.safe_load(f)  # pyright: ignore[reportAny]  # YAML boundary
    except yaml.YAMLError as e:
        msg = (
            f"Failed to parse YAML configuration file: {config_path}\n"
            f"YAML parsing error: {e}\n"
            f"Please check the file for syntax errors."
        )
        raise ConfigurationError(msg) from e
    except OSError as e:
        msg = f"Failed to read configuration file: {config_path}\nError: {e}\nPlease check file permissions."
        raise ConfigurationError(msg) from e

    # Validate YAML contains a dictionary
    if not isinstance(raw_data, dict):
        msg = (
            f"Invalid configuration file format: {config_path}\n"
            f"Expected YAML dictionary at root level, got: {type(raw_data).__name__}\n"
            f"Configuration file must contain key-value pairs."
        )
        raise ConfigurationError(msg)

    # Resolve environment variables
    try:
        resolved_data = resolve_env_vars_in_dict(raw_data)  # pyright: ignore[reportUnknownArgumentType]  # YAML boundary
    except EnvironmentVariableError as e:
        msg = (
            f"Environment variable resolution failed in: {config_path}\n"
            f"{e}\n"
            f"Set the required environment variable before starting the application."
        )
        raise ConfigurationError(msg) from e

    # Validate against Pydantic schema
    try:
        config = MainConfig.model_validate(resolved_data)
    except ValidationError as e:
        # Format validation errors with field-level diagnostics
        error_lines = ["Configuration validation failed:", ""]
        for error in e.errors():
            field_path = " → ".join(str(loc) for loc in error["loc"])
            error_msg = error["msg"]
            error_type = error["type"]
            error_lines.append(f"  Field: {field_path}")
            error_lines.append(f"  Error: {error_msg}")
            error_lines.append(f"  Type: {error_type}")
            error_lines.append("")

        error_lines.append(f"Configuration file: {config_path}")
        error_lines.append("Please fix the above errors and try again.")

        msg = "\n".join(error_lines)
        raise ConfigurationError(msg) from e

    return config


def load_provider_config[T: BaseModel](
    config_path: Path,
    model: type[T],
    *,
    provider_name: str,
) -> T:
    """Load and validate provider-specific configuration from YAML file.

    Loads a provider-specific configuration file, resolves environment variables,
    and validates against the provided Pydantic model. Provides fail-fast validation
    with actionable error messages specific to the provider.

    Args:
        config_path: Path to provider configuration YAML file
        model: Pydantic model class for validation
        provider_name: Human-readable provider name for error messages

    Returns:
        Validated provider configuration instance

    Raises:
        ConfigurationError: If configuration file cannot be loaded or is invalid
        EnvironmentVariableError: If required environment variable is missing

    Examples:
        >>> from mover_status.plugins.provider_a.config import ProviderAConfig
        >>> config = load_provider_config(
        ...     Path("config/providers/provider_a.yaml"),
        ...     ProviderAConfig,
        ...     provider_name="Provider A"
        ... )
        >>> print(config.webhook_url)
        https://example.com/webhooks/...
    """
    # Validate file exists
    if not config_path.exists():
        msg = (
            f"{provider_name} configuration file not found: {config_path}\n"
            f"Please create a configuration file for {provider_name} at this location.\n"
            f"See documentation for {provider_name} configuration format."
        )
        raise ConfigurationError(msg)

    # Load YAML file
    try:
        with config_path.open("r") as f:
            raw_data: object = yaml.safe_load(f)  # pyright: ignore[reportAny]  # YAML boundary
    except yaml.YAMLError as e:
        msg = (
            f"Failed to parse {provider_name} YAML configuration: {config_path}\n"
            f"YAML parsing error: {e}\n"
            f"Please check the file for syntax errors."
        )
        raise ConfigurationError(msg) from e
    except OSError as e:
        msg = (
            f"Failed to read {provider_name} configuration file: {config_path}\n"
            f"Error: {e}\n"
            f"Please check file permissions."
        )
        raise ConfigurationError(msg) from e

    # Validate YAML contains a dictionary
    if not isinstance(raw_data, dict):
        msg = (
            f"Invalid {provider_name} configuration format: {config_path}\n"
            f"Expected YAML dictionary at root level, got: {type(raw_data).__name__}\n"
            f"Configuration file must contain key-value pairs."
        )
        raise ConfigurationError(msg)

    # Resolve environment variables
    try:
        resolved_data = resolve_env_vars_in_dict(raw_data)  # pyright: ignore[reportUnknownArgumentType]  # YAML boundary
    except EnvironmentVariableError as e:
        msg = (
            f"Environment variable resolution failed in {provider_name} config: {config_path}\n"
            f"{e}\n"
            f"Set the required environment variable before starting the application."
        )
        raise ConfigurationError(msg) from e

    # Validate against Pydantic schema
    try:
        config = model.model_validate(resolved_data)
    except ValidationError as e:
        # Format validation errors with field-level diagnostics
        error_lines = [f"{provider_name} configuration validation failed:", ""]
        for error in e.errors():
            field_path = " → ".join(str(loc) for loc in error["loc"])
            error_msg = error["msg"]
            error_type = error["type"]
            error_lines.append(f"  Field: {field_path}")
            error_lines.append(f"  Error: {error_msg}")
            error_lines.append(f"  Type: {error_type}")
            error_lines.append("")

        error_lines.append(f"Configuration file: {config_path}")
        error_lines.append(f"Please fix the above errors in your {provider_name} configuration.")

        msg = "\n".join(error_lines)
        raise ConfigurationError(msg) from e

    return config
