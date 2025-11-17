"""Unit tests for configuration system.

Tests for Pydantic configuration models including validation logic,
field validators, and runtime configuration conversion.
"""

from pathlib import Path
from typing import TypeIs

import pytest
from pydantic import ValidationError

from mover_status.core.config import (
    ENV_VAR_PATTERN,
    ApplicationConfig,
    ApplicationRuntimeConfig,
    ConfigurationError,
    EnvironmentVariableError,
    MainConfig,
    MonitoringConfig,
    MonitoringRuntimeConfig,
    NotificationsConfig,
    ProvidersConfig,
    ProvidersRuntimeConfig,
    load_main_config,
    load_provider_config,
    resolve_env_var,
    resolve_env_vars_in_dict,
)


@pytest.mark.unit
class TestMonitoringConfig:
    """Test MonitoringConfig validation and defaults."""

    def test_valid_monitoring_config(self, tmp_path: Path) -> None:
        """Test creation with valid configuration."""
        pid_file = tmp_path / "mover.pid"

        config = MonitoringConfig(
            pid_file=pid_file,
            sampling_interval=30,
            process_timeout=600,
            exclusion_paths=[],
        )

        assert config.pid_file == pid_file
        assert config.sampling_interval == 30
        assert config.process_timeout == 600
        assert config.exclusion_paths == []

    def test_default_values(self, tmp_path: Path) -> None:
        """Test default values are applied correctly."""
        pid_file = tmp_path / "mover.pid"

        config = MonitoringConfig(pid_file=pid_file)

        assert config.sampling_interval == 60
        assert config.process_timeout == 300
        assert config.exclusion_paths == []

    def test_pid_file_parent_must_exist(self, tmp_path: Path) -> None:
        """Test validation fails if PID file parent directory does not exist."""
        nonexistent = tmp_path / "nonexistent" / "mover.pid"

        with pytest.raises(ValidationError) as exc_info:
            _ = MonitoringConfig(pid_file=nonexistent)

        assert "PID file parent directory does not exist" in str(exc_info.value)

    def test_sampling_interval_must_be_positive(self, tmp_path: Path) -> None:
        """Test sampling_interval must be greater than 0."""
        pid_file = tmp_path / "mover.pid"

        with pytest.raises(ValidationError) as exc_info:
            _ = MonitoringConfig(pid_file=pid_file, sampling_interval=0)

        assert "greater than 0" in str(exc_info.value).lower()

        with pytest.raises(ValidationError) as exc_info:
            _ = MonitoringConfig(pid_file=pid_file, sampling_interval=-5)

        assert "greater than 0" in str(exc_info.value).lower()

    def test_process_timeout_must_be_positive(self, tmp_path: Path) -> None:
        """Test process_timeout must be greater than 0."""
        pid_file = tmp_path / "mover.pid"

        with pytest.raises(ValidationError) as exc_info:
            _ = MonitoringConfig(pid_file=pid_file, process_timeout=0)

        assert "greater than 0" in str(exc_info.value).lower()

    def test_exclusion_paths_must_exist(self, tmp_path: Path) -> None:
        """Test validation fails if exclusion paths do not exist."""
        pid_file = tmp_path / "mover.pid"
        nonexistent = tmp_path / "nonexistent"

        with pytest.raises(ValidationError) as exc_info:
            _ = MonitoringConfig(pid_file=pid_file, exclusion_paths=[nonexistent])

        assert "Exclusion path does not exist" in str(exc_info.value)

    def test_valid_exclusion_paths(self, tmp_path: Path) -> None:
        """Test exclusion paths validation succeeds for existing paths."""
        pid_file = tmp_path / "mover.pid"
        exclusion1 = tmp_path / "exclude1"
        exclusion2 = tmp_path / "exclude2"
        exclusion1.mkdir()
        exclusion2.mkdir()

        config = MonitoringConfig(
            pid_file=pid_file,
            exclusion_paths=[exclusion1, exclusion2],
        )

        assert len(config.exclusion_paths) == 2
        assert exclusion1 in config.exclusion_paths
        assert exclusion2 in config.exclusion_paths


@pytest.mark.unit
class TestNotificationsConfig:
    """Test NotificationsConfig validation and defaults."""

    def test_valid_notifications_config(self) -> None:
        """Test creation with valid configuration."""
        config = NotificationsConfig(
            thresholds=[0.0, 50.0, 100.0],
            completion_enabled=True,
            retry_attempts=3,
        )

        assert config.thresholds == [0.0, 50.0, 100.0]
        assert config.completion_enabled is True
        assert config.retry_attempts == 3

    def test_default_values(self) -> None:
        """Test default values are applied correctly."""
        config = NotificationsConfig()

        assert config.thresholds == [0.0, 25.0, 50.0, 75.0, 100.0]
        assert config.completion_enabled is True
        assert config.retry_attempts == 5

    def test_thresholds_must_be_in_valid_range(self) -> None:
        """Test threshold percentages must be between 0 and 100."""
        with pytest.raises(ValidationError) as exc_info:
            _ = NotificationsConfig(thresholds=[-5.0, 50.0, 100.0])

        assert "Threshold must be between 0 and 100" in str(exc_info.value)

        with pytest.raises(ValidationError) as exc_info:
            _ = NotificationsConfig(thresholds=[0.0, 50.0, 150.0])

        assert "Threshold must be between 0 and 100" in str(exc_info.value)

    def test_retry_attempts_must_be_non_negative(self) -> None:
        """Test retry_attempts must be >= 0."""
        config = NotificationsConfig(retry_attempts=0)
        assert config.retry_attempts == 0

        with pytest.raises(ValidationError) as exc_info:
            _ = NotificationsConfig(retry_attempts=-1)

        assert "greater than or equal to 0" in str(exc_info.value).lower()

    def test_boundary_thresholds(self) -> None:
        """Test boundary values for thresholds (0 and 100)."""
        config = NotificationsConfig(thresholds=[0.0, 100.0])

        assert config.thresholds == [0.0, 100.0]


@pytest.mark.unit
class TestProvidersConfig:
    """Test ProvidersConfig validation."""

    def test_valid_providers_config_discord_only(self) -> None:
        """Test configuration with only webhook service enabled."""
        config = ProvidersConfig(discord_enabled=True, telegram_enabled=False)

        assert config.discord_enabled is True
        assert config.telegram_enabled is False

    def test_valid_providers_config_telegram_only(self) -> None:
        """Test configuration with only chat platform enabled."""
        config = ProvidersConfig(discord_enabled=False, telegram_enabled=True)

        assert config.discord_enabled is False
        assert config.telegram_enabled is True

    def test_valid_providers_config_both_enabled(self) -> None:
        """Test configuration with both providers enabled."""
        config = ProvidersConfig(discord_enabled=True, telegram_enabled=True)

        assert config.discord_enabled is True
        assert config.telegram_enabled is True

    def test_at_least_one_provider_must_be_enabled(self) -> None:
        """Test validation fails if no providers are enabled."""
        with pytest.raises(ValidationError) as exc_info:
            _ = ProvidersConfig(discord_enabled=False, telegram_enabled=False)

        assert "At least one notification provider must be enabled" in str(exc_info.value)

    def test_default_values(self) -> None:
        """Test default values require explicit enablement."""
        with pytest.raises(ValidationError) as exc_info:
            _ = ProvidersConfig()

        assert "At least one notification provider must be enabled" in str(exc_info.value)


@pytest.mark.unit
class TestApplicationConfig:
    """Test ApplicationConfig validation and defaults."""

    def test_valid_application_config(self) -> None:
        """Test creation with valid configuration."""
        config = ApplicationConfig(
            log_level="DEBUG",
            dry_run=True,
            version_check=False,
            syslog_enabled=False,
        )

        assert config.log_level == "DEBUG"
        assert config.dry_run is True
        assert config.version_check is False
        assert config.syslog_enabled is False

    def test_default_values(self) -> None:
        """Test default values are applied correctly."""
        config = ApplicationConfig()

        assert config.log_level == "INFO"
        assert config.dry_run is False
        assert config.version_check is True
        assert config.syslog_enabled is True

    def test_log_level_validation(self) -> None:
        """Test log_level must be a valid logging level."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

        for level in valid_levels:
            config = ApplicationConfig(log_level=level)
            assert config.log_level == level

        with pytest.raises(ValidationError) as exc_info:
            _ = ApplicationConfig(log_level="INVALID")

        assert "pattern" in str(exc_info.value).lower()


def is_monitoring_runtime_config(obj: object) -> TypeIs[MonitoringRuntimeConfig]:
    """Type predicate to narrow to MonitoringRuntimeConfig."""
    return isinstance(obj, dict) and "pid_file" in obj and "process_timeout" in obj


def is_providers_runtime_config(obj: object) -> TypeIs[ProvidersRuntimeConfig]:
    """Type predicate to narrow to ProvidersRuntimeConfig."""
    return isinstance(obj, dict) and "discord_enabled" in obj and "telegram_enabled" in obj


def is_application_runtime_config(obj: object) -> TypeIs[ApplicationRuntimeConfig]:
    """Type predicate to narrow to ApplicationRuntimeConfig."""
    return isinstance(obj, dict) and "log_level" in obj and "dry_run" in obj


@pytest.mark.unit
class TestMainConfig:
    """Test MainConfig integration and runtime conversion."""

    def test_valid_main_config(self, tmp_path: Path) -> None:
        """Test creation with valid complete configuration."""
        pid_file = tmp_path / "mover.pid"

        config = MainConfig(
            monitoring=MonitoringConfig(pid_file=pid_file),
            notifications=NotificationsConfig(),
            providers=ProvidersConfig(discord_enabled=True),
            application=ApplicationConfig(),
        )

        assert config.monitoring.pid_file == pid_file
        assert config.notifications.completion_enabled is True
        assert config.providers.discord_enabled is True
        assert config.application.log_level == "INFO"

    def test_application_has_default(self, tmp_path: Path) -> None:
        """Test application section has default value."""
        pid_file = tmp_path / "mover.pid"

        config = MainConfig(
            monitoring=MonitoringConfig(pid_file=pid_file),
            notifications=NotificationsConfig(),
            providers=ProvidersConfig(discord_enabled=True),
        )

        assert config.application.log_level == "INFO"
        assert config.application.dry_run is False

    def test_to_runtime_config_conversion(self, tmp_path: Path) -> None:
        """Test conversion to runtime configuration format."""
        pid_file = tmp_path / "mover.pid"

        config = MainConfig(
            monitoring=MonitoringConfig(
                pid_file=pid_file,
                sampling_interval=45,
                process_timeout=400,
            ),
            notifications=NotificationsConfig(retry_attempts=3),
            providers=ProvidersConfig(discord_enabled=True, telegram_enabled=True),
            application=ApplicationConfig(log_level="DEBUG", dry_run=True),
        )

        runtime = config.to_runtime_config()

        assert "monitoring" in runtime
        assert "providers" in runtime
        assert "application" in runtime

        monitoring_runtime = runtime["monitoring"]
        assert is_monitoring_runtime_config(monitoring_runtime)
        assert monitoring_runtime["pid_file"] == pid_file
        assert monitoring_runtime["process_timeout"] == 400

        providers_runtime = runtime["providers"]
        assert is_providers_runtime_config(providers_runtime)
        assert providers_runtime["discord_enabled"] is True
        assert providers_runtime["telegram_enabled"] is True

        application_runtime = runtime["application"]
        assert is_application_runtime_config(application_runtime)
        assert application_runtime["log_level"] == "DEBUG"
        assert application_runtime["dry_run"] is True

    def test_validation_error_propagation(self, tmp_path: Path) -> None:
        """Test validation errors from nested configs propagate to MainConfig."""
        pid_file = tmp_path / "mover.pid"

        with pytest.raises(ValidationError) as exc_info:
            _ = MainConfig(
                monitoring=MonitoringConfig(
                    pid_file=pid_file,
                    sampling_interval=-10,  # Invalid: must be positive
                ),
                notifications=NotificationsConfig(),
                providers=ProvidersConfig(discord_enabled=True),
            )

        assert "greater than 0" in str(exc_info.value).lower()

        with pytest.raises(ValidationError) as exc_info:
            _ = MainConfig(
                monitoring=MonitoringConfig(pid_file=pid_file),
                notifications=NotificationsConfig(
                    thresholds=[0.0, 150.0]  # Invalid: > 100
                ),
                providers=ProvidersConfig(discord_enabled=True),
            )

        assert "Threshold must be between 0 and 100" in str(exc_info.value)


@pytest.mark.unit
class TestEnvironmentVariablePattern:
    """Test environment variable pattern regex."""

    def test_pattern_matches_valid_variable_names(self) -> None:
        """Test pattern matches valid environment variable names."""
        assert ENV_VAR_PATTERN.search("${SIMPLE_VAR}") is not None
        assert ENV_VAR_PATTERN.search("${VAR_WITH_UNDERSCORES}") is not None
        assert ENV_VAR_PATTERN.search("${VAR123}") is not None
        assert ENV_VAR_PATTERN.search("${VAR_123_ABC}") is not None

    def test_pattern_extracts_variable_name(self) -> None:
        """Test pattern extracts variable name correctly."""
        match = ENV_VAR_PATTERN.search("${TEST_VAR}")
        assert match is not None
        assert match.group(1) == "TEST_VAR"

    def test_pattern_does_not_match_invalid_syntax(self) -> None:
        """Test pattern does not match invalid syntax."""
        assert ENV_VAR_PATTERN.search("$SIMPLE_VAR") is None  # Missing braces
        assert ENV_VAR_PATTERN.search("{SIMPLE_VAR}") is None  # Missing $
        assert ENV_VAR_PATTERN.search("${lowercase}") is None  # Lowercase not allowed
        assert ENV_VAR_PATTERN.search("${VAR-WITH-DASHES}") is None  # Dashes not allowed

    def test_pattern_finds_multiple_variables(self) -> None:
        """Test pattern finds all variables in a string."""
        text = "prefix ${VAR1} middle ${VAR2} suffix"
        matches = list(ENV_VAR_PATTERN.finditer(text))
        assert len(matches) == 2
        assert matches[0].group(1) == "VAR1"
        assert matches[1].group(1) == "VAR2"


@pytest.mark.unit
class TestResolveEnvVar:
    """Test resolve_env_var function."""

    def test_resolve_single_variable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test resolving a single environment variable."""
        monkeypatch.setenv("TEST_VAR", "test_value")
        result = resolve_env_var("${TEST_VAR}")
        assert result == "test_value"

    def test_resolve_variable_in_string(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test resolving environment variable within a string."""
        monkeypatch.setenv("TEST_VAR", "secret")
        result = resolve_env_var("prefix_${TEST_VAR}_suffix")
        assert result == "prefix_secret_suffix"

    def test_resolve_multiple_variables(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test resolving multiple environment variables in one string."""
        monkeypatch.setenv("VAR1", "value1")
        monkeypatch.setenv("VAR2", "value2")
        result = resolve_env_var("${VAR1}_middle_${VAR2}")
        assert result == "value1_middle_value2"

    def test_no_variables_returns_original(self) -> None:
        """Test string without variables is returned unchanged."""
        result = resolve_env_var("no variables here")
        assert result == "no variables here"

    def test_missing_variable_raises_error(self) -> None:
        """Test missing environment variable raises EnvironmentVariableError."""
        with pytest.raises(EnvironmentVariableError) as exc_info:
            _ = resolve_env_var("${NONEXISTENT_VAR}")

        error_msg = str(exc_info.value)
        assert "NONEXISTENT_VAR" in error_msg
        assert "not set" in error_msg
        assert "Please set this variable" in error_msg

    def test_error_message_does_not_expose_secrets(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test error messages never expose secret values."""
        monkeypatch.setenv("SECRET_VAR", "super_secret_value")

        # Error for missing variable should not show other env var values
        with pytest.raises(EnvironmentVariableError) as exc_info:
            _ = resolve_env_var("${MISSING_VAR}")

        error_msg = str(exc_info.value)
        assert "super_secret_value" not in error_msg
        assert "MISSING_VAR" in error_msg

    def test_empty_string_returns_empty(self) -> None:
        """Test empty string is handled correctly."""
        result = resolve_env_var("")
        assert result == ""

    def test_variable_with_empty_value(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test environment variable with empty value is resolved."""
        monkeypatch.setenv("EMPTY_VAR", "")
        result = resolve_env_var("${EMPTY_VAR}")
        assert result == ""


@pytest.mark.unit
class TestResolveEnvVarsInDict:
    """Test resolve_env_vars_in_dict function."""

    def test_resolve_simple_dict(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test resolving environment variables in a simple dictionary."""
        monkeypatch.setenv("SECRET", "my_secret")
        data = {"key": "${SECRET}"}
        result = resolve_env_vars_in_dict(data)
        assert result == {"key": "my_secret"}

    def test_resolve_nested_dict(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test resolving environment variables in nested dictionaries."""
        monkeypatch.setenv("SECRET", "nested_secret")
        data = {"outer": {"inner": "${SECRET}"}}
        result = resolve_env_vars_in_dict(data)
        assert result == {"outer": {"inner": "nested_secret"}}

    def test_resolve_list_of_strings(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test resolving environment variables in lists."""
        monkeypatch.setenv("VAR1", "value1")
        monkeypatch.setenv("VAR2", "value2")
        data = {"items": ["${VAR1}", "${VAR2}", "static"]}
        result = resolve_env_vars_in_dict(data)
        assert result == {"items": ["value1", "value2", "static"]}

    def test_resolve_list_of_dicts(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test resolving environment variables in lists of dictionaries."""
        monkeypatch.setenv("SECRET", "list_secret")
        data = {"items": [{"key": "${SECRET}"}, {"key": "static"}]}
        result = resolve_env_vars_in_dict(data)
        assert result == {"items": [{"key": "list_secret"}, {"key": "static"}]}

    def test_preserve_non_string_values(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test non-string values are preserved unchanged."""
        monkeypatch.setenv("SECRET", "my_secret")
        data = {
            "string": "${SECRET}",
            "int": 42,
            "float": 3.14,
            "bool": True,
            "none": None,
        }
        result = resolve_env_vars_in_dict(data)
        assert result == {
            "string": "my_secret",
            "int": 42,
            "float": 3.14,
            "bool": True,
            "none": None,
        }

    def test_complex_nested_structure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test resolving in complex nested structures."""
        monkeypatch.setenv("WEBHOOK_URL", "https://example.com/webhook")
        monkeypatch.setenv("BOT_TOKEN", "secret_token")

        data = {
            "providers": {
                "discord": {
                    "webhook_url": "${WEBHOOK_URL}",
                    "enabled": True,
                },
                "telegram": {
                    "bot_token": "${BOT_TOKEN}",
                    "chat_id": 123456,
                },
            },
            "settings": {
                "timeout": 30,
                "retries": [1, 2, 3],
            },
        }

        result = resolve_env_vars_in_dict(data)

        # Type assertions for nested dict access in tests
        assert isinstance(result["providers"], dict)
        assert isinstance(result["providers"]["discord"], dict)
        assert isinstance(result["providers"]["telegram"], dict)
        assert isinstance(result["settings"], dict)

        assert result["providers"]["discord"]["webhook_url"] == "https://example.com/webhook"
        assert result["providers"]["telegram"]["bot_token"] == "secret_token"
        assert result["providers"]["discord"]["enabled"] is True
        assert result["providers"]["telegram"]["chat_id"] == 123456
        assert result["settings"]["timeout"] == 30
        assert result["settings"]["retries"] == [1, 2, 3]

    def test_missing_variable_in_dict_raises_error(self) -> None:
        """Test missing environment variable in dict raises error."""
        data = {"key": "${MISSING_VAR}"}
        with pytest.raises(EnvironmentVariableError) as exc_info:
            _ = resolve_env_vars_in_dict(data)

        assert "MISSING_VAR" in str(exc_info.value)

    def test_missing_variable_in_nested_dict_raises_error(self) -> None:
        """Test missing environment variable in nested dict raises error."""
        data = {"outer": {"inner": "${MISSING_VAR}"}}
        with pytest.raises(EnvironmentVariableError) as exc_info:
            _ = resolve_env_vars_in_dict(data)

        assert "MISSING_VAR" in str(exc_info.value)

    def test_empty_dict_returns_empty(self) -> None:
        """Test empty dictionary is handled correctly."""
        result = resolve_env_vars_in_dict({})
        assert result == {}

    def test_dict_without_variables_unchanged(self) -> None:
        """Test dictionary without variables is returned with same values."""
        data = {"key1": "value1", "key2": 42, "nested": {"key3": "value3"}}
        result = resolve_env_vars_in_dict(data)
        assert result == data


@pytest.mark.unit
class TestLoadMainConfig:
    """Test load_main_config function."""

    def test_load_valid_config(self, tmp_path: Path) -> None:
        """Test loading a valid configuration file."""
        # Create a valid configuration file
        config_file = tmp_path / "config.yaml"
        pid_file = tmp_path / "mover.pid"

        config_content = f"""
monitoring:
  pid_file: {pid_file}
  sampling_interval: 30
  process_timeout: 600
  exclusion_paths: []

notifications:
  thresholds: [0.0, 50.0, 100.0]
  completion_enabled: true
  retry_attempts: 3

providers:
  discord_enabled: true
  telegram_enabled: false

application:
  log_level: DEBUG
  dry_run: false
  version_check: true
  syslog_enabled: false
"""
        _ = config_file.write_text(config_content)

        # Load configuration
        config = load_main_config(config_file)

        # Verify configuration
        assert config.monitoring.pid_file == pid_file
        assert config.monitoring.sampling_interval == 30
        assert config.monitoring.process_timeout == 600
        assert config.notifications.thresholds == [0.0, 50.0, 100.0]
        assert config.notifications.retry_attempts == 3
        assert config.providers.discord_enabled is True
        assert config.providers.telegram_enabled is False
        assert config.application.log_level == "DEBUG"
        assert config.application.dry_run is False

    def test_load_config_with_env_vars(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test loading configuration with environment variable resolution."""
        monkeypatch.setenv("TEST_PID_FILE", str(tmp_path / "mover.pid"))
        monkeypatch.setenv("TEST_LOG_LEVEL", "WARNING")

        config_file = tmp_path / "config.yaml"
        config_content = """
monitoring:
  pid_file: ${TEST_PID_FILE}
  sampling_interval: 60

notifications:
  thresholds: [0.0, 100.0]

providers:
  discord_enabled: true
  telegram_enabled: false

application:
  log_level: ${TEST_LOG_LEVEL}
"""
        _ = config_file.write_text(config_content)

        config = load_main_config(config_file)

        assert config.monitoring.pid_file == tmp_path / "mover.pid"
        assert config.application.log_level == "WARNING"

    def test_load_config_file_not_found(self, tmp_path: Path) -> None:
        """Test error when configuration file does not exist."""
        nonexistent = tmp_path / "nonexistent.yaml"

        with pytest.raises(ConfigurationError) as exc_info:
            _ = load_main_config(nonexistent)

        error_msg = str(exc_info.value)
        assert "not found" in error_msg
        assert str(nonexistent) in error_msg

    def test_load_config_invalid_yaml(self, tmp_path: Path) -> None:
        """Test error when YAML file is malformed."""
        config_file = tmp_path / "config.yaml"
        _ = config_file.write_text("invalid: yaml: content: [")

        with pytest.raises(ConfigurationError) as exc_info:
            _ = load_main_config(config_file)

        error_msg = str(exc_info.value)
        assert "parse" in error_msg.lower()
        assert "YAML" in error_msg

    def test_load_config_not_dict(self, tmp_path: Path) -> None:
        """Test error when YAML root is not a dictionary."""
        config_file = tmp_path / "config.yaml"
        _ = config_file.write_text("- item1\n- item2\n")

        with pytest.raises(ConfigurationError) as exc_info:
            _ = load_main_config(config_file)

        error_msg = str(exc_info.value)
        assert "dictionary" in error_msg.lower()
        assert "list" in error_msg.lower()

    def test_load_config_missing_env_var(self, tmp_path: Path) -> None:
        """Test error when environment variable is missing."""
        config_file = tmp_path / "config.yaml"
        pid_file = tmp_path / "mover.pid"

        config_content = f"""
monitoring:
  pid_file: {pid_file}

notifications:
  thresholds: [0.0, 100.0]

providers:
  discord_enabled: true
  telegram_enabled: false

application:
  log_level: ${{MISSING_VAR}}
"""
        _ = config_file.write_text(config_content)

        with pytest.raises(ConfigurationError) as exc_info:
            _ = load_main_config(config_file)

        error_msg = str(exc_info.value)
        assert "MISSING_VAR" in error_msg
        assert "not set" in error_msg

    def test_load_config_validation_error(self, tmp_path: Path) -> None:
        """Test error when configuration fails Pydantic validation."""
        config_file = tmp_path / "config.yaml"
        pid_file = tmp_path / "mover.pid"

        # Invalid: sampling_interval must be positive
        config_content = f"""
monitoring:
  pid_file: {pid_file}
  sampling_interval: -10

notifications:
  thresholds: [0.0, 100.0]

providers:
  discord_enabled: true
  telegram_enabled: false
"""
        _ = config_file.write_text(config_content)

        with pytest.raises(ConfigurationError) as exc_info:
            _ = load_main_config(config_file)

        error_msg = str(exc_info.value)
        assert "validation failed" in error_msg.lower()
        assert "Field:" in error_msg
        assert "Error:" in error_msg

    def test_load_config_field_level_diagnostics(self, tmp_path: Path) -> None:
        """Test that validation errors include field-level diagnostics."""
        config_file = tmp_path / "config.yaml"
        pid_file = tmp_path / "mover.pid"

        # Invalid: threshold > 100
        config_content = f"""
monitoring:
  pid_file: {pid_file}

notifications:
  thresholds: [0.0, 150.0]

providers:
  discord_enabled: true
  telegram_enabled: false
"""
        _ = config_file.write_text(config_content)

        with pytest.raises(ConfigurationError) as exc_info:
            _ = load_main_config(config_file)

        error_msg = str(exc_info.value)
        # Should contain field path
        assert "notifications" in error_msg.lower() or "thresholds" in error_msg.lower()
        # Should contain error details
        assert "Field:" in error_msg
        assert "Error:" in error_msg
        assert "Type:" in error_msg


@pytest.mark.unit
class TestLoadProviderConfig:
    """Test load_provider_config function."""

    def test_load_valid_provider_config(self, tmp_path: Path) -> None:
        """Test loading a valid provider configuration."""
        # Create a simple Pydantic model for testing
        from pydantic import BaseModel, Field

        class TestProviderConfig(BaseModel):
            """Test provider configuration."""

            api_key: str = Field(description="API key")
            enabled: bool = Field(default=True, description="Enable provider")

        config_file = tmp_path / "provider.yaml"
        config_content = """
api_key: test_key_123
enabled: true
"""
        _ = config_file.write_text(config_content)

        config = load_provider_config(
            config_file,
            TestProviderConfig,
            provider_name="TestProvider",
        )

        assert config.api_key == "test_key_123"
        assert config.enabled is True

    def test_load_provider_config_with_env_vars(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test loading provider configuration with environment variables."""
        from pydantic import BaseModel, Field

        class TestProviderConfig(BaseModel):
            """Test provider configuration."""

            api_key: str = Field(description="API key")

        monkeypatch.setenv("PROVIDER_API_KEY", "secret_key_from_env")

        config_file = tmp_path / "provider.yaml"
        config_content = """
api_key: ${PROVIDER_API_KEY}
"""
        _ = config_file.write_text(config_content)

        config = load_provider_config(
            config_file,
            TestProviderConfig,
            provider_name="TestProvider",
        )

        assert config.api_key == "secret_key_from_env"

    def test_load_provider_config_file_not_found(self, tmp_path: Path) -> None:
        """Test error when provider configuration file does not exist."""
        from pydantic import BaseModel

        class TestProviderConfig(BaseModel):
            """Test provider configuration."""

            api_key: str

        nonexistent = tmp_path / "nonexistent.yaml"

        with pytest.raises(ConfigurationError) as exc_info:
            _ = load_provider_config(
                nonexistent,
                TestProviderConfig,
                provider_name="TestProvider",
            )

        error_msg = str(exc_info.value)
        assert "TestProvider" in error_msg
        assert "not found" in error_msg

    def test_load_provider_config_validation_error(self, tmp_path: Path) -> None:
        """Test error when provider configuration fails validation."""
        from pydantic import BaseModel, Field

        class TestProviderConfig(BaseModel):
            """Test provider configuration."""

            api_key: str = Field(min_length=10, description="API key")

        config_file = tmp_path / "provider.yaml"
        config_content = """
api_key: short
"""
        _ = config_file.write_text(config_content)

        with pytest.raises(ConfigurationError) as exc_info:
            _ = load_provider_config(
                config_file,
                TestProviderConfig,
                provider_name="TestProvider",
            )

        error_msg = str(exc_info.value)
        assert "TestProvider" in error_msg
        assert "validation failed" in error_msg.lower()
        assert "Field:" in error_msg

    def test_load_provider_config_provider_name_in_errors(self, tmp_path: Path) -> None:
        """Test that provider name appears in all error messages."""
        from pydantic import BaseModel

        class TestProviderConfig(BaseModel):
            """Test provider configuration."""

            api_key: str

        # Test file not found error
        with pytest.raises(ConfigurationError) as exc_info:
            _ = load_provider_config(
                tmp_path / "missing.yaml",
                TestProviderConfig,
                provider_name="Discord",
            )
        assert "Discord" in str(exc_info.value)

        # Test invalid YAML error
        config_file = tmp_path / "invalid.yaml"
        _ = config_file.write_text("invalid: yaml: [")
        with pytest.raises(ConfigurationError) as exc_info:
            _ = load_provider_config(
                config_file,
                TestProviderConfig,
                provider_name="Telegram",
            )
        assert "Telegram" in str(exc_info.value)
