"""Tests for enhanced Telegram error handling functionality."""

from __future__ import annotations

import asyncio
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import timedelta

from mover_status.plugins.telegram.bot.client import TelegramBotClient
from mover_status.plugins.telegram.rate_limiting import AdvancedRateLimiter, RateLimitConfig
from mover_status.plugins.telegram.provider import TelegramProvider


class TestEnhancedErrorHandling:
    """Test suite for enhanced error handling."""
    
    @pytest.fixture
    def bot_token(self) -> str:
        """Valid bot token for testing."""
        return "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
    
    @pytest.fixture
    def client_with_rate_limiter(self, bot_token: str) -> TelegramBotClient:
        """Create a bot client with rate limiter for testing."""
        config = RateLimitConfig(
            global_limit=1000,  # High limits to avoid interference
            chat_limit=1000,
            group_limit=1000
        )
        rate_limiter = AdvancedRateLimiter(config)
        
        return TelegramBotClient(
            bot_token=bot_token,
            timeout=30.0,
            max_retries=3,
            retry_delay=1.0,
            rate_limiter=rate_limiter
        )
    
    @pytest.mark.asyncio
    async def test_forbidden_error_handling(self, client_with_rate_limiter: TelegramBotClient) -> None:
        """Test handling of Forbidden errors (bot blocked)."""
        chat_id = "123456"
        
        with patch('telegram.Bot.send_message') as mock_send:
            from telegram.error import Forbidden
            mock_send.side_effect = Forbidden("Forbidden: bot was blocked by the user")
            
            result = await client_with_rate_limiter.send_message(
                chat_id=chat_id,
                text="Test message"
            )
            
            assert result is False
            # Should not retry on Forbidden errors
            assert mock_send.call_count == 1
    
    @pytest.mark.asyncio
    async def test_bad_request_error_handling(self, client_with_rate_limiter: TelegramBotClient) -> None:
        """Test handling of BadRequest errors."""
        chat_id = "123456"
        
        with patch('telegram.Bot.send_message') as mock_send:
            from telegram.error import BadRequest
            mock_send.side_effect = BadRequest("Bad Request: message is too long")
            
            result = await client_with_rate_limiter.send_message(
                chat_id=chat_id,
                text="Test message"
            )
            
            assert result is False
            # Should not retry on BadRequest errors
            assert mock_send.call_count == 1
    
    @pytest.mark.asyncio
    async def test_rate_limiting_integration(self, client_with_rate_limiter: TelegramBotClient) -> None:
        """Test integration with rate limiting."""
        chat_id = "123456"
        
        # First request should use rate limiter but not wait (within limits)
        with patch('telegram.Bot.send_message') as mock_send:
            mock_send.return_value = AsyncMock()
            
            result = await client_with_rate_limiter.send_message(
                chat_id=chat_id,
                text="Test message"
            )
            
            assert result is True
            assert mock_send.call_count == 1
    
    @pytest.mark.asyncio
    async def test_retry_after_with_timedelta(self, client_with_rate_limiter: TelegramBotClient) -> None:
        """Test RetryAfter handling with timedelta objects."""
        chat_id = "123456"
        call_count = 0
        
        def side_effect(*_args: object, **_kwargs: object) -> AsyncMock | None:
            nonlocal call_count
            call_count += 1
            
            if call_count == 1:
                from telegram.error import RetryAfter
                # Use timedelta as the newer python-telegram-bot versions do
                raise RetryAfter(retry_after=timedelta(seconds=0.1))
            else:
                return AsyncMock()
        
        with patch('telegram.Bot.send_message', side_effect=side_effect):
            result = await client_with_rate_limiter.send_message(
                chat_id=chat_id,
                text="Test message"
            )
            
            assert result is True
            assert call_count == 2  # Should retry after rate limit
    
    @pytest.mark.asyncio
    async def test_network_error_retry(self, client_with_rate_limiter: TelegramBotClient) -> None:
        """Test NetworkError retry with exponential backoff."""
        chat_id = "123456"
        call_count = 0
        
        def side_effect(*_args: object, **_kwargs: object) -> AsyncMock | None:
            nonlocal call_count
            call_count += 1
            
            if call_count <= 2:
                from telegram.error import NetworkError
                raise NetworkError("Network unreachable")
            else:
                return AsyncMock()
        
        with patch('telegram.Bot.send_message', side_effect=side_effect):
            start_time = asyncio.get_event_loop().time()
            
            result = await client_with_rate_limiter.send_message(
                chat_id=chat_id,
                text="Test message"
            )
            
            end_time = asyncio.get_event_loop().time()
            
            assert result is True
            assert call_count == 3  # Initial + 2 retries
            # Should have some delay due to exponential backoff
            assert end_time - start_time >= 0.01  # At least some delay
    
    @pytest.mark.asyncio
    async def test_timeout_error_retry(self, client_with_rate_limiter: TelegramBotClient) -> None:
        """Test TimedOut error retry behavior."""
        chat_id = "123456"
        call_count = 0
        
        def side_effect(*_args: object, **_kwargs: object) -> AsyncMock | None:
            nonlocal call_count
            call_count += 1
            
            if call_count == 1:
                from telegram.error import TimedOut
                raise TimedOut("Request timed out")
            else:
                return AsyncMock()
        
        with patch('telegram.Bot.send_message', side_effect=side_effect):
            result = await client_with_rate_limiter.send_message(
                chat_id=chat_id,
                text="Test message"
            )
            
            assert result is True
            assert call_count == 2  # Should retry after timeout
    
    @pytest.mark.asyncio
    async def test_max_retries_exhausted(self, client_with_rate_limiter: TelegramBotClient) -> None:
        """Test behavior when max retries are exhausted."""
        chat_id = "123456"
        
        with patch('telegram.Bot.send_message') as mock_send:
            from telegram.error import TimedOut
            mock_send.side_effect = TimedOut("Persistent timeout")
            
            result = await client_with_rate_limiter.send_message(
                chat_id=chat_id,
                text="Test message"
            )
            
            assert result is False
            # Should try max_retries + 1 times (initial + retries)
            assert mock_send.call_count == 4  # 1 initial + 3 retries
    
    @pytest.mark.asyncio
    async def test_authentication_testing(self, client_with_rate_limiter: TelegramBotClient) -> None:
        """Test bot authentication testing functionality."""
        with patch('telegram.Bot.get_me') as mock_get_me:
            mock_bot_info = MagicMock()
            mock_bot_info.id = 123456789
            mock_bot_info.username = "test_bot"
            mock_bot_info.first_name = "Test Bot"
            mock_bot_info.is_bot = True
            mock_bot_info.can_join_groups = True
            mock_bot_info.can_read_all_group_messages = False
            mock_bot_info.supports_inline_queries = False
            
            mock_get_me.return_value = mock_bot_info
            
            result = await client_with_rate_limiter.test_bot_authentication()
            
            assert result["authenticated"] is True
            assert result["error"] is None
            
            bot_info = result["bot_info"]
            assert isinstance(bot_info, dict)
            assert bot_info["id"] == 123456789
            assert bot_info["username"] == "test_bot"
            assert bot_info["is_bot"] is True
    
    @pytest.mark.asyncio
    async def test_authentication_failure(self, client_with_rate_limiter: TelegramBotClient) -> None:
        """Test authentication failure handling."""
        with patch('telegram.Bot.get_me') as mock_get_me:
            from telegram.error import Forbidden
            mock_get_me.side_effect = Forbidden("Unauthorized")
            
            result = await client_with_rate_limiter.test_bot_authentication()
            
            assert result["authenticated"] is False
            assert result["bot_info"] is None
            
            error = result["error"]
            assert isinstance(error, dict)
            assert error["type"] == "forbidden"
            assert "Unauthorized" in error["message"]
    
    def test_rate_limiting_statistics(self, client_with_rate_limiter: TelegramBotClient) -> None:
        """Test rate limiting statistics retrieval."""
        stats = client_with_rate_limiter.get_rate_limiting_statistics()
        
        assert stats is not None
        assert "global_tokens" in stats
        assert "global_capacity" in stats
        assert "config" in stats
        
        config_stats = stats["config"]
        assert isinstance(config_stats, dict)
        assert "global_limit" in config_stats


class TestProviderErrorHandling:
    """Test suite for provider-level error handling."""
    
    @pytest.fixture
    def provider_config(self) -> dict[str, object]:
        """Provider configuration for testing."""
        return {
            "bot_token": "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
            "chat_ids": ["123456", "-100987654"],
            "parse_mode": "HTML",
            "timeout": 30.0,
            "max_retries": 3,
            "retry_delay": 1.0,
            "rate_limiting": {
                "enabled": True,
                "global_limit": 30,
                "chat_limit": 20,
                "hourly_quota": 1000
            }
        }
    
    @pytest.fixture
    def provider(self, provider_config: dict[str, object]) -> TelegramProvider:
        """Create a provider for testing."""
        return TelegramProvider(provider_config)
    
    @pytest.mark.asyncio
    async def test_comprehensive_status(self, provider: TelegramProvider) -> None:
        """Test comprehensive status retrieval."""
        with patch('telegram.Bot.get_me') as mock_get_me, \
             patch('telegram.Bot.get_chat') as mock_get_chat:
            
            # Mock successful authentication
            mock_bot_info = MagicMock()
            mock_bot_info.id = 123456789
            mock_bot_info.username = "test_bot"
            mock_bot_info.first_name = "Test Bot"
            mock_bot_info.is_bot = True
            mock_bot_info.can_join_groups = True
            mock_bot_info.can_read_all_group_messages = False
            mock_bot_info.supports_inline_queries = False
            mock_get_me.return_value = mock_bot_info
            
            # Mock chat info
            mock_chat = MagicMock()
            mock_chat.type = "private"
            mock_chat.title = None
            mock_get_chat.return_value = mock_chat
            
            status = await provider.get_comprehensive_status()
            
            assert "provider_name" in status
            assert "configuration" in status
            assert "authentication" in status
            assert "chat_statistics" in status
            assert "rate_limiting" in status
            assert "chat_permissions" in status
            
            # Check configuration
            config = status["configuration"]
            assert isinstance(config, dict)
            assert config["chat_count"] == 2
            assert config["rate_limiting_enabled"] is True
            
            # Check authentication
            auth = status["authentication"]
            assert isinstance(auth, dict)
            assert auth["authenticated"] is True
    
    @pytest.mark.asyncio
    async def test_fallback_delivery(self, provider: TelegramProvider) -> None:
        """Test fallback delivery mechanism."""
        from mover_status.notifications.models.message import Message
        
        message = Message(
            title="Test Notification",
            content="This is a test message",
            priority="normal"
        )
        
        with patch('telegram.Bot.send_message') as mock_send:
            # First attempt fails, second (fallback) succeeds
            call_count = 0
            
            def side_effect(*_args: object, **kwargs: object) -> AsyncMock | None:
                nonlocal call_count
                call_count += 1
                
                # Check if this is a fallback call (no parse_mode or empty parse_mode)
                parse_mode = kwargs.get("parse_mode", "")
                if parse_mode == "":
                    return AsyncMock()  # Fallback succeeds
                else:
                    from telegram.error import BadRequest
                    raise BadRequest("Invalid parse mode")
            
            mock_send.side_effect = side_effect
            
            result = await provider.send_notification_with_fallback_and_monitoring(
                message=message,
                fallback_enabled=True
            )
            
            assert result["partial_success"] is True
            assert "fallback_details" in result
            assert result["metrics"]["final_successful_chats"] > 0
    
    @pytest.mark.asyncio
    async def test_send_notification_monitoring(self, provider: TelegramProvider) -> None:
        """Test notification sending with monitoring."""
        from mover_status.notifications.models.message import Message
        
        message = Message(
            title="Test Notification",
            content="This is a test message",
            priority="high"
        )
        
        with patch('telegram.Bot.send_message') as mock_send:
            mock_send.return_value = AsyncMock()
            
            result = await provider.send_notification_with_fallback_and_monitoring(
                message=message,
                fallback_enabled=False
            )
            
            assert result["success"] is True
            assert "metrics" in result
            
            metrics = result.get("metrics")
            assert isinstance(metrics, dict)
            assert "successful_chats" in metrics
            assert "total_chats" in metrics
            assert "success_rate" in metrics
            assert "execution_time" in metrics
            
            assert metrics["successful_chats"] == 2  # Both chats should succeed
            assert metrics["total_chats"] == 2
            assert metrics["success_rate"] == 1.0
    
    @pytest.mark.asyncio
    async def test_chat_permissions_validation_failure(self, provider: TelegramProvider) -> None:
        """Test handling of chat permission validation failures."""
        with patch('telegram.Bot.get_chat') as mock_get_chat:
            from telegram.error import Forbidden
            mock_get_chat.side_effect = Forbidden("Bot not in chat")
            
            status = await provider.get_comprehensive_status()
            
            # Should handle permission errors gracefully
            assert "chat_permissions" in status
            permissions = status["chat_permissions"]
            assert isinstance(permissions, dict)
            assert permissions["accessible_chats"] == 0
            assert permissions["blocked_chats"] == 2  # Both chats should be blocked


class TestErrorHandlingEdgeCases:
    """Test suite for error handling edge cases."""
    
    @pytest.mark.asyncio
    async def test_invalid_chat_id_handling(self) -> None:
        """Test handling of invalid chat IDs."""
        client = TelegramBotClient(
            bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
        )
        
        # Invalid chat ID should return False immediately
        result = await client.send_message(
            chat_id="invalid_chat_id",
            text="Test message"
        )
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_unexpected_exception_handling(self) -> None:
        """Test handling of unexpected exceptions."""
        client = TelegramBotClient(
            bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
        )
        
        with patch('telegram.Bot.send_message') as mock_send:
            mock_send.side_effect = ValueError("Unexpected error")
            
            result = await client.send_message(
                chat_id="123456",
                text="Test message"
            )
            
            assert result is False
            # Should not retry on unexpected exceptions
            assert mock_send.call_count == 1
    
    @pytest.mark.asyncio
    async def test_rate_limiter_exception_resilience(self) -> None:
        """Test that rate limiter exceptions don't break the flow."""
        # Create a rate limiter that will fail
        config = RateLimitConfig()
        rate_limiter = AdvancedRateLimiter(config)
        
        client = TelegramBotClient(
            bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
            rate_limiter=rate_limiter
        )
        
        with patch.object(rate_limiter, 'acquire') as mock_acquire, \
             patch('telegram.Bot.send_message') as mock_send:
            
            # Rate limiter throws exception
            mock_acquire.side_effect = Exception("Rate limiter error")
            mock_send.return_value = AsyncMock()
            
            # Should still attempt to send message
            result = await client.send_message(
                chat_id="123456",
                text="Test message"
            )
            
            # Message sending should proceed despite rate limiter error
            assert mock_send.call_count >= 1