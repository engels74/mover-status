"""Tests for main configuration model."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from mover_status.config.models.main import AppConfig
from mover_status.config.models.monitoring import (
    MonitoringConfig,
    ProcessConfig,
    ProgressConfig,
    NotificationConfig,
    LoggingConfig,
)
from mover_status.config.models.providers import (
    ProviderConfig,
    TelegramConfig,
    DiscordConfig,
)


class TestAppConfig:
    """Test suite for AppConfig class."""

    def test_app_config_minimal_creation(self) -> None:
        """Test AppConfig creation with minimal required fields."""
        config = AppConfig(
            process=ProcessConfig(
                name="mover",
                paths=["/usr/local/sbin/mover"],
            )
        )

        # Required field
        assert config.process.name == "mover"
        assert config.process.paths == ["/usr/local/sbin/mover"]
        
        # Default values
        assert isinstance(config.monitoring, MonitoringConfig)
        assert isinstance(config.progress, ProgressConfig)
        assert isinstance(config.notifications, NotificationConfig)
        assert isinstance(config.logging, LoggingConfig)
        assert isinstance(config.providers, ProviderConfig)

    def test_app_config_full_creation(self) -> None:
        """Test AppConfig creation with all fields specified."""
        monitoring = MonitoringConfig(interval=60, dry_run=True)
        process = ProcessConfig(name="rsync", paths=["/usr/bin/rsync"])
        progress = ProgressConfig(min_change_threshold=10.0)
        notifications = NotificationConfig(enabled_providers=["telegram"])
        logging = LoggingConfig(level="DEBUG")
        providers = ProviderConfig(
            telegram=TelegramConfig(
                bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
                chat_ids=[123],
            )
        )
        
        config = AppConfig(
            monitoring=monitoring,
            process=process,
            progress=progress,
            notifications=notifications,
            logging=logging,
            providers=providers,
        )
        
        assert config.monitoring == monitoring
        assert config.process == process
        assert config.progress == progress
        assert config.notifications == notifications
        assert config.logging == logging
        assert config.providers == providers

    def test_app_config_validation_missing_process(self) -> None:
        """Test AppConfig validation when process field is missing."""
        with pytest.raises(ValidationError) as exc_info:
            _ = AppConfig()  # pyright: ignore[reportCallIssue] # Testing validation error
        
        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["type"] == "missing"
        assert errors[0]["loc"] == ("process",)

    def test_app_config_validation_enabled_providers_configured(self) -> None:
        """Test AppConfig validation for enabled providers being configured."""
        # Valid case: enabled provider is configured
        telegram_config = TelegramConfig(
            bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
            chat_ids=[123],
        )
        
        config = AppConfig(
            process=ProcessConfig(name="mover", paths=["/usr/bin/mover"]),
            notifications=NotificationConfig(enabled_providers=["telegram"]),
            providers=ProviderConfig(telegram=telegram_config),
        )
        
        # Should not raise validation error
        assert config.notifications.enabled_providers == ["telegram"]
        assert config.providers.telegram == telegram_config

    def test_app_config_validation_enabled_providers_not_configured(self) -> None:
        """Test AppConfig validation when enabled providers are not configured."""
        with pytest.raises(ValidationError) as exc_info:
            _ = AppConfig(
                process=ProcessConfig(name="mover", paths=["/usr/bin/mover"]),
                notifications=NotificationConfig(enabled_providers=["telegram"]),
                providers=ProviderConfig(),  # No telegram config
            )
        
        errors = exc_info.value.errors()
        # We expect at least one error, but there might be additional ProcessConfig validation errors
        assert len(errors) >= 1
        # Check that there's a validation error related to telegram provider
        error_messages = str(errors)
        assert "telegram" in error_messages or "provider" in error_messages

    def test_app_config_validation_multiple_enabled_providers_partial_configured(self) -> None:
        """Test AppConfig validation when some enabled providers are not configured."""
        telegram_config = TelegramConfig(
            bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
            chat_ids=[123],
        )
        
        with pytest.raises(ValidationError) as exc_info:
            _ = AppConfig(
                process=ProcessConfig(name="mover", paths=["/usr/bin/mover"]),
                notifications=NotificationConfig(enabled_providers=["telegram", "discord"]),
                providers=ProviderConfig(telegram=telegram_config),  # Missing discord config
            )
        
        errors = exc_info.value.errors()
        assert len(errors) >= 1
        # Check that there's a validation error related to discord provider
        error_messages = str(errors)
        assert "discord" in error_messages or "provider" in error_messages

    def test_app_config_validation_all_enabled_providers_configured(self) -> None:
        """Test AppConfig validation when all enabled providers are configured."""
        telegram_config = TelegramConfig(
            bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
            chat_ids=[123],
        )
        discord_config = DiscordConfig(
            webhook_url="https://discord.com/api/webhooks/123/abc",
        )
        
        config = AppConfig(
            process=ProcessConfig(name="mover", paths=["/usr/bin/mover"]),
            notifications=NotificationConfig(enabled_providers=["telegram", "discord"]),
            providers=ProviderConfig(
                telegram=telegram_config,
                discord=discord_config,
            ),
        )
        
        # Should not raise validation error
        assert config.notifications.enabled_providers == ["telegram", "discord"]
        assert config.providers.telegram == telegram_config
        assert config.providers.discord == discord_config

    def test_app_config_validation_no_enabled_providers(self) -> None:
        """Test AppConfig validation when no providers are enabled."""
        config = AppConfig(
            process=ProcessConfig(name="mover", paths=["/usr/bin/mover"]),
            notifications=NotificationConfig(enabled_providers=[]),
            providers=ProviderConfig(),
        )
        
        # Should not raise validation error when no providers are enabled
        assert config.notifications.enabled_providers == []
        assert config.providers.telegram is None
        assert config.providers.discord is None

    def test_app_config_validation_providers_configured_but_not_enabled(self) -> None:
        """Test AppConfig validation when providers are configured but not enabled."""
        telegram_config = TelegramConfig(
            bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
            chat_ids=[123],
        )
        
        config = AppConfig(
            process=ProcessConfig(name="mover", paths=["/usr/bin/mover"]),
            notifications=NotificationConfig(enabled_providers=[]),
            providers=ProviderConfig(telegram=telegram_config),
        )
        
        # Should not raise validation error - it's okay to have providers configured but not enabled
        assert config.notifications.enabled_providers == []
        assert config.providers.telegram == telegram_config

    def test_app_config_forbids_extra_fields(self) -> None:
        """Test that AppConfig forbids extra fields."""
        with pytest.raises(ValidationError) as exc_info:
            _ = AppConfig(
                process=ProcessConfig(name="mover", paths=["/usr/bin/mover"]),
                extra_field="not_allowed",  # pyright: ignore[reportCallIssue] # Testing validation error
            )
        
        errors = exc_info.value.errors()
        assert len(errors) >= 1
        # Check that there's an extra_forbidden error
        error_types = [error["type"] for error in errors]
        assert "extra_forbidden" in error_types

    def test_app_config_nested_validation_errors(self) -> None:
        """Test AppConfig validation with nested validation errors."""
        with pytest.raises(ValidationError) as exc_info:
            _ = AppConfig(
                process=ProcessConfig(name="", paths=["/usr/bin/mover"]),  # Invalid empty name
            )
        
        errors = exc_info.value.errors()
        assert len(errors) >= 1
        # Check that there's a validation error for the empty name
        name_errors = [error for error in errors if "name" in str(error.get("loc", []))]
        assert len(name_errors) >= 1
        assert name_errors[0]["type"] == "string_too_short"

    def test_app_config_complex_nested_structure(self) -> None:
        """Test AppConfig with complex nested configuration structure."""
        config = AppConfig(
            monitoring=MonitoringConfig(
                interval=45,
                detection_timeout=600,
                dry_run=False,
            ),
            process=ProcessConfig(
                name="backup-tool",
                paths=["/opt/backup/bin/backup-tool"],
            ),
            progress=ProgressConfig(
                min_change_threshold=2.5,
                estimation_window=15,
                exclusions=["/custom/exclude", "/another/exclude"],
            ),
            notifications=NotificationConfig(
                enabled_providers=["telegram", "discord"],
                events=["started", "completed", "failed"],
            ),
            logging=LoggingConfig(
                level="WARNING",
                format="%(levelname)s: %(message)s",
                file="/var/log/backup.log",
            ),
            providers=ProviderConfig(
                telegram=TelegramConfig(
                    bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
                    chat_ids=[-1001234567890, 123456789],
                ),
                discord=DiscordConfig(
                    webhook_url="https://discord.com/api/webhooks/123456789/abcdefghijk",
                ),
            ),
        )
        
        # Verify all nested structures are properly configured
        assert config.monitoring.interval == 45
        assert config.process.name == "backup-tool"
        assert config.progress.min_change_threshold == 2.5
        assert config.notifications.enabled_providers == ["telegram", "discord"]
        assert config.logging.level == "WARNING"
        assert config.providers.telegram is not None
        assert config.providers.discord is not None
        assert len(config.providers.telegram.chat_ids) == 2
