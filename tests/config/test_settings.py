"""Unit tests for the Settings configuration system."""

import os
from pathlib import Path
from typing import Dict, Any, Set

import pytest
from pydantic import ValidationError

from config.constants import LogLevel, MessagePriority, NotificationProvider
from config.settings import Settings, FileSystemSettings, LoggingSettings, MonitoringSettings
from config.providers.discord.settings import DiscordSettings
from config.providers.telegram.settings import TelegramSettings


@pytest.fixture
def temp_env():
    """Fixture to manage temporary environment variables."""
    old_env = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(old_env)


@pytest.fixture
def sample_yaml_config(tmp_path) -> Path:
    """Create a sample YAML configuration file."""
    cache_path = tmp_path / "cache"
    excluded_path = cache_path / "excluded"
    log_dir = tmp_path / "logs"

    # Create required directories
    cache_path.mkdir(parents=True)
    excluded_path.mkdir(parents=True)
    log_dir.mkdir(parents=True)

    config = {
        "filesystem": {
            "cache_path": str(cache_path),
            "excluded_paths": [str(excluded_path)]
        },
        "logging": {
            "log_dir": str(log_dir),
            "log_level": "DEBUG",
            "debug_mode": True
        },
        "monitoring": {
            "polling_interval": 1.0,
            "notification_increment": 10,
            "message_priority": "normal"
        },
        "discord": {
            "enabled": True,
            "webhook_url": "https://discord.com/api/webhooks/123456789/abcdefghijklmnop"
        },
        "telegram": {
            "enabled": True,
            "bot_token": "5934756012:AAHjwqTZ8V1RjPxk9vLmNyOcBsQdFeGhIjK",
            "chat_id": "-1001234567890"
        }
    }
    
    config_path = tmp_path / "config.yml"
    config_path.write_text("""
filesystem:
  cache_path: {cache_path}
  excluded_paths:
    - {excluded_path}
logging:
  log_dir: {log_dir}
  log_level: DEBUG
  debug_mode: true
monitoring:
  polling_interval: 1.0
  notification_increment: 10
  message_priority: normal
discord:
  enabled: true
  webhook_url: https://discord.com/api/webhooks/123456789/abcdefghijklmnop
telegram:
  enabled: true
  bot_token: 5934756012:AAHjwqTZ8V1RjPxk9vLmNyOcBsQdFeGhIjK
  chat_id: -1001234567890
    """.format(
        cache_path=str(cache_path),
        excluded_path=str(excluded_path),
        log_dir=str(log_dir)
    ))
    
    return config_path


def test_settings_default_values():
    """Test that Settings initializes with correct default values."""
    settings = Settings()
    
    assert isinstance(settings.filesystem, FileSystemSettings)
    assert isinstance(settings.logging, LoggingSettings)
    assert isinstance(settings.monitoring, MonitoringSettings)
    assert settings.dry_run is False
    assert settings.check_version is True


def test_settings_from_env(temp_env):
    """Test loading settings from environment variables."""
    os.environ.update({
        "MOVER_DRY_RUN": "true",
        "MOVER_LOGGING__LOG_LEVEL": "DEBUG",
        "MOVER_MONITORING__POLLING_INTERVAL": "2.5",
        "MOVER_DISCORD__ENABLED": "true",
        "MOVER_DISCORD__WEBHOOK_URL": "https://discord.com/api/webhooks/123456789/abcdefghijklmnop"
    })
    
    settings = Settings()
    assert settings.dry_run is True
    assert settings.logging.log_level == LogLevel.DEBUG
    assert settings.monitoring.polling_interval == 2.5
    assert settings.discord.enabled is True
    assert settings.discord.webhook_url == "https://discord.com/api/webhooks/123456789/abcdefghijklmnop"


def test_settings_from_yaml(sample_yaml_config):
    """Test loading settings from YAML file."""
    settings = Settings.from_yaml(sample_yaml_config)
    
    assert settings.logging.log_level == LogLevel.DEBUG
    assert settings.logging.debug_mode is True
    assert settings.monitoring.polling_interval == 1.0
    assert settings.monitoring.notification_increment == 10
    assert settings.monitoring.message_priority == MessagePriority.NORMAL
    assert settings.discord.enabled is True
    assert settings.telegram.enabled is True
    assert settings.telegram.bot_token == "5934756012:AAHjwqTZ8V1RjPxk9vLmNyOcBsQdFeGhIjK"
    assert settings.telegram.chat_id == -1001234567890


def test_settings_validation():
    """Test settings validation rules."""
    with pytest.raises(ValidationError) as exc_info:
        MonitoringSettings(polling_interval=0.05)  # Too low
    assert "polling_interval" in str(exc_info.value)
    
    with pytest.raises(ValidationError) as exc_info:
        MonitoringSettings(notification_increment=101)  # Too high
    assert "notification_increment" in str(exc_info.value)


def test_active_providers():
    """Test the active_providers property."""
    settings = Settings(
        discord=DiscordSettings(enabled=True),
        telegram=TelegramSettings(enabled=False)
    )
    
    assert settings.active_providers == [NotificationProvider.DISCORD]
    
    settings.telegram.enabled = True
    assert set(settings.active_providers) == {
        NotificationProvider.DISCORD,
        NotificationProvider.TELEGRAM
    }


def test_filesystem_settings_validation(tmp_path):
    """Test filesystem settings validation."""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    
    # Valid configuration
    fs_settings = FileSystemSettings(cache_path=cache_dir)
    assert fs_settings.cache_path == cache_dir
    
    # Invalid cache path
    with pytest.raises(ValidationError) as exc_info:
        FileSystemSettings(cache_path=tmp_path / "nonexistent")
    assert "Cache path does not exist" in str(exc_info.value)
    
    # Invalid excluded path
    with pytest.raises(ValidationError) as exc_info:
        FileSystemSettings(
            cache_path=cache_dir,
            excluded_paths={tmp_path / "nonexistent"}
        )
    assert "Excluded path does not exist" in str(exc_info.value)
