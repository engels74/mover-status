"""Tests for Discord webhook client."""

from __future__ import annotations

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from mover_status.plugins.discord.webhook.client import (
    DiscordWebhookClient,
    DiscordEmbed,
)


class TestDiscordEmbed:
    """Test cases for Discord embed model."""

    def test_valid_embed(self) -> None:
        """Test creating a valid embed."""
        embed = DiscordEmbed(
            title="Test Title",
            description="Test description",
            color=0xFF0000,
            fields=[
                {"name": "Field 1", "value": "Value 1", "inline": True},
                {"name": "Field 2", "value": "Value 2", "inline": False},
            ],
        )
        
        assert embed.title == "Test Title"
        assert embed.description == "Test description"
        assert embed.color == 0xFF0000
        assert len(embed.fields) == 2

    def test_embed_field_validation_missing_name(self) -> None:
        """Test field validation with missing name."""
        with pytest.raises(ValueError, match="must have 'name' and 'value'"):
            _ = DiscordEmbed(
                title="Test",
                description="Test description",
                fields=[{"value": "Value 1"}],  # Missing name
            )

    def test_embed_field_validation_missing_value(self) -> None:
        """Test field validation with missing value."""
        with pytest.raises(ValueError, match="must have 'name' and 'value'"):
            _ = DiscordEmbed(
                title="Test",
                description="Test description",
                fields=[{"name": "Field 1"}],  # Missing value
            )

    def test_embed_field_validation_name_too_long(self) -> None:
        """Test field validation with name too long."""
        long_name = "x" * 257  # 257 characters
        
        with pytest.raises(ValueError, match="name cannot exceed 256 characters"):
            _ = DiscordEmbed(
                title="Test",
                description="Test description",
                fields=[{"name": long_name, "value": "Value"}],
            )

    def test_embed_field_validation_value_too_long(self) -> None:
        """Test field validation with value too long."""
        long_value = "x" * 1025  # 1025 characters
        
        with pytest.raises(ValueError, match="value cannot exceed 1024 characters"):
            _ = DiscordEmbed(
                title="Test",
                description="Test description",
                fields=[{"name": "Field", "value": long_value}],
            )

    def test_embed_too_many_fields(self) -> None:
        """Test embed with too many fields."""
        fields: list[dict[str, str | bool]] = [{"name": f"Field {i}", "value": f"Value {i}"} for i in range(26)]
        
        with pytest.raises(ValueError):
            _ = DiscordEmbed(title="Test", description="Test description", fields=fields)


