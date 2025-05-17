"""
Tests for the default configuration modules.
"""

# Import the modules to test
from mover_status.config.default_config import DEFAULT_CONFIG
from mover_status.notification.providers.telegram import TELEGRAM_DEFAULTS
from mover_status.notification.providers.discord import DISCORD_DEFAULTS


class TestCoreDefaultConfig:
    """Test cases for the core default configuration."""

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
            "notification_increment",
            "enabled_providers",
        ]
        for key in required_keys:
            assert key in notification, f"Missing required key in notification section: {key}"

        # Check types
        assert isinstance(notification["notification_increment"], int)
        assert isinstance(notification["enabled_providers"], list)

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
            "completion",
        ]
        for key in required_keys:
            assert key in messages, f"Missing required key in messages section: {key}"

        # Check types
        assert isinstance(messages["completion"], str)

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
        assert all(isinstance(item, str) for item in paths["exclude"])  # pyright:ignore[reportUnknownVariableType]

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


class TestTelegramDefaultConfig:
    """Test cases for the Telegram provider default configuration."""

    def test_config_is_dictionary(self) -> None:
        """Test that the Telegram default configuration is a dictionary."""
        assert isinstance(TELEGRAM_DEFAULTS, dict)

    def test_required_keys(self) -> None:
        """Test that all required keys are present in the configuration."""
        required_keys = [
            "name",
            "enabled",
            "bot_token",
            "chat_id",
            "message_template",
            "parse_mode",
            "disable_notification",
        ]
        for key in required_keys:
            assert key in TELEGRAM_DEFAULTS, f"Missing required key in Telegram defaults: {key}"

    def test_types(self) -> None:
        """Test that all values have the correct types."""
        assert isinstance(TELEGRAM_DEFAULTS["name"], str)
        assert isinstance(TELEGRAM_DEFAULTS["enabled"], bool)
        assert isinstance(TELEGRAM_DEFAULTS["bot_token"], str)
        assert isinstance(TELEGRAM_DEFAULTS["chat_id"], str)
        assert isinstance(TELEGRAM_DEFAULTS["message_template"], str)
        assert isinstance(TELEGRAM_DEFAULTS["parse_mode"], str)
        assert isinstance(TELEGRAM_DEFAULTS["disable_notification"], bool)

    def test_message_template(self) -> None:
        """Test that the message template contains required placeholders."""
        template = TELEGRAM_DEFAULTS["message_template"]
        required_placeholders = ["{percent}", "{remaining_data}", "{etc}"]
        for placeholder in required_placeholders:
            assert placeholder in template, f"Missing placeholder {placeholder} in Telegram message template"


class TestDiscordDefaultConfig:
    """Test cases for the Discord provider default configuration."""

    def test_config_is_dictionary(self) -> None:
        """Test that the Discord default configuration is a dictionary."""
        assert isinstance(DISCORD_DEFAULTS, dict)

    def test_required_keys(self) -> None:
        """Test that all required keys are present in the configuration."""
        required_keys = [
            "name",
            "enabled",
            "webhook_url",
            "username",
            "message_template",
            "use_embeds",
            "embed_title",
            "embed_colors",
        ]
        for key in required_keys:
            assert key in DISCORD_DEFAULTS, f"Missing required key in Discord defaults: {key}"

    def test_types(self) -> None:
        """Test that all values have the correct types."""
        assert isinstance(DISCORD_DEFAULTS["name"], str)
        assert isinstance(DISCORD_DEFAULTS["enabled"], bool)
        assert isinstance(DISCORD_DEFAULTS["webhook_url"], str)
        assert isinstance(DISCORD_DEFAULTS["username"], str)
        assert isinstance(DISCORD_DEFAULTS["message_template"], str)
        assert isinstance(DISCORD_DEFAULTS["use_embeds"], bool)
        assert isinstance(DISCORD_DEFAULTS["embed_title"], str)
        assert isinstance(DISCORD_DEFAULTS["embed_colors"], dict)

    def test_message_template(self) -> None:
        """Test that the message template contains required placeholders."""
        template = DISCORD_DEFAULTS["message_template"]
        required_placeholders = ["{percent}", "{remaining_data}", "{etc}"]
        for placeholder in required_placeholders:
            assert placeholder in template, f"Missing placeholder {placeholder} in Discord message template"

    def test_embed_colors(self) -> None:
        """Test that the embed colors dictionary has the required keys."""
        colors = DISCORD_DEFAULTS["embed_colors"]
        required_keys = ["low_progress", "mid_progress", "high_progress", "complete"]
        for key in required_keys:
            assert key in colors, f"Missing required key in embed_colors: {key}"
            assert isinstance(colors[key], int), f"Embed color {key} should be an integer"
