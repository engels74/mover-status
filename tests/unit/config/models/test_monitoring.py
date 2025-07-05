"""Tests for monitoring configuration models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from mover_status.config.models.monitoring import (
    MonitoringConfig,
    ProcessConfig,
    ProgressConfig,
    NotificationConfig,
    LoggingConfig,
)


class TestMonitoringConfig:
    """Test suite for MonitoringConfig class."""

    def test_monitoring_config_defaults(self) -> None:
        """Test MonitoringConfig with default values."""
        config = MonitoringConfig()
        assert config.interval == 60
        assert config.detection_timeout == 300
        assert config.dry_run is False

    def test_monitoring_config_custom_values(self) -> None:
        """Test MonitoringConfig with custom values."""
        config = MonitoringConfig(
            interval=60,
            detection_timeout=600,
            dry_run=True,
        )
        assert config.interval == 60
        assert config.detection_timeout == 600
        assert config.dry_run is True

    def test_monitoring_config_validation_interval(self) -> None:
        """Test MonitoringConfig validation for interval."""
        with pytest.raises(ValidationError) as exc_info:
            MonitoringConfig(interval=0)

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["type"] == "greater_than_equal"

    def test_monitoring_config_validation_detection_timeout(self) -> None:
        """Test MonitoringConfig validation for detection_timeout."""
        with pytest.raises(ValidationError) as exc_info:
            MonitoringConfig(detection_timeout=0)

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["type"] == "greater_than_equal"


class TestProcessConfig:
    """Test suite for ProcessConfig class."""

    def test_process_config_creation(self) -> None:
        """Test ProcessConfig creation with required fields."""
        config = ProcessConfig(
            name="mover",
            paths=["/usr/local/sbin/mover"],
        )
        assert config.name == "mover"
        assert config.paths == ["/usr/local/sbin/mover"]

    def test_process_config_validation_name_empty(self) -> None:
        """Test ProcessConfig validation for empty name."""
        with pytest.raises(ValidationError) as exc_info:
            ProcessConfig(name="", paths=["/usr/local/sbin/mover"])

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["type"] == "string_too_short"

    def test_process_config_validation_path_empty(self) -> None:
        """Test ProcessConfig validation for empty paths list."""
        with pytest.raises(ValidationError) as exc_info:
            ProcessConfig(name="mover", paths=[])

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["type"] == "too_short"

    def test_process_config_validation_name_pattern(self) -> None:
        """Test ProcessConfig validation for name pattern."""
        # Valid names
        valid_names = ["mover", "rsync", "cp", "mv", "backup-tool", "sync_app"]
        for name in valid_names:
            config = ProcessConfig(name=name, paths=["/usr/bin/test"])
            assert config.name == name

    def test_process_config_validation_path_pattern(self) -> None:
        """Test ProcessConfig validation for path pattern."""
        # Valid paths
        valid_paths = [
            ["/usr/bin/mover"],
            ["/usr/local/sbin/rsync"],
            ["/opt/backup/bin/tool", "/usr/bin/tool"],
            ["/home/user/bin/script"],
        ]
        for paths in valid_paths:
            config = ProcessConfig(name="test", paths=paths)
            assert config.paths == paths


class TestProgressConfig:
    """Test suite for ProgressConfig class."""

    def test_progress_config_defaults(self) -> None:
        """Test ProgressConfig with default values."""
        config = ProgressConfig()
        assert config.min_change_threshold == 5.0
        assert config.estimation_window == 10
        assert config.exclusions == []

    def test_progress_config_custom_values(self) -> None:
        """Test ProgressConfig with custom values."""
        custom_exclusions = ["/custom/path", "/another/path"]
        config = ProgressConfig(
            min_change_threshold=10.0,
            estimation_window=20,
            exclusions=custom_exclusions,
        )
        assert config.min_change_threshold == 10.0
        assert config.estimation_window == 20
        assert config.exclusions == custom_exclusions

    def test_progress_config_validation_threshold(self) -> None:
        """Test ProgressConfig validation for min_change_threshold."""
        # Test that valid values work
        config = ProgressConfig(min_change_threshold=0.0)
        assert config.min_change_threshold == 0.0

        config = ProgressConfig(min_change_threshold=100.0)
        assert config.min_change_threshold == 100.0

    def test_progress_config_validation_estimation_window(self) -> None:
        """Test ProgressConfig validation for estimation_window."""
        with pytest.raises(ValidationError) as exc_info:
            ProgressConfig(estimation_window=0)

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["type"] == "greater_than_equal"

    def test_progress_config_validation_exclusions_empty_string(self) -> None:
        """Test ProgressConfig validation for empty exclusion strings."""
        # Test that empty strings are filtered out by the validator
        config = ProgressConfig(exclusions=["", "/valid/path", "  ", "/another/path"])
        assert config.exclusions == ["/valid/path", "/another/path"]


class TestNotificationConfig:
    """Test suite for NotificationConfig class."""

    def test_notification_config_defaults(self) -> None:
        """Test NotificationConfig with default values."""
        config = NotificationConfig()
        assert config.enabled_providers == []
        assert config.events == ["started", "progress", "completed", "failed"]
        assert config.rate_limits["progress"] == 300
        assert config.rate_limits["status"] == 60

    def test_notification_config_custom_values(self) -> None:
        """Test NotificationConfig with custom values."""
        config = NotificationConfig(
            enabled_providers=["telegram", "discord"],
            events=["started", "completed"],
        )
        assert config.enabled_providers == ["telegram", "discord"]
        assert config.events == ["started", "completed"]

    def test_notification_config_validation_providers(self) -> None:
        """Test NotificationConfig validation for enabled_providers."""
        # Valid providers
        # Test individual valid providers
        config = NotificationConfig(enabled_providers=["telegram"])
        assert config.enabled_providers == ["telegram"]

        config = NotificationConfig(enabled_providers=["discord"])
        assert config.enabled_providers == ["discord"]

        config = NotificationConfig(enabled_providers=["telegram", "discord"])
        assert config.enabled_providers == ["telegram", "discord"]

        # Invalid providers - this would be caught at runtime by Pydantic
        # Type checker prevents us from testing invalid literals directly
        # We can test this by bypassing type checking
        with pytest.raises(ValidationError) as exc_info:
            NotificationConfig(enabled_providers=["invalid_provider"])  # pyright: ignore[reportArgumentType]

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert "literal_error" in errors[0]["type"]

    def test_notification_config_validation_events(self) -> None:
        """Test NotificationConfig validation for events."""
        # Test individual valid events
        config = NotificationConfig(events=["started"])
        assert config.events == ["started"]

        config = NotificationConfig(events=["progress"])
        assert config.events == ["progress"]

        config = NotificationConfig(events=["completed"])
        assert config.events == ["completed"]

        config = NotificationConfig(events=["failed"])
        assert config.events == ["failed"]

        config = NotificationConfig(events=["started", "completed"])
        assert config.events == ["started", "completed"]

        # Invalid events - bypassing type checker for runtime validation test
        with pytest.raises(ValidationError) as exc_info:
            NotificationConfig(events=["invalid_event"])  # pyright: ignore[reportArgumentType]
        
        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert "literal_error" in errors[0]["type"]


class TestLoggingConfig:
    """Test suite for LoggingConfig class."""

    def test_logging_config_defaults(self) -> None:
        """Test LoggingConfig with default values."""
        config = LoggingConfig()
        assert config.level == "INFO"
        assert config.format == "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        assert config.file is None

    def test_logging_config_custom_values(self) -> None:
        """Test LoggingConfig with custom values."""
        config = LoggingConfig(
            level="DEBUG",
            format="%(levelname)s: %(message)s",
            file="/var/log/mover.log",
        )
        assert config.level == "DEBUG"
        assert config.format == "%(levelname)s: %(message)s"
        assert config.file == "/var/log/mover.log"

    def test_logging_config_validation_level(self) -> None:
        """Test LoggingConfig validation for level."""
        # Valid levels
        valid_levels = ["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"]
        for level in valid_levels:
            config = LoggingConfig(level=level)  # pyright: ignore[reportArgumentType]
            assert config.level == level

        # Invalid level - bypassing type checker for runtime validation test
        with pytest.raises(ValidationError) as exc_info:
            LoggingConfig(level="INVALID")  # pyright: ignore[reportArgumentType]

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert "literal_error" in errors[0]["type"]

    def test_logging_config_validation_format_empty(self) -> None:
        """Test LoggingConfig validation for empty format."""
        # Test that empty format is allowed (no minimum length constraint)
        config = LoggingConfig(format="")
        assert config.format == ""