class TestDiscordWebhookClient:
    """Test cases for Discord webhook client."""

    @pytest.fixture
    def valid_webhook_url(self) -> str:
        """Valid Discord webhook URL."""
        return "https://discord.com/api/webhooks/123456789/abcdefg"

    @pytest.fixture
    def client(self, valid_webhook_url: str) -> DiscordWebhookClient:
        """Discord webhook client with valid URL."""
        return DiscordWebhookClient(
            webhook_url=valid_webhook_url,
            username="Test Bot",
            avatar_url="https://example.com/avatar.png",
        )

    def test_init_with_valid_url(self, valid_webhook_url: str) -> None:
        """Test client initialization with valid URL."""
        client = DiscordWebhookClient(webhook_url=valid_webhook_url)
        
        assert client.webhook_url == valid_webhook_url
        assert client.username is None
        assert client.avatar_url is None
        assert client.timeout == 30.0
        assert client.max_retries == 3
        assert client.retry_delay == 1.0

    def test_init_with_all_params(self, valid_webhook_url: str) -> None:
        """Test client initialization with all parameters."""
        client = DiscordWebhookClient(
            webhook_url=valid_webhook_url,
            username="Custom Bot",
            avatar_url="https://example.com/custom.png",
            timeout=60.0,
            max_retries=5,
            retry_delay=2.0,
        )
        
        assert client.webhook_url == valid_webhook_url
        assert client.username == "Custom Bot"
        assert client.avatar_url == "https://example.com/custom.png"
        assert client.timeout == 60.0
        assert client.max_retries == 5
        assert client.retry_delay == 2.0

    def test_validate_webhook_url_invalid_scheme(self) -> None:
        """Test webhook URL validation with invalid scheme."""
        with pytest.raises(ValueError, match="must use HTTP or HTTPS"):
            _ = DiscordWebhookClient(webhook_url="ftp://discord.com/api/webhooks/123/abc")

    def test_validate_webhook_url_invalid_domain(self) -> None:
        """Test webhook URL validation with invalid domain."""
        with pytest.raises(ValueError, match="must be a Discord webhook"):
            _ = DiscordWebhookClient(webhook_url="https://example.com/api/webhooks/123/abc")

    def test_validate_webhook_url_invalid_path(self) -> None:
        """Test webhook URL validation with invalid path."""
        with pytest.raises(ValueError, match="Invalid Discord webhook URL format"):
            _ = DiscordWebhookClient(webhook_url="https://discord.com/invalid/path")

    def test_validate_webhook_url_discordapp_domain(self) -> None:
        """Test webhook URL validation with discordapp.com domain."""
        client = DiscordWebhookClient(
            webhook_url="https://discordapp.com/api/webhooks/123/abc"
        )
        assert client.webhook_url == "https://discordapp.com/api/webhooks/123/abc"

    @pytest.mark.asyncio
    async def test_rate_limit_tracking(self, client: DiscordWebhookClient) -> None:
        """Test rate limit timestamp tracking."""
        # Access private attributes for testing
        client._rate_limit_max = 2  # Low limit for testing  # pyright: ignore[reportPrivateUsage]
        
        await client._check_rate_limit()  # pyright: ignore[reportPrivateUsage]
        assert len(client._rate_limit_timestamps) == 1  # pyright: ignore[reportPrivateUsage]
        
        await client._check_rate_limit()  # pyright: ignore[reportPrivateUsage]
        assert len(client._rate_limit_timestamps) == 2  # pyright: ignore[reportPrivateUsage]

    @pytest.mark.asyncio
    async def test_rate_limit_enforcement(self, client: DiscordWebhookClient) -> None:
        """Test rate limit enforcement with sleep."""
        # Set very low limit to trigger rate limiting
        client._rate_limit_max = 1  # pyright: ignore[reportPrivateUsage]
        client._rate_limit_window = 1.0  # 1 second window  # pyright: ignore[reportPrivateUsage]
        
        # First call should succeed immediately
        start_time = asyncio.get_event_loop().time()
        await client._check_rate_limit()  # pyright: ignore[reportPrivateUsage]
        first_call_time = asyncio.get_event_loop().time() - start_time
        assert first_call_time < 0.1  # Should be very fast
        
        # Second call should be delayed
        start_time = asyncio.get_event_loop().time()
        await client._check_rate_limit()  # pyright: ignore[reportPrivateUsage]
        second_call_time = asyncio.get_event_loop().time() - start_time
        assert second_call_time >= 0.9  # Should wait close to 1 second

    @pytest.mark.asyncio
    async def test_send_message_success(self, client: DiscordWebhookClient) -> None:
        """Test successful message sending."""
        with patch('httpx.AsyncClient.post', new_callable=AsyncMock) as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 204
            mock_post.return_value = mock_response
            
            result = await client.send_message(content="Test message")
            
            assert result is True
            mock_post.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_message_with_embeds(self, client: DiscordWebhookClient) -> None:
        """Test message sending with embeds."""
        with patch('httpx.AsyncClient.post', new_callable=AsyncMock) as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 204
            mock_post.return_value = mock_response
            
            embed = DiscordEmbed(title="Test Embed", description="Test description")
            result = await client.send_message(embeds=[embed])
            
            assert result is True
            mock_post.assert_called_once()
            
            # Check payload structure
            call_args = mock_post.call_args
            assert call_args is not None
            payload = call_args[1]["json"]  # pyright: ignore[reportAny]
            assert "embeds" in payload
            assert len(payload["embeds"]) == 1  # pyright: ignore[reportAny]
            assert payload["embeds"][0]["title"] == "Test Embed"

    @pytest.mark.asyncio
    async def test_send_message_with_custom_params(self, client: DiscordWebhookClient) -> None:
        """Test message sending with custom username and avatar."""
        with patch('httpx.AsyncClient.post', new_callable=AsyncMock) as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 204
            mock_post.return_value = mock_response
            
            result = await client.send_message(
                content="Test message",
                username="Custom Bot",
                avatar_url="https://example.com/custom.png",
            )
            
            assert result is True
            
            # Check payload includes custom parameters
            call_args = mock_post.call_args
            assert call_args is not None
            payload = call_args[1]["json"]  # pyright: ignore[reportAny]
            assert payload["username"] == "Custom Bot"
            assert payload["avatar_url"] == "https://example.com/custom.png"

    @pytest.mark.asyncio
    async def test_send_message_rate_limited_by_discord(self, client: DiscordWebhookClient) -> None:
        """Test handling Discord rate limiting."""
        with patch('httpx.AsyncClient.post', new_callable=AsyncMock) as mock_post:
            # First call: rate limited
            rate_limit_response = MagicMock()
            rate_limit_response.status_code = 429
            rate_limit_response.headers = {"Retry-After": "0.1"}
            
            # Second call: success
            success_response = MagicMock()
            success_response.status_code = 204
            
            mock_post.side_effect = [rate_limit_response, success_response]
            
            result = await client.send_message(content="Test message")
            
            assert result is True
            assert mock_post.call_count == 2

    @pytest.mark.asyncio
    async def test_send_message_client_error(self, client: DiscordWebhookClient) -> None:
        """Test handling client errors (4xx)."""
        with patch('httpx.AsyncClient.post', new_callable=AsyncMock) as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 400
            mock_response.text = "Bad Request"
            mock_post.return_value = mock_response
            
            result = await client.send_message(content="Test message")
            
            assert result is False
            # Should not retry on client errors
            mock_post.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_message_server_error_with_retries(self, client: DiscordWebhookClient) -> None:
        """Test handling server errors with retries."""
        client.retry_delay = 0.01  # Fast retries for testing
        
        with patch('httpx.AsyncClient.post', new_callable=AsyncMock) as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_response.text = "Internal Server Error"
            mock_post.return_value = mock_response
            
            result = await client.send_message(content="Test message")
            
            assert result is False
            # Should retry max_retries + 1 times
            assert mock_post.call_count == client.max_retries + 1

    @pytest.mark.asyncio
    async def test_send_message_network_error(self, client: DiscordWebhookClient) -> None:
        """Test handling network errors."""
        client.retry_delay = 0.01  # Fast retries for testing
        
        with patch('httpx.AsyncClient.post', new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = httpx.ConnectError("Connection failed")
            
            result = await client.send_message(content="Test message")
            
            assert result is False
            assert mock_post.call_count == client.max_retries + 1

    @pytest.mark.asyncio
    async def test_send_message_timeout_error(self, client: DiscordWebhookClient) -> None:
        """Test handling timeout errors."""
        client.retry_delay = 0.01  # Fast retries for testing
        
        with patch('httpx.AsyncClient.post', new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = httpx.TimeoutException("Request timed out")
            
            result = await client.send_message(content="Test message")
            
            assert result is False
            assert mock_post.call_count == client.max_retries + 1

    @pytest.mark.asyncio
    async def test_send_message_validation_errors(self, client: DiscordWebhookClient) -> None:
        """Test validation errors for message sending."""
        # No content or embeds
        with pytest.raises(ValueError, match="Either content or embeds must be provided"):
            _ = await client.send_message()
        
        # Content too long
        long_content = "x" * 2001
        with pytest.raises(ValueError, match="cannot exceed 2000 characters"):
            _ = await client.send_message(content=long_content)
        
        # Too many embeds
        embeds = [DiscordEmbed(title=f"Embed {i}", description="Test") for i in range(11)]
        with pytest.raises(ValueError, match="Cannot send more than 10 embeds"):
            _ = await client.send_message(embeds=embeds)

    def test_repr(self, client: DiscordWebhookClient) -> None:
        """Test string representation of client."""
        repr_str = repr(client)
        assert "DiscordWebhookClient" in repr_str
        assert "webhook_url" in repr_str