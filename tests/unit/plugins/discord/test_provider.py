"""Tests for Discord provider."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

from mover_status.plugins.discord.provider import DiscordProvider
from mover_status.notifications.models.message import Message


class TestDiscordProvider:
    """Test cases for Discord provider."""

    @pytest.fixture
    def valid_config(self) -> dict[str, object]:
        """Valid Discord provider configuration."""
        return {
            "webhook_url": "https://discord.com/api/webhooks/123/abc",
            "username": "Test Bot",
            "avatar_url": "https://example.com/avatar.png",
            "timeout": 30.0,
            "max_retries": 3,
            "retry_delay": 1.0,
            "enabled": True,
        }

    @pytest.fixture
    def sample_message(self) -> Message:
        """Sample notification message."""
        return Message(
            title="Test Notification",
            content="This is a test notification",
            priority="normal",
            tags=["test", "notification"],
            metadata={"source": "test", "environment": "dev"},
        )

    def test_init_with_valid_config(self, valid_config: dict[str, object]) -> None:
        """Test Discord provider initialization with valid config."""
        provider = DiscordProvider(valid_config)
        
        assert provider.get_provider_name() == "discord"
        assert provider.is_enabled() is True
        assert provider.webhook_client is not None
        assert provider.webhook_client.webhook_url == valid_config["webhook_url"]
        assert provider.webhook_client.username == valid_config["username"]
        assert provider.webhook_client.avatar_url == valid_config["avatar_url"]

    def test_init_with_minimal_config(self) -> None:
        """Test Discord provider initialization with minimal config."""
        config = {
            "webhook_url": "https://discord.com/api/webhooks/123/abc",
        }
        provider = DiscordProvider(config)
        
        assert provider.get_provider_name() == "discord"
        assert provider.is_enabled() is True
        assert provider.webhook_client.username is None
        assert provider.webhook_client.avatar_url is None

    def test_init_disabled(self) -> None:
        """Test Discord provider initialization when disabled."""
        config = {
            "webhook_url": "https://discord.com/api/webhooks/123/abc",
            "enabled": False,
        }
        provider = DiscordProvider(config)
        
        assert provider.is_enabled() is False

    def test_validate_config_missing_webhook_url(self) -> None:
        """Test validation fails when webhook_url is missing."""
        config: dict[str, object] = {}
        
        with pytest.raises(ValueError, match="webhook_url is required"):
            _ = DiscordProvider(config)

    def test_validate_config_invalid_webhook_url(self) -> None:
        """Test validation fails with invalid webhook URL."""
        config = {
            "webhook_url": "https://example.com/not-discord",
        }
        
        with pytest.raises(ValueError, match="must be a Discord webhook URL"):
            _ = DiscordProvider(config)

    def test_validate_config_invalid_timeout(self) -> None:
        """Test validation fails with invalid timeout."""
        config = {
            "webhook_url": "https://discord.com/api/webhooks/123/abc",
            "timeout": -1.0,
        }
        
        with pytest.raises(ValueError, match="timeout must be positive"):
            _ = DiscordProvider(config)

    def test_validate_config_invalid_max_retries(self) -> None:
        """Test validation fails with invalid max_retries."""
        config = {
            "webhook_url": "https://discord.com/api/webhooks/123/abc",
            "max_retries": -1,
        }
        
        with pytest.raises(ValueError, match="max_retries must be non-negative"):
            _ = DiscordProvider(config)

    def test_validate_config_invalid_retry_delay(self) -> None:
        """Test validation fails with invalid retry_delay."""
        config = {
            "webhook_url": "https://discord.com/api/webhooks/123/abc",
            "retry_delay": -1.0,
        }
        
        with pytest.raises(ValueError, match="retry_delay must be non-negative"):
            _ = DiscordProvider(config)

    def test_validate_config_invalid_timeout_type(self) -> None:
        """Test validation fails with invalid timeout type."""
        config = {
            "webhook_url": "https://discord.com/api/webhooks/123/abc",
            "timeout": "not_a_number",
        }
        
        with pytest.raises(ValueError, match="Invalid timeout value"):
            _ = DiscordProvider(config)

    @pytest.mark.asyncio
    async def test_send_notification_success(
        self, 
        valid_config: dict[str, object],
        sample_message: Message,
    ) -> None:
        """Test successful notification sending."""
        provider = DiscordProvider(valid_config)
        
        with patch.object(provider.webhook_client, 'send_message', new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True
            
            result = await provider.send_notification(sample_message)
            
            assert result is True
            mock_send.assert_called_once()
            
            # Verify embed creation
            call_args = mock_send.call_args
            assert call_args is not None
            embeds_arg = call_args[1]["embeds"]  # pyright: ignore[reportAny]
            assert embeds_arg is not None
            assert len(embeds_arg) == 1  # pyright: ignore[reportAny]
            
            embed = embeds_arg[0]  # pyright: ignore[reportAny]
            assert embed.title == sample_message.title  # pyright: ignore[reportAny]
            assert embed.description == sample_message.content  # pyright: ignore[reportAny]
            assert embed.color == 0x0099FF  # Blue for normal priority  # pyright: ignore[reportAny]

    @pytest.mark.asyncio
    async def test_send_notification_failure(
        self, 
        valid_config: dict[str, object],
        sample_message: Message,
    ) -> None:
        """Test notification sending failure."""
        provider = DiscordProvider(valid_config)
        
        with patch.object(provider.webhook_client, 'send_message', new_callable=AsyncMock) as mock_send:
            mock_send.return_value = False
            
            result = await provider.send_notification(sample_message)
            
            assert result is False
            mock_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_notification_exception(
        self, 
        valid_config: dict[str, object],
        sample_message: Message,
    ) -> None:
        """Test notification sending with exception."""
        provider = DiscordProvider(valid_config)
        
        with patch.object(provider.webhook_client, 'send_message', new_callable=AsyncMock) as mock_send:
            mock_send.side_effect = Exception("Network error")
            
            result = await provider.send_notification(sample_message)
            
            assert result is False
            mock_send.assert_called_once()

    def test_create_embed_with_tags(
        self, 
        valid_config: dict[str, object],
        sample_message: Message,
    ) -> None:
        """Test embed creation with tags."""
        provider = DiscordProvider(valid_config)
        
        embed = provider._create_embed(sample_message)  # pyright: ignore[reportPrivateUsage]
        
        assert embed.title == sample_message.title
        assert embed.description == sample_message.content
        assert embed.color == 0x0099FF  # Blue for normal priority
        
        # Check for tags field
        tags_field = next((f for f in embed.fields if f["name"] == "Tags"), None)
        assert tags_field is not None
        assert tags_field["value"] == "test, notification"

    def test_create_embed_priority_colors(self, valid_config: dict[str, object]) -> None:
        """Test embed creation with different priority colors."""
        provider = DiscordProvider(valid_config)
        
        # Test different priorities - each separate to avoid type issues
        message_low = Message(title="Test", content="Test content", priority="low")
        embed_low = provider._create_embed(message_low)  # pyright: ignore[reportPrivateUsage]
        assert embed_low.color == 0x00FF00  # Green
        
        message_normal = Message(title="Test", content="Test content", priority="normal")
        embed_normal = provider._create_embed(message_normal)  # pyright: ignore[reportPrivateUsage]
        assert embed_normal.color == 0x0099FF  # Blue
        
        message_high = Message(title="Test", content="Test content", priority="high")
        embed_high = provider._create_embed(message_high)  # pyright: ignore[reportPrivateUsage]
        assert embed_high.color == 0xFF9900  # Orange
        
        message_urgent = Message(title="Test", content="Test content", priority="urgent")
        embed_urgent = provider._create_embed(message_urgent)  # pyright: ignore[reportPrivateUsage]
        assert embed_urgent.color == 0xFF0000  # Red

    def test_create_embed_with_metadata(self, valid_config: dict[str, object]) -> None:
        """Test embed creation with metadata fields."""
        provider = DiscordProvider(valid_config)
        
        message = Message(
            title="Test",
            content="Test content",
            metadata={"source": "test", "environment": "dev", "version": "1.0.0"},
        )
        
        embed = provider._create_embed(message)  # pyright: ignore[reportPrivateUsage]
        
        # Check for metadata fields
        source_field = next((f for f in embed.fields if f["name"] == "Source"), None)
        assert source_field is not None
        assert source_field["value"] == "test"
        
        env_field = next((f for f in embed.fields if f["name"] == "Environment"), None)
        assert env_field is not None
        assert env_field["value"] == "dev"

    def test_create_embed_field_limit(self, valid_config: dict[str, object]) -> None:
        """Test embed creation respects field limits."""
        provider = DiscordProvider(valid_config)
        
        # Create message with many metadata fields
        metadata = {f"field_{i}": f"value_{i}" for i in range(30)}
        message = Message(
            title="Test",
            content="Test content",
            tags=["tag1", "tag2"],
            metadata=metadata,
        )
        
        embed = provider._create_embed(message)  # pyright: ignore[reportPrivateUsage]
        
        # Should have at most 25 fields (Discord limit)
        assert len(embed.fields) <= 25

    def test_get_provider_name(self, valid_config: dict[str, object]) -> None:
        """Test provider name retrieval."""
        provider = DiscordProvider(valid_config)
        assert provider.get_provider_name() == "discord"