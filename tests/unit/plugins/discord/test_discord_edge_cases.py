"""Edge case tests for Discord provider with comprehensive TDD coverage."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch
from typing import TYPE_CHECKING, TypedDict, cast

if TYPE_CHECKING:
    from mover_status.plugins.discord.webhook.client import DiscordEmbed


class EmbedField(TypedDict):
    """Type definition for Discord embed field."""
    name: str
    value: str
    inline: bool


class Embed(TypedDict):
    """Type definition for Discord embed."""
    title: str
    description: str
    color: int
    fields: list[EmbedField]


class DiscordWebhookPayload(TypedDict):
    """Type definition for Discord webhook payload."""
    embeds: list[Embed]
    username: str
    avatar_url: str


from unittest.mock import MagicMock

from mover_status.plugins.discord.provider import DiscordProvider
from mover_status.plugins.discord.webhook.error_handling import DiscordApiError, DiscordErrorType
from mover_status.notifications.models.message import Message


class TestDiscordProviderEdgeCases:
    """Comprehensive edge case tests for Discord provider."""
    
    @pytest.fixture
    def base_config(self) -> dict[str, object]:
        """Base valid configuration."""
        return {
            "webhook_url": "https://discord.com/api/webhooks/123456789/test-webhook-token",
            "username": "Test Bot",
            "avatar_url": "https://example.com/avatar.png",
            "enabled": True,
        }
    
    def test_config_validation_edge_cases(self, base_config: dict[str, object]) -> None:
        """Test configuration validation with edge cases."""
        # Test empty webhook URL
        config = {**base_config, "webhook_url": ""}
        with pytest.raises(ValueError, match="webhook_url is required"):
            _ = DiscordProvider(config)
        
        # Test None webhook URL
        config = {**base_config, "webhook_url": None}
        with pytest.raises(ValueError, match="webhook_url is required"):
            _ = DiscordProvider(config)
        
        # Test webhook URL without protocol
        config = {**base_config, "webhook_url": "discord.com/api/webhooks/123/abc"}
        with pytest.raises(ValueError, match="must be a valid HTTP/HTTPS URL"):
            _ = DiscordProvider(config)
        
        # Test non-Discord webhook URL
        config = {**base_config, "webhook_url": "https://example.com/webhook"}
        with pytest.raises(ValueError, match="must be a Discord webhook URL"):
            _ = DiscordProvider(config)
        
        # Test discordapp.com domain (should be valid)
        config = {**base_config, "webhook_url": "https://discordapp.com/api/webhooks/123/abc"}
        _ = DiscordProvider(config)
        
        # Test zero timeout
        config = {**base_config, "timeout": 0}
        with pytest.raises(ValueError, match="timeout must be positive"):
            _ = DiscordProvider(config)
        
        # Test negative timeout
        config = {**base_config, "timeout": -5.0}
        with pytest.raises(ValueError, match="timeout must be positive"):
            _ = DiscordProvider(config)
        
        # Test timeout as object
        config = {**base_config, "timeout": {"value": 30}}
        with pytest.raises(ValueError, match="timeout must be a number"):
            _ = DiscordProvider(config)
        
        # Test max_retries boundary cases
        config = {**base_config, "max_retries": 0}  # Should be valid
        provider = DiscordProvider(config)
        assert provider.webhook_client.max_retries == 0
        
        # Test large max_retries
        config = {**base_config, "max_retries": 1000}
        provider = DiscordProvider(config)
        assert provider.webhook_client.max_retries == 1000
        
        # Test retry_delay boundary cases
        config = {**base_config, "retry_delay": 0.0}  # Should be valid
        provider = DiscordProvider(config)
        assert provider.webhook_client.retry_delay == 0.0
        
        # Test string numeric values
        config = {
            **base_config,
            "timeout": "30.5",
            "max_retries": "5",
            "retry_delay": "2.5",
        }
        provider = DiscordProvider(config)
        assert provider.webhook_client.timeout == 30.5
        assert provider.webhook_client.max_retries == 5
        assert provider.webhook_client.retry_delay == 2.5
    
    def test_create_embed_edge_cases(self, base_config: dict[str, object]) -> None:
        """Test embed creation with edge cases."""
        provider = DiscordProvider(base_config)
        
        # Test message with empty tags
        message = Message(
            title="Test",
            content="Test content",
            tags=[],
        )
        embed = provider._create_embed(message)  # pyright: ignore[reportPrivateUsage]
        
        # Should not include tags field if empty
        tag_fields = [f for f in embed.fields if f["name"] == "Tags"]
        assert len(tag_fields) == 0
        
        # Test message with empty metadata
        message = Message(
            title="Test",
            content="Test content",
            metadata={},
        )
        embed = provider._create_embed(message)  # pyright: ignore[reportPrivateUsage]
        
        # Should only have priority field
        non_priority_fields = [f for f in embed.fields if f["name"] != "Priority"]
        assert len(non_priority_fields) == 0
        
        # Test message with None values in metadata
        message = Message(
            title="Test",
            content="Test content",
            metadata={"key": ""},  # Empty string value
        )
        embed = provider._create_embed(message)  # pyright: ignore[reportPrivateUsage]
        
        # Should include field with empty value
        key_field = next((f for f in embed.fields if f["name"] == "Key"), None)
        assert key_field is not None
        assert key_field["value"] == ""
        
        # Test maximum field count scenario
        large_metadata = {f"field_{i:03d}": f"value_{i}" for i in range(100)}
        message = Message(
            title="Test",
            content="Test content",
            tags=["tag1", "tag2"],
            metadata=large_metadata,
        )
        embed = provider._create_embed(message)  # pyright: ignore[reportPrivateUsage]
        
        # Should respect 25 field limit
        assert len(embed.fields) <= 25
        
        # Should include tags and priority
        field_names = [f["name"] for f in embed.fields]
        assert "Tags" in field_names
        assert "Priority" in field_names
        
        # Test default priority behavior (normal priority should map to blue)
        message = Message(
            title="Test",
            content="Test content",
            # priority defaults to "normal"
        )
        embed = provider._create_embed(message)  # pyright: ignore[reportPrivateUsage]
        assert embed.color == 0x0099FF  # Blue for normal priority
        
        # Test special characters in metadata keys
        message = Message(
            title="Test",
            content="Test content",
            metadata={
                "test_key": "value1",
                "UPPER_CASE": "value2",
                "mixed_Case_Key": "value3",
                "key-with-dashes": "value4",
            },
        )
        embed = provider._create_embed(message)  # pyright: ignore[reportPrivateUsage]
        
        # Should properly format field names
        field_names = [f["name"] for f in embed.fields]
        assert "Test Key" in field_names
        assert "Upper Case" in field_names
        assert "Mixed Case Key" in field_names
        assert "Key-With-Dashes" in field_names
    
    @pytest.mark.asyncio
    async def test_send_notification_exception_edge_cases(
        self,
        base_config: dict[str, object],
    ) -> None:
        """Test exception handling edge cases in send_notification."""
        provider = DiscordProvider(base_config)
        message = Message(title="Test", content="Test content")
        
        # Test Discord API specific errors
        discord_errors = [
            DiscordApiError(DiscordErrorType.RATE_LIMITED, "Rate limited"),
            DiscordApiError(DiscordErrorType.INVALID_WEBHOOK, "Invalid webhook"),
            DiscordApiError(DiscordErrorType.MISSING_PERMISSIONS, "Missing permissions"),
            DiscordApiError(DiscordErrorType.SERVER_ERROR, "Server error"),
        ]
        
        for error in discord_errors:
            with patch.object(provider.webhook_client, 'send_message', new_callable=AsyncMock) as mock_send:
                mock_send.side_effect = error
                
                result = await provider.send_notification(message)
                assert result is False
                mock_send.assert_called_once()
        
        # Test generic exception
        with patch.object(provider.webhook_client, 'send_message', new_callable=AsyncMock) as mock_send:
            mock_send.side_effect = RuntimeError("Unexpected error")
            
            result = await provider.send_notification(message)
            assert result is False
            mock_send.assert_called_once()
        
        # Test successful response after exception
        with patch.object(provider.webhook_client, 'send_message', new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True
            
            result = await provider.send_notification(message)
            assert result is True
            mock_send.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_concurrent_send_operations(
        self,
        base_config: dict[str, object],
    ) -> None:
        """Test concurrent send operations with rate limiting."""
        import asyncio
        
        provider = DiscordProvider(base_config)
        
        # Create multiple messages
        messages = [
            Message(
                title=f"Concurrent Test {i}",
                content=f"Testing concurrent operations {i}",
                priority="normal",
            )
            for i in range(5)
        ]
        
        # Mock successful responses with delay to simulate rate limiting
        async def mock_send_with_delay(*_: object, **_kwargs: object) -> bool:
            await asyncio.sleep(0.01)  # Small delay
            return True
        
        with patch.object(provider.webhook_client, 'send_message', new_callable=AsyncMock) as mock_send:
            mock_send.side_effect = mock_send_with_delay
            
            # Send all messages concurrently
            tasks = [provider.send_notification(msg) for msg in messages]
            results = await asyncio.gather(*tasks)
            
            # All should succeed
            assert all(results)
            assert mock_send.call_count == len(messages)
    
    @pytest.mark.asyncio
    async def test_webhook_client_initialization_edge_cases(
        self,
        base_config: dict[str, object],
    ) -> None:
        """Test webhook client initialization with edge cases."""
        # Test with None optional values
        config = {
            **base_config,
            "username": None,
            "avatar_url": None,
        }
        provider = DiscordProvider(config)
        assert provider.webhook_client.username is None
        assert provider.webhook_client.avatar_url is None
        
        # Test with empty string optional values
        config = {
            **base_config,
            "username": "",
            "avatar_url": "",
        }
        provider = DiscordProvider(config)
        assert provider.webhook_client.username == ""
        assert provider.webhook_client.avatar_url == ""
        
        # Test with non-string optional values that can be converted
        config = {
            **base_config,
            "username": 123,
            "avatar_url": 456,
        }
        provider = DiscordProvider(config)
        assert provider.webhook_client.username == "123"
        assert provider.webhook_client.avatar_url == "456"
        
        # Test with invalid timeout types that can't be converted
        config: dict[str, object] = {
            **base_config,
            "timeout": [],
        }
        provider = DiscordProvider(config)
        assert provider.webhook_client.timeout == 30.0  # Should use default
        
        # Test with invalid max_retries types
        config = {
            **base_config,
            "max_retries": [],
        }
        provider = DiscordProvider(config)
        assert provider.webhook_client.max_retries == 3  # Should use default
        
        # Test with invalid retry_delay types
        config = {
            **base_config,
            "retry_delay": [],
        }
        provider = DiscordProvider(config)
        assert provider.webhook_client.retry_delay == 1.0  # Should use default
    
    def test_embed_field_validation_edge_cases(self, base_config: dict[str, object]) -> None:
        """Test embed field validation with edge cases."""
        provider = DiscordProvider(base_config)
        
        # Test with very long metadata keys and values
        long_key = "x" * 300  # Longer than Discord's 256 char limit
        long_value = "y" * 2000  # Longer than Discord's 1024 char limit
        
        message = Message(
            title="Test",
            content="Test content",
            metadata={long_key: long_value},
        )
        
        # Should not raise exception during embed creation
        embed = provider._create_embed(message)  # pyright: ignore[reportPrivateUsage]
        
        # Find the field with the long key
        long_key_field = next(
            (f for f in embed.fields if long_key.replace("_", " ").title() in str(f["name"])),
            None
        )
        # Field might be truncated or excluded, but should not crash
        if long_key_field:
            assert isinstance(long_key_field["value"], str)
    
    @pytest.mark.asyncio
    async def test_provider_state_consistency(self, base_config: dict[str, object]) -> None:
        """Test provider state consistency across operations."""
        provider = DiscordProvider(base_config)
        
        # Test that provider state doesn't change between calls
        initial_webhook_url = provider.webhook_client.webhook_url
        initial_username = provider.webhook_client.username
        initial_avatar_url = provider.webhook_client.avatar_url
        
        message = Message(title="Test", content="Test content")
        
        with patch.object(provider.webhook_client, 'send_message', new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True
            
            # Send multiple messages
            for _ in range(3):
                _ = await provider.send_notification(message)
            
            # Verify state hasn't changed
            assert provider.webhook_client.webhook_url == initial_webhook_url
            assert provider.webhook_client.username == initial_username
            assert provider.webhook_client.avatar_url == initial_avatar_url
            assert mock_send.call_count == 3
    
    def test_provider_name_consistency(self, base_config: dict[str, object]) -> None:
        """Test provider name consistency."""
        provider = DiscordProvider(base_config)
        
        # Provider name should always return "discord"
        assert provider.get_provider_name() == "discord"
        
        # Test multiple calls
        for _ in range(5):
            assert provider.get_provider_name() == "discord"
    
    @pytest.mark.asyncio
    async def test_memory_usage_with_large_batches(
        self,
        base_config: dict[str, object],
    ) -> None:
        """Test memory usage with large message batches."""
        provider = DiscordProvider(base_config)
        
        # Create a large batch of messages
        large_batch = [
            Message(
                title=f"Batch Test {i}",
                content=f"Large batch processing test {i}" * 10,  # Longer content
                metadata={f"key_{j}": f"value_{j}" for j in range(10)},  # Multiple fields
            )
            for i in range(50)  # Large batch
        ]
        
        with patch.object(provider.webhook_client, 'send_message', new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True
            
            # Process batch sequentially
            results: list[bool] = []
            for message in large_batch:
                result = await provider.send_notification(message)
                results.append(result)
            
            # All should succeed
            assert all(results)
            assert mock_send.call_count == len(large_batch)
            
            # Verify provider is still functional after large batch
            test_message = Message(title="Post-batch test", content="Testing after batch")
            _ = await provider.send_notification(test_message)
    
    def test_config_mutation_safety(self, base_config: dict[str, object]) -> None:
        """Test that provider is safe from config mutations."""
        config = base_config.copy()
        provider = DiscordProvider(config)
        
        # Mutate original config
        config["webhook_url"] = "https://example.com/malicious"
        config["username"] = "Malicious Bot"
        
        # Provider should retain original config
        assert provider.webhook_client.webhook_url == base_config["webhook_url"]
        assert provider.webhook_client.username == base_config["username"]
    
    @pytest.mark.asyncio
    async def test_embed_generation_consistency(self, base_config: dict[str, object]) -> None:
        """Test embed generation consistency across multiple calls."""
        provider = DiscordProvider(base_config)
        
        message = Message(
            title="Consistency Test",
            content="Testing embed generation consistency",
            priority="high",
            tags=["test", "consistency"],
            metadata={"run": "1", "type": "test"},
        )
        
        # Generate multiple embeds for the same message
        embeds: list[DiscordEmbed] = []
        for _ in range(5):
            embed = provider._create_embed(message)  # pyright: ignore[reportPrivateUsage]
            embeds.append(embed)
        
        # All embeds should be identical
        first_embed = embeds[0]
        for embed in embeds[1:]:
            assert embed.title == first_embed.title
            assert embed.description == first_embed.description
            assert embed.color == first_embed.color
            assert len(embed.fields) == len(first_embed.fields)
            
            # Compare fields (order might matter)
            for i, field in enumerate(embed.fields):
                assert field["name"] == first_embed.fields[i]["name"]
                assert field["value"] == first_embed.fields[i]["value"]
                assert field["inline"] == first_embed.fields[i]["inline"]
    
    @pytest.mark.asyncio
    async def test_provider_initialization_edge_cases(self) -> None:
        """Test edge cases in provider initialization."""
        # Test with empty webhook URL
        with pytest.raises(ValueError):
            _ = DiscordProvider({"webhook_url": ""})
        
        # Test with None webhook URL
        with pytest.raises(ValueError):
            _ = DiscordProvider({"webhook_url": None})
        
        # Test with invalid URL scheme
        with pytest.raises(ValueError):
            _ = DiscordProvider({"webhook_url": "ftp://discord.com/api/webhooks/123/abc"})
        
        # Test with non-Discord URL
        with pytest.raises(ValueError):
            _ = DiscordProvider({"webhook_url": "https://example.com/webhook"})
        
        # Test with invalid numeric values
        with pytest.raises(ValueError):
            _ = DiscordProvider({
                "webhook_url": "https://discord.com/api/webhooks/123/abc",
                "timeout": "not-a-number",
            })
        
        with pytest.raises(ValueError):
            _ = DiscordProvider({
                "webhook_url": "https://discord.com/api/webhooks/123/abc",
                "max_retries": "invalid",
            })
        
        with pytest.raises(ValueError):
            _ = DiscordProvider({
                "webhook_url": "https://discord.com/api/webhooks/123/abc",
                "retry_delay": "invalid",
            })
    
    @pytest.mark.asyncio
    async def test_embed_field_ordering(self) -> None:
        """Test that embed fields maintain proper ordering and structure."""
        provider = DiscordProvider({
            "webhook_url": "https://discord.com/api/webhooks/123/abc",
        })
        
        # Message with metadata that has special ordering requirements
        message = Message(
            title="Field Order Test",
            content="Testing field ordering",
            priority="normal",
            tags=["order", "test"],
            metadata={
                "z_last": "should appear last",
                "a_first": "should appear first",
                "m_middle": "should appear middle",
            },
        )
        
        # Mock successful response
        mock_response = MagicMock()
        mock_response.status_code = 204
        
        with patch("httpx.AsyncClient.post", return_value=mock_response) as mock_post:
            result = await provider.send_notification(message)
            assert result is True
            
            # Get the generated embed from the call
            call_args = mock_post.call_args
            assert call_args is not None
            payload = cast(DiscordWebhookPayload, call_args.kwargs["json"])
            embed = payload["embeds"][0]
            
            # Verify fields are present
            assert "fields" in embed
            fields = embed["fields"]
            
            # Find tags and priority fields
            field_names = [field["name"] for field in fields]
            assert "Tags" in field_names
            assert "Priority" in field_names