"""Unit tests for configuration system.

Tests for Pydantic configuration models including validation logic,
field validators, and runtime configuration conversion.
"""

from pathlib import Path
from typing import TypeIs

import pytest
from pydantic import ValidationError

from mover_status.core.config import (
    ApplicationConfig,
    ApplicationRuntimeConfig,
    MainConfig,
    MonitoringConfig,
    MonitoringRuntimeConfig,
    NotificationsConfig,
    ProvidersConfig,
    ProvidersRuntimeConfig,
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
