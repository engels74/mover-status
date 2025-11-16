"""Tests for Discord configuration schema."""

import pytest
from pydantic import ValidationError

from mover_status.plugins.discord.config import DiscordConfig


class TestDiscordConfig:
    """DiscordConfig validation scenarios."""

    def test_valid_configuration(self) -> None:
        """Configuration accepts valid HTTPS webhook with extras."""
        config = DiscordConfig.model_validate(
            {
                "webhook_url": "https://discord.com/api/webhooks/123456789012345678/abcdef",
                "username": "  Mover Bot ",
                "embed_color": "0x5865F2",
            }
        )

        assert config.webhook_url.startswith("https://discord.com/api/webhooks/")
        assert config.username == "Mover Bot"
        assert config.embed_color == 0x5865F2

    def test_accepts_subdomain_hosts(self) -> None:
        """Canary/PTB webhook hosts are allowed."""
        config = DiscordConfig(
            webhook_url="https://ptb.discordapp.com/api/webhooks/1/test-token",
        )

        assert config.webhook_url.startswith("https://ptb.discordapp.com")

    def test_rejects_non_https_scheme(self) -> None:
        """Webhook must be HTTPS."""
        with pytest.raises(ValidationError) as exc_info:
            _ = DiscordConfig(
                webhook_url="http://discord.com/api/webhooks/1/token",
            )
        assert "HTTPS" in str(exc_info.value)

    def test_rejects_invalid_domain(self) -> None:
        """Webhook host must be Discord-owned."""
        with pytest.raises(ValidationError) as exc_info:
            _ = DiscordConfig(
                webhook_url="https://example.com/api/webhooks/1/token",
            )
        assert "discord.com" in str(exc_info.value)

    def test_rejects_invalid_path(self) -> None:
        """Webhook path must include /api/webhooks/<id>/<token>."""
        with pytest.raises(ValidationError) as exc_info:
            _ = DiscordConfig(
                webhook_url="https://discord.com/api/hooks/1/token",
            )
        assert "/api/webhooks" in str(exc_info.value)

    def test_blank_username_not_allowed(self) -> None:
        """Username cannot be blank when specified."""
        with pytest.raises(ValidationError):
            _ = DiscordConfig(
                webhook_url="https://discord.com/api/webhooks/1/token",
                username="   ",
            )

    def test_invalid_embed_color_string(self) -> None:
        """Invalid hex string triggers validation error."""
        with pytest.raises(ValidationError):
            _ = DiscordConfig.model_validate(
                {
                    "webhook_url": "https://discord.com/api/webhooks/1/token",
                    "embed_color": "zzzzzz",
                }
            )
