"""Integration tests for Discord provider end-to-end workflows."""

from __future__ import annotations

import asyncio
import pytest
from unittest.mock import patch, MagicMock
from typing import TYPE_CHECKING, Any
import httpx

from mover_status.plugins.discord.provider import DiscordProvider
from mover_status.notifications.models.message import Message
from mover_status.notifications.manager.dispatcher import AsyncDispatcher, DispatchStatus
from mover_status.notifications.base.registry import get_global_registry, ProviderMetadata

if TYPE_CHECKING:
    pass


class TestDiscordIntegration:
    """Integration tests for Discord provider workflows."""
    
    @pytest.fixture
    def discord_config(self) -> dict[str, object]:
        """Standard Discord configuration for testing."""
        return {
            "webhook_url": "https://discord.com/api/webhooks/123456789/test-webhook-token",
            "username": "Integration Test Bot",
            "avatar_url": "https://example.com/avatar.png",
            "timeout": 30.0,
            "max_retries": 3,
            "retry_delay": 1.0,
            "enabled": True,
        }
    
    @pytest.fixture
    def sample_messages(self) -> list[Message]:
        """Sample messages for testing various scenarios."""
        return [
            Message(
                title="System Alert",
                content="Critical system failure detected",
                priority="urgent",
                tags=["alert", "system", "critical"],
                metadata={"severity": "high", "component": "database"},
            ),
            Message(
                title="Transfer Complete",
                content="File transfer completed successfully",
                priority="normal",
                tags=["transfer", "success"],
                metadata={"size": "2.5GB", "duration": "45min"},
            ),
            Message(
                title="Maintenance Notice",
                content="Scheduled maintenance starting in 30 minutes",
                priority="low",
                tags=["maintenance", "scheduled"],
                metadata={"window": "1 hour", "impact": "minimal"},
            ),
        ]
    
    @pytest.mark.asyncio
    async def test_end_to_end_discord_notification_flow(
        self,
        discord_config: dict[str, object],
        sample_messages: list[Message],
    ) -> None:
        """Test complete Discord notification flow from provider to webhook."""
        # Setup mock HTTP responses
        mock_responses: list[MagicMock] = []
        for _ in sample_messages:
            mock_response = MagicMock()
            mock_response.status_code = 204
            mock_responses.append(mock_response)
        
        with patch("httpx.AsyncClient.post", side_effect=mock_responses) as mock_post:
            provider = DiscordProvider(discord_config)
            
            # Send each message and verify success
            for message in sample_messages:
                result = await provider.send_notification(message)
                assert result is True
            
            # Verify all HTTP calls were made
            assert mock_post.call_count == len(sample_messages)
            
            # Verify webhook calls contain proper embeds
            for i, call in enumerate(mock_post.call_args_list):
                payload: dict[str, Any] = call.kwargs["json"]
                assert "embeds" in payload
                assert len(payload["embeds"]) == 1
                
                embed: dict[str, Any] = payload["embeds"][0]
                assert embed["title"] == sample_messages[i].title
                assert embed["description"] == sample_messages[i].content
                
                # Verify priority color mapping
                expected_colors = {
                    "urgent": 0xFF0000,  # Red
                    "normal": 0x0099FF,  # Blue
                    "low": 0x00FF00,     # Green
                }
                expected_color = expected_colors[sample_messages[i].priority]
                assert embed["color"] == expected_color
    
    @pytest.mark.asyncio
    async def test_rate_limiting_integration(
        self,
        discord_config: dict[str, object],
    ) -> None:
        """Test rate limiting behavior under load."""
        # Create a provider with aggressive rate limiting for testing
        provider = DiscordProvider(discord_config)
        
        # Mock successful responses
        mock_response = MagicMock()
        mock_response.status_code = 204
        
        with patch("httpx.AsyncClient.post", return_value=mock_response) as mock_post:
            # Send messages rapidly to trigger rate limiting
            messages = [
                Message(
                    title=f"Rate Test {i}",
                    content=f"Testing rate limiting {i}",
                    priority="normal",
                )
                for i in range(10)
            ]
            
            # Send all messages concurrently
            tasks = [provider.send_notification(msg) for msg in messages]
            results = await asyncio.gather(*tasks)
            
            # All should succeed eventually
            assert all(results)
            assert mock_post.call_count == len(messages)
            
            # Verify rate limiter was used (timing would show delays)
            stats = provider.webhook_client.get_rate_limit_stats()
            assert isinstance(stats, dict)
            assert "requests_in_window" in stats
            assert stats["requests_in_window"] == len(messages)
    
    @pytest.mark.asyncio
    async def test_error_handling_integration(
        self,
        discord_config: dict[str, object],
    ) -> None:
        """Test error handling across different failure scenarios."""
        provider = DiscordProvider(discord_config)
        message = Message(
            title="Error Test",
            content="Testing error handling",
            priority="normal",
        )
        
        # Test various HTTP error scenarios
        error_scenarios: list[tuple[int, dict[str, str]]] = [
            # Rate limiting
            (429, {"retry-after": "30"}),
            # Invalid webhook
            (404, {}),
            # Missing permissions
            (403, {}),
            # Server error
            (500, {}),
            # Bad request
            (400, {}),
        ]
        
        for status_code, headers in error_scenarios:
            mock_response = MagicMock()
            mock_response.status_code = status_code
            mock_response.headers = headers
            mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                f"HTTP {status_code}",
                request=MagicMock(),
                response=mock_response,
            )
            
            with patch("httpx.AsyncClient.post", return_value=mock_response):
                result = await provider.send_notification(message)
                assert result is False
    
    @pytest.mark.asyncio
    async def test_network_error_integration(
        self,
        discord_config: dict[str, object],
    ) -> None:
        """Test network error handling integration."""
        provider = DiscordProvider(discord_config)
        message = Message(
            title="Network Test",
            content="Testing network errors",
            priority="normal",
        )
        
        # Test different network error types
        network_errors = [
            httpx.ConnectError("Connection failed"),
            httpx.TimeoutException("Request timeout"),
            httpx.NetworkError("Network unavailable"),
        ]
        
        for error in network_errors:
            with patch("httpx.AsyncClient.post", side_effect=error):
                result = await provider.send_notification(message)
                assert result is False
    
    @pytest.mark.asyncio
    async def test_dispatcher_integration(
        self,
        discord_config: dict[str, object],
    ) -> None:
        """Test Discord provider integration with notification dispatcher."""
        # Reset global registry
        get_global_registry().reset()
        
        # Register Discord provider
        registry = get_global_registry()
        metadata = ProviderMetadata(
            name="discord",
            description="Discord webhook provider",
            version="1.0.0",
            author="Integration Test",
            provider_class=DiscordProvider,
            tags=["discord", "webhook"],
        )
        registry.register_provider("discord", DiscordProvider, metadata)
        
        # Create dispatcher
        dispatcher = AsyncDispatcher(max_workers=2, queue_size=10)
        provider = DiscordProvider(discord_config)
        dispatcher.register_provider("discord", provider)
        
        await dispatcher.start()
        
        try:
            # Mock successful HTTP response
            mock_response = MagicMock()
            mock_response.status_code = 204
            
            with patch("httpx.AsyncClient.post", return_value=mock_response):
                message = Message(
                    title="Dispatcher Test",
                    content="Testing dispatcher integration",
                    priority="normal",
                )
                
                result = await dispatcher.dispatch_message(message, ["discord"])
                
                assert result.status == DispatchStatus.SUCCESS
                assert len(result.provider_results) == 1
                assert result.provider_results[0].success is True
                assert result.provider_results[0].provider_name == "discord"
        
        finally:
            await dispatcher.stop()
    
    @pytest.mark.asyncio
    async def test_concurrent_message_processing(
        self,
        discord_config: dict[str, object],
    ) -> None:
        """Test concurrent message processing with Discord provider."""
        provider = DiscordProvider(discord_config)
        
        # Create multiple messages
        messages = [
            Message(
                title=f"Concurrent Test {i}",
                content=f"Testing concurrent processing {i}",
                priority="normal",
                tags=[f"test_{i}"],
                metadata={"index": str(i)},
            )
            for i in range(20)
        ]
        
        # Mock successful responses
        mock_response = MagicMock()
        mock_response.status_code = 204
        
        with patch("httpx.AsyncClient.post", return_value=mock_response) as mock_post:
            # Process all messages concurrently
            tasks = [provider.send_notification(msg) for msg in messages]
            results = await asyncio.gather(*tasks)
            
            # All should succeed
            assert all(results)
            assert mock_post.call_count == len(messages)
            
            # Verify each message was processed correctly
            for call in mock_post.call_args_list:
                payload: dict[str, Any] = call.kwargs["json"]
                embed: dict[str, Any] = payload["embeds"][0]
                
                # Find corresponding message by title
                expected_message = next(
                    msg for msg in messages 
                    if msg.title == embed["title"]
                )
                
                assert embed["description"] == expected_message.content
                assert embed["color"] == 0x0099FF  # Normal priority
    
    @pytest.mark.asyncio
    async def test_large_message_handling(
        self,
        discord_config: dict[str, object],
    ) -> None:
        """Test handling of large messages that approach Discord limits."""
        provider = DiscordProvider(discord_config)
        
        # Create message with maximum field count
        large_metadata = {f"field_{i}": f"value_{i}" for i in range(50)}
        large_message = Message(
            title="Large Message Test",
            content="Testing large message handling with many fields",
            priority="normal",
            tags=["large", "test"],
            metadata=large_metadata,
        )
        
        mock_response = MagicMock()
        mock_response.status_code = 204
        
        with patch("httpx.AsyncClient.post", return_value=mock_response) as mock_post:
            result = await provider.send_notification(large_message)
            assert result is True
            
            # Verify field limiting was applied
            payload: dict[str, Any] = mock_post.call_args.kwargs["json"]
            embed: dict[str, Any] = payload["embeds"][0]
            
            # Discord has a 25 field limit, but we reserve space for tags and priority
            # So total should be <= 25
            assert len(embed["fields"]) <= 25
            
            # Verify tags and priority fields are present
            field_names: list[str] = [str(field["name"]) for field in embed["fields"]]
            assert "Tags" in field_names
            assert "Priority" in field_names
    
    @pytest.mark.asyncio
    async def test_webhook_validation_integration(
        self,
        discord_config: dict[str, object],
    ) -> None:
        """Test webhook validation during provider initialization."""
        # Test invalid webhook URLs
        invalid_configs = [
            {**discord_config, "webhook_url": "https://example.com/not-discord"},
            {**discord_config, "webhook_url": "invalid-url"},
            {**discord_config, "webhook_url": ""},
            {**discord_config, "webhook_url": None},
        ]
        
        for config in invalid_configs:
            with pytest.raises(ValueError):
                _ = DiscordProvider(config)
    
    @pytest.mark.asyncio
    async def test_configuration_validation_integration(
        self,
        discord_config: dict[str, object],
    ) -> None:
        """Test configuration validation with various parameter combinations."""
        # Test valid configurations
        valid_configs = [
            # Minimal config
            {"webhook_url": "https://discord.com/api/webhooks/123/abc"},
            # With string numbers
            {
                **discord_config,
                "timeout": "30.0",
                "max_retries": "3",
                "retry_delay": "1.0",
            },
            # With integer numbers
            {
                **discord_config,
                "timeout": 30,
                "max_retries": 3,
                "retry_delay": 1,
            },
        ]
        
        for config in valid_configs:
            provider = DiscordProvider(config)
            assert provider.get_provider_name() == "discord"
        
        # Test invalid configurations
        invalid_configs = [
            # Negative timeout
            {**discord_config, "timeout": -1.0},
            # Negative max_retries
            {**discord_config, "max_retries": -1},
            # Negative retry_delay
            {**discord_config, "retry_delay": -1.0},
            # Invalid timeout type
            {**discord_config, "timeout": "invalid"},
            # Invalid max_retries type
            {**discord_config, "max_retries": "invalid"},
            # Invalid retry_delay type
            {**discord_config, "retry_delay": "invalid"},
        ]
        
        for config in invalid_configs:
            with pytest.raises(ValueError):
                _ = DiscordProvider(config)
    
    @pytest.mark.asyncio
    async def test_retry_mechanism_integration(
        self,
        discord_config: dict[str, object],
    ) -> None:
        """Test retry mechanism with various failure scenarios."""
        provider = DiscordProvider(discord_config)
        message = Message(
            title="Retry Test",
            content="Testing retry mechanism",
            priority="normal",
        )
        
        # Test scenario: First few attempts fail, then succeed
        responses = [
            # First attempt: 500 error
            MagicMock(status_code=500, headers={}),
            # Second attempt: 429 rate limit
            MagicMock(status_code=429, headers={"retry-after": "1"}),
            # Third attempt: Success
            MagicMock(status_code=204, headers={}),
        ]
        
        with patch("httpx.AsyncClient.post", side_effect=responses):
            result = await provider.send_notification(message)
            # Should eventually succeed after retries
            assert result is True
    
    @pytest.mark.asyncio
    async def test_embed_generation_integration(
        self,
        discord_config: dict[str, object],
    ) -> None:
        """Test embed generation with various message types."""
        provider = DiscordProvider(discord_config)
        
        # Test different message configurations
        test_cases = [
            # Message with no metadata or tags
            Message(title="Simple", content="Simple message"),
            
            # Message with tags only
            Message(
                title="Tagged",
                content="Tagged message",
                tags=["tag1", "tag2"],
            ),
            
            # Message with metadata only
            Message(
                title="Metadata",
                content="Message with metadata",
                metadata={"key": "value"},
            ),
            
            # Message with everything
            Message(
                title="Complete",
                content="Complete message",
                priority="high",
                tags=["complete", "test"],
                metadata={"source": "test", "type": "integration"},
            ),
        ]
        
        mock_response = MagicMock()
        mock_response.status_code = 204
        
        with patch("httpx.AsyncClient.post", return_value=mock_response) as mock_post:
            for test_message in test_cases:
                result = await provider.send_notification(test_message)
                assert result is True
        
        # Verify all embeds were generated correctly
        assert mock_post.call_count == len(test_cases)
        
        for i, call in enumerate(mock_post.call_args_list):
            payload: dict[str, Any] = call.kwargs["json"]
            embed: dict[str, Any] = payload["embeds"][0]
            test_message = test_cases[i]
            
            assert embed["title"] == test_message.title
            assert embed["description"] == test_message.content
            
            # Verify fields based on message content
            field_names: list[str] = [str(field["name"]) for field in embed["fields"]]
            
            if test_message.tags:
                assert "Tags" in field_names
            
            if test_message.metadata:
                for key in test_message.metadata:
                    expected_field_name = key.replace("_", " ").title()
                    assert expected_field_name in field_names
            
            # Priority field should always be present
            assert "Priority" in field_names