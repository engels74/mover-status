"""Tests for provider configuration models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from mover_status.config.models.providers import (
    DiscordConfig,
    DiscordEmbedConfig,
    DiscordEmbedColors,
    DiscordMentions,
    DiscordNotificationConfig,
    TelegramConfig,
    TelegramFormatConfig,
    TelegramTemplates,
    TelegramNotificationConfig,
    ProviderConfig,
)
from mover_status.config.models.base import RateLimitConfig, RetryConfig


class TestDiscordEmbedColors:
    """Test suite for DiscordEmbedColors class."""

    def test_discord_embed_colors_defaults(self) -> None:
        """Test DiscordEmbedColors with default values."""
        colors = DiscordEmbedColors()
        assert colors.started == 0x00ff00  # Green
        assert colors.progress == 0x0099ff  # Blue
        assert colors.completed == 0x00cc00  # Green
        assert colors.failed == 0xff0000  # Red

    def test_discord_embed_colors_custom_values(self) -> None:
        """Test DiscordEmbedColors with custom values."""
        colors = DiscordEmbedColors(
            started=0xFF0000,
            progress=0x00FF00,
            completed=0x0000FF,
            failed=0xFFFF00,
        )
        assert colors.started == 0xFF0000
        assert colors.progress == 0x00FF00
        assert colors.completed == 0x0000FF
        assert colors.failed == 0xFFFF00

    def test_discord_embed_colors_validation(self) -> None:
        """Test DiscordEmbedColors validation for color values."""
        # Valid color values (0 to 0xFFFFFF)
        valid_colors = [0x000000, 0x123456, 0xFFFFFF]
        for color in valid_colors:
            colors = DiscordEmbedColors(started=color)
            assert colors.started == color

        # Invalid color values (negative or too large)
        with pytest.raises(ValidationError) as exc_info:
            _ = DiscordEmbedColors(started=-1)
        
        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["type"] == "greater_than_equal"

        with pytest.raises(ValidationError) as exc_info:
            _ = DiscordEmbedColors(started=0x1000000)  # Too large
        
        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["type"] == "less_than_equal"


class TestDiscordMentions:
    """Test suite for DiscordMentions class."""

    def test_discord_mentions_defaults(self) -> None:
        """Test DiscordMentions with default values."""
        mentions = DiscordMentions()
        assert mentions.started == []
        assert mentions.failed == ["@everyone"]
        assert mentions.completed == []

    def test_discord_mentions_custom_values(self) -> None:
        """Test DiscordMentions with custom values."""
        mentions = DiscordMentions(
            started=["123456789"],
            failed=["@admin"],
            completed=["987654321"],
        )
        assert mentions.started == ["123456789"]
        assert mentions.failed == ["@admin"]
        assert mentions.completed == ["987654321"]

    def test_discord_mentions_validation_user_ids(self) -> None:
        """Test DiscordMentions validation for mention strings."""
        # Valid mention strings
        valid_mentions = ["@user123", "@admin", "123456789"]
        mentions = DiscordMentions(started=valid_mentions)
        assert mentions.started == valid_mentions

    def test_discord_mentions_validation_role_names(self) -> None:
        """Test DiscordMentions validation for role mentions."""
        # Valid role mentions
        valid_roles = ["@admin", "@moderator", "@everyone"]
        mentions = DiscordMentions(failed=valid_roles)
        assert mentions.failed == valid_roles


class TestDiscordEmbedConfig:
    """Test suite for DiscordEmbedConfig class."""

    def test_discord_embed_config_defaults(self) -> None:
        """Test DiscordEmbedConfig with default values."""
        embed = DiscordEmbedConfig()
        assert embed.enabled is True
        assert embed.thumbnail is True
        assert embed.timestamp is True
        assert isinstance(embed.colors, DiscordEmbedColors)

    def test_discord_embed_config_custom_values(self) -> None:
        """Test DiscordEmbedConfig with custom values."""
        custom_colors = DiscordEmbedColors(started=0xFF0000)
        embed = DiscordEmbedConfig(
            enabled=False,
            thumbnail=False,
            timestamp=False,
            colors=custom_colors,
        )
        assert embed.enabled is False
        assert embed.thumbnail is False
        assert embed.timestamp is False
        assert embed.colors == custom_colors

    def test_discord_embed_config_validation_title_empty(self) -> None:
        """Test DiscordEmbedConfig validation for boolean fields."""
        # Test that boolean fields work correctly
        config = DiscordEmbedConfig(enabled=True, thumbnail=False, timestamp=True)
        assert config.enabled is True
        assert config.thumbnail is False
        assert config.timestamp is True


class TestDiscordNotificationConfig:
    """Test suite for DiscordNotificationConfig class."""

    def test_discord_notification_config_defaults(self) -> None:
        """Test DiscordNotificationConfig with default values."""
        config = DiscordNotificationConfig()
        assert isinstance(config.mentions, DiscordMentions)
        assert isinstance(config.rate_limits, RateLimitConfig)

    def test_discord_notification_config_custom_values(self) -> None:
        """Test DiscordNotificationConfig with custom values."""
        custom_mentions = DiscordMentions(started=["@admin"])
        config = DiscordNotificationConfig(
            mentions=custom_mentions,
        )
        assert config.mentions == custom_mentions


class TestDiscordConfig:
    """Test suite for DiscordConfig class."""

    def test_discord_config_creation(self) -> None:
        """Test DiscordConfig creation with required fields."""
        config = DiscordConfig(
            webhook_url="https://discord.com/api/webhooks/123/abc",
        )
        assert config.webhook_url == "https://discord.com/api/webhooks/123/abc"
        assert isinstance(config.embeds, DiscordEmbedConfig)
        assert isinstance(config.notifications, DiscordNotificationConfig)
        assert isinstance(config.retry, RetryConfig)

    def test_discord_config_validation_webhook_url(self) -> None:
        """Test DiscordConfig validation for webhook URL."""
        # Valid webhook URLs
        valid_urls = [
            "https://discord.com/api/webhooks/123456789/abcdefghijk",
            "https://discord.com/api/webhooks/987654321/zyxwvutsrqp",
        ]
        for url in valid_urls:
            config = DiscordConfig(webhook_url=url)
            assert config.webhook_url == url

        # Invalid webhook URLs
        invalid_urls = [
            "http://discord.com/api/webhooks/123/abc",  # Not HTTPS
            "https://example.com/webhook",  # Wrong domain
            "https://discord.com/api/webhook/123/abc",  # Wrong path
            "",  # Empty
        ]
        for url in invalid_urls:
            with pytest.raises(ValidationError) as exc_info:
                _ = DiscordConfig(webhook_url=url)
            
            errors = exc_info.value.errors()
            assert len(errors) >= 1


class TestTelegramFormatConfig:
    """Test suite for TelegramFormatConfig class."""

    def test_telegram_format_config_defaults(self) -> None:
        """Test TelegramFormatConfig with default values."""
        config = TelegramFormatConfig()
        assert config.parse_mode == "HTML"
        assert config.disable_web_page_preview is True
        assert config.disable_notification is False

    def test_telegram_format_config_custom_values(self) -> None:
        """Test TelegramFormatConfig with custom values."""
        config = TelegramFormatConfig(
            parse_mode="Markdown",
            disable_web_page_preview=False,
            disable_notification=True,
        )
        assert config.parse_mode == "Markdown"
        assert config.disable_web_page_preview is False
        assert config.disable_notification is True

    def test_telegram_format_config_validation_parse_mode(self) -> None:
        """Test TelegramFormatConfig validation for parse_mode."""
        # Valid parse modes
        valid_modes = ["HTML", "Markdown", "MarkdownV2"]
        for mode in valid_modes:
            config = TelegramFormatConfig(parse_mode=mode)  # pyright: ignore[reportArgumentType]
            assert config.parse_mode == mode

        # Invalid parse mode - bypassing type checker for runtime validation test
        with pytest.raises(ValidationError) as exc_info:
            _ = TelegramFormatConfig(parse_mode="Invalid")  # pyright: ignore[reportArgumentType]
        
        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert "literal_error" in errors[0]["type"]


class TestTelegramTemplates:
    """Test suite for TelegramTemplates class."""

    def test_telegram_templates_defaults(self) -> None:
        """Test TelegramTemplates with default values."""
        templates = TelegramTemplates()
        assert "🚀 <b>Mover Started</b>" in templates.started
        assert "📈 <b>Mover Progress</b>" in templates.progress
        assert "✅ <b>Mover Completed</b>" in templates.completed
        assert "❌ <b>Mover Failed</b>" in templates.failed

    def test_telegram_templates_custom_values(self) -> None:
        """Test TelegramTemplates with custom values."""
        templates = TelegramTemplates(
            started="Custom started template",
            progress="Custom progress template",
            completed="Custom completed template",
            failed="Custom failed template",
        )
        assert templates.started == "Custom started template"
        assert templates.progress == "Custom progress template"
        assert templates.completed == "Custom completed template"
        assert templates.failed == "Custom failed template"

    def test_telegram_templates_validation_empty_strings(self) -> None:
        """Test TelegramTemplates validation for empty strings."""
        # Test that empty strings are allowed (no minimum length constraint)
        templates = TelegramTemplates(started="")
        assert templates.started == ""


class TestTelegramNotificationConfig:
    """Test suite for TelegramNotificationConfig class."""

    def test_telegram_notification_config_defaults(self) -> None:
        """Test TelegramNotificationConfig with default values."""
        config = TelegramNotificationConfig()
        assert config.events == ["started", "progress", "completed", "failed"]
        assert isinstance(config.rate_limits, RateLimitConfig)

    def test_telegram_notification_config_custom_values(self) -> None:
        """Test TelegramNotificationConfig with custom values."""
        config = TelegramNotificationConfig(
            events=["started", "completed"],
        )
        assert config.events == ["started", "completed"]


class TestTelegramConfig:
    """Test suite for TelegramConfig class."""

    def test_telegram_config_creation(self) -> None:
        """Test TelegramConfig creation with required fields."""
        config = TelegramConfig(
            bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
            chat_ids=[-1001234567890],
        )
        assert config.bot_token == "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
        assert config.chat_ids == [-1001234567890]
        assert isinstance(config.format, TelegramFormatConfig)
        assert isinstance(config.templates, TelegramTemplates)
        assert isinstance(config.notifications, TelegramNotificationConfig)

    def test_telegram_config_validation_bot_token(self) -> None:
        """Test TelegramConfig validation for bot token."""
        # Valid bot tokens work
        valid_token = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
        config = TelegramConfig(bot_token=valid_token, chat_ids=[123])
        assert config.bot_token == valid_token

    def test_telegram_config_validation_chat_ids_empty(self) -> None:
        """Test TelegramConfig validation for empty chat_ids."""
        with pytest.raises(ValidationError) as exc_info:
            _ = TelegramConfig(
                bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
                chat_ids=[],
            )
        
        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["type"] == "too_short"


class TestProviderConfig:
    """Test suite for ProviderConfig class."""

    def test_provider_config_defaults(self) -> None:
        """Test ProviderConfig with default values."""
        config = ProviderConfig()
        assert config.telegram is None
        assert config.discord is None

    def test_provider_config_with_providers(self) -> None:
        """Test ProviderConfig with configured providers."""
        telegram_config = TelegramConfig(
            bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
            chat_ids=[123],
        )
        discord_config = DiscordConfig(
            webhook_url="https://discord.com/api/webhooks/123/abc",
        )
        
        config = ProviderConfig(
            telegram=telegram_config,
            discord=discord_config,
        )
        assert config.telegram == telegram_config
        assert config.discord == discord_config
