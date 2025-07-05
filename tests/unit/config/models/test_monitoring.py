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
        assert config.interval == 30
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
        assert errors[0]["type"] == "greater_than"

    def test_monitoring_config_validation_detection_timeout(self) -> None:
        """Test MonitoringConfig validation for detection_timeout."""
        with pytest.raises(ValidationError) as exc_info:
            MonitoringConfig(detection_timeout=0)
        
        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["type"] == "greater_than"


class TestProcessConfig:
    """Test suite for ProcessConfig class."""

    def test_process_config_creation(self) -> None:
        """Test ProcessConfig creation with required fields."""
        config = ProcessConfig(
            name="mover",
            path="/usr/local/sbin/mover",
        )
        assert config.name == "mover"
        assert config.path == "/usr/local/sbin/mover"

    def test_process_config_validation_name_empty(self) -> None:
        """Test ProcessConfig validation for empty name."""
        with pytest.raises(ValidationError) as exc_info:
            ProcessConfig(name="", path="/usr/local/sbin/mover")
        
        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["type"] == "string_too_short"

    def test_process_config_validation_path_empty(self) -> None:
        """Test ProcessConfig validation for empty path."""
        with pytest.raises(ValidationError) as exc_info:
            ProcessConfig(name="mover", path="")
        
        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["type"] == "string_too_short"

    def test_process_config_validation_name_pattern(self) -> None:
        """Test ProcessConfig validation for name pattern."""
        # Valid names
        valid_names = ["mover", "rsync", "cp", "mv", "backup-tool", "sync_app"]
        for name in valid_names:
            config = ProcessConfig(name=name, path="/usr/bin/test")
            assert config.name == name

        # Invalid names (with special characters)
        invalid_names = ["mover!", "rsync@", "cp#", "mv$", "backup tool"]
        for name in invalid_names:
            with pytest.raises(ValidationError) as exc_info:
                ProcessConfig(name=name, path="/usr/bin/test")
            
            errors = exc_info.value.errors()
            assert len(errors) == 1
            assert errors[0]["type"] == "string_pattern_mismatch"

    def test_process_config_validation_path_pattern(self) -> None:
        """Test ProcessConfig validation for path pattern."""
        # Valid paths
        valid_paths = [
            "/usr/bin/mover",
            "/usr/local/sbin/rsync",
            "/opt/backup/bin/tool",
            "/home/user/bin/script",
        ]
        for path in valid_paths:
            config = ProcessConfig(name="test", path=path)
            assert config.path == path

        # Invalid paths (not absolute)
        invalid_paths = ["mover", "bin/mover", "./mover", "../bin/mover"]
        for path in invalid_paths:
            with pytest.raises(ValidationError) as exc_info:
                ProcessConfig(name="test", path=path)
            
            errors = exc_info.value.errors()
            assert len(errors) == 1
            assert errors[0]["type"] == "string_pattern_mismatch"


class TestProgressConfig:
    """Test suite for ProgressConfig class."""

    def test_progress_config_defaults(self) -> None:
        """Test ProgressConfig with default values."""
        config = ProgressConfig()
        assert config.min_change_threshold == 5.0
        assert config.estimation_window == 10
        assert config.exclusions == [
            "/.Trash-*",
            "/lost+found",
            "/tmp",
            "/var/tmp",
        ]

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
        with pytest.raises(ValidationError) as exc_info:
            ProgressConfig(min_change_threshold=0.0)
        
        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["type"] == "greater_than"

        with pytest.raises(ValidationError) as exc_info:
            ProgressConfig(min_change_threshold=101.0)
        
        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["type"] == "less_than_equal"

    def test_progress_config_validation_estimation_window(self) -> None:
        """Test ProgressConfig validation for estimation_window."""
        with pytest.raises(ValidationError) as exc_info:
            ProgressConfig(estimation_window=0)
        
        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["type"] == "greater_than"

    def test_progress_config_validation_exclusions_empty_string(self) -> None:
        """Test ProgressConfig validation for empty exclusion strings."""
        with pytest.raises(ValidationError) as exc_info:
            ProgressConfig(exclusions=["", "/valid/path"])
        
        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["type"] == "string_too_short"


class TestNotificationConfig:
    """Test suite for NotificationConfig class."""

    def test_notification_config_defaults(self) -> None:
        """Test NotificationConfig with default values."""
        config = NotificationConfig()
        assert config.enabled_providers == []
        assert config.events == ["started", "progress", "completed", "failed"]
        assert config.rate_limits.progress == 300
        assert config.rate_limits.status == 60

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
        valid_providers = [["telegram"], ["discord"], ["telegram", "discord"]]
        for providers in valid_providers:
            config = NotificationConfig(enabled_providers=providers)
            assert config.enabled_providers == providers

        # Invalid providers
        with pytest.raises(ValidationError) as exc_info:
            NotificationConfig(enabled_providers=["invalid_provider"])
        
        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert "literal_error" in errors[0]["type"]

    def test_notification_config_validation_events(self) -> None:
        """Test NotificationConfig validation for events."""
        # Valid events
        valid_events = [
            ["started"],
            ["progress"],
            ["completed"],
            ["failed"],
            ["started", "completed"],
        ]
        for events in valid_events:
            config = NotificationConfig(events=events)
            assert config.events == events

        # Invalid events
        with pytest.raises(ValidationError) as exc_info:
            NotificationConfig(events=["invalid_event"])
        
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
        assert config.file_path is None

    def test_logging_config_custom_values(self) -> None:
        """Test LoggingConfig with custom values."""
        config = LoggingConfig(
            level="DEBUG",
            format="%(levelname)s: %(message)s",
            file_path="/var/log/mover.log",
        )
        assert config.level == "DEBUG"
        assert config.format == "%(levelname)s: %(message)s"
        assert config.file_path == "/var/log/mover.log"

    def test_logging_config_validation_level(self) -> None:
        """Test LoggingConfig validation for level."""
        # Valid levels
        valid_levels = ["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"]
        for level in valid_levels:
            config = LoggingConfig(level=level)
            assert config.level == level

        # Invalid level
        with pytest.raises(ValidationError) as exc_info:
            LoggingConfig(level="INVALID")
        
        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert "literal_error" in errors[0]["type"]

    def test_logging_config_validation_format_empty(self) -> None:
        """Test LoggingConfig validation for empty format."""
        with pytest.raises(ValidationError) as exc_info:
            LoggingConfig(format="")
        
        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["type"] == "string_too_short"
