"""
Tests for the default configuration module.
"""

import pytest
from typing import Any, Dict

# Import the module to test
from mover_status.config.default_config import DEFAULT_CONFIG


class TestDefaultConfig:
    """Test cases for the default configuration."""

    def test_config_is_dictionary(self) -> None:
        """Test that the default configuration is a dictionary."""
        assert isinstance(DEFAULT_CONFIG, dict)

    def test_required_top_level_keys(self) -> None:
        """Test that all required top-level keys are present in the configuration."""
        required_keys = [
            "notification",
            "monitoring",
            "messages",
            "paths",
            "debug",
        ]
        for key in required_keys:
            assert key in DEFAULT_CONFIG, f"Missing required key: {key}"

    def test_notification_section(self) -> None:
        """Test the notification section of the configuration."""
        notification = DEFAULT_CONFIG.get("notification", {})
        
        # Check required keys
        required_keys = [
            "use_telegram",
            "use_discord",
            "telegram_bot_token",
            "telegram_chat_id",
            "discord_webhook_url",
            "discord_name",
            "notification_increment",
        ]
        for key in required_keys:
            assert key in notification, f"Missing required key in notification section: {key}"
        
        # Check types
        assert isinstance(notification["use_telegram"], bool)
        assert isinstance(notification["use_discord"], bool)
        assert isinstance(notification["telegram_bot_token"], str)
        assert isinstance(notification["telegram_chat_id"], str)
        assert isinstance(notification["discord_webhook_url"], str)
        assert isinstance(notification["discord_name"], str)
        assert isinstance(notification["notification_increment"], int)
        
        # Check default values
        assert notification["notification_increment"] > 0, "Notification increment should be positive"

    def test_monitoring_section(self) -> None:
        """Test the monitoring section of the configuration."""
        monitoring = DEFAULT_CONFIG.get("monitoring", {})
        
        # Check required keys
        required_keys = [
            "mover_executable",
            "cache_directory",
            "poll_interval",
        ]
        for key in required_keys:
            assert key in monitoring, f"Missing required key in monitoring section: {key}"
        
        # Check types
        assert isinstance(monitoring["mover_executable"], str)
        assert isinstance(monitoring["cache_directory"], str)
        assert isinstance(monitoring["poll_interval"], int)
        
        # Check default values
        assert monitoring["poll_interval"] > 0, "Poll interval should be positive"
        assert monitoring["mover_executable"].startswith("/"), "Mover executable should be an absolute path"
        assert monitoring["cache_directory"].startswith("/"), "Cache directory should be an absolute path"

    def test_messages_section(self) -> None:
        """Test the messages section of the configuration."""
        messages = DEFAULT_CONFIG.get("messages", {})
        
        # Check required keys
        required_keys = [
            "telegram_moving",
            "discord_moving",
            "completion",
        ]
        for key in required_keys:
            assert key in messages, f"Missing required key in messages section: {key}"
        
        # Check types
        assert isinstance(messages["telegram_moving"], str)
        assert isinstance(messages["discord_moving"], str)
        assert isinstance(messages["completion"], str)
        
        # Check that message templates contain required placeholders
        required_placeholders = ["{percent}", "{remaining_data}", "{etc}"]
        for placeholder in required_placeholders:
            assert placeholder in messages["telegram_moving"], f"Missing placeholder {placeholder} in telegram_moving message"
            assert placeholder in messages["discord_moving"], f"Missing placeholder {placeholder} in discord_moving message"

    def test_paths_section(self) -> None:
        """Test the paths section of the configuration."""
        paths = DEFAULT_CONFIG.get("paths", {})
        
        # Check required keys
        required_keys = [
            "exclude",
        ]
        for key in required_keys:
            assert key in paths, f"Missing required key in paths section: {key}"
        
        # Check types
        assert isinstance(paths["exclude"], list)
        
        # Check that all excluded paths are strings
        for path in paths["exclude"]:
            assert isinstance(path, str)

    def test_debug_section(self) -> None:
        """Test the debug section of the configuration."""
        debug = DEFAULT_CONFIG.get("debug", {})
        
        # Check required keys
        required_keys = [
            "dry_run",
            "enable_debug",
        ]
        for key in required_keys:
            assert key in debug, f"Missing required key in debug section: {key}"
        
        # Check types
        assert isinstance(debug["dry_run"], bool)
        assert isinstance(debug["enable_debug"], bool)
