"""Tests for Telegram notification provider."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch
from typing import TYPE_CHECKING

from mover_status.plugins.telegram.provider import TelegramProvider
from mover_status.notifications.models.message import Message

if TYPE_CHECKING:
    from collections.abc import Mapping


class TestTelegramProvider:
    """Test suite for TelegramProvider."""
    
    @pytest.fixture
    def minimal_config(self) -> Mapping[str, object]:
        """Minimal valid configuration for testing."""
        return {
            "bot_token": "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
            "chat_ids": ["123456789"]
        }
    
    @pytest.fixture
    def full_config(self) -> Mapping[str, object]:
        """Full configuration with all options."""
        return {
            "bot_token": "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
            "chat_ids": ["123456789", "-100987654321"],
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
            "timeout": 30.0,
            "max_retries": 3,
            "retry_delay": 1.0
        }
    
    @pytest.fixture
    def test_message(self) -> Message:
        """Test message for notifications."""
        return Message(
            title="Test Notification",
            content="This is a test message.",
            priority="normal"
        )
    
    def test_provider_initialization_minimal_config(self, minimal_config: Mapping[str, object]) -> None:
        """Test provider initialization with minimal config."""
        provider = TelegramProvider(minimal_config)
        
        assert provider.bot_token == "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
        assert provider.chat_ids == ["123456789"]
        assert provider.parse_mode == "HTML"  # Default
        assert provider.disable_web_page_preview is True  # Default
        assert provider.timeout == 30.0  # Default
        assert provider.max_retries == 3  # Default
        assert provider.retry_delay == 1.0  # Default
    
    def test_provider_initialization_full_config(self, full_config: Mapping[str, object]) -> None:
        """Test provider initialization with full config."""
        provider = TelegramProvider(full_config)
        
        assert provider.bot_token == "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
        assert provider.chat_ids == ["123456789", "-100987654321"]
        assert provider.parse_mode == "HTML"
        assert provider.disable_web_page_preview is True
        assert provider.timeout == 30.0
        assert provider.max_retries == 3
        assert provider.retry_delay == 1.0
    
    def test_config_validation_missing_bot_token(self) -> None:
        """Test config validation fails when bot token is missing."""
        config = {"chat_ids": ["123456789"]}
        
        with pytest.raises(ValueError, match="bot_token is required"):
            _ = TelegramProvider(config)
    
    def test_config_validation_missing_chat_ids(self) -> None:
        """Test config validation fails when chat_ids are missing."""
        config = {"bot_token": "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"}
        
        with pytest.raises(ValueError, match="chat_ids is required"):
            _ = TelegramProvider(config)
    
    def test_config_validation_empty_chat_ids(self) -> None:
        """Test config validation fails when chat_ids list is empty."""
        config: dict[str, object] = {
            "bot_token": "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
            "chat_ids": []
        }
        
        with pytest.raises(ValueError, match="chat_ids cannot be empty"):
            _ = TelegramProvider(config)
    
    def test_config_validation_invalid_parse_mode(self) -> None:
        """Test config validation fails with invalid parse mode."""
        config = {
            "bot_token": "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
            "chat_ids": ["123456789"],
            "parse_mode": "INVALID"
        }
        
        with pytest.raises(ValueError, match="parse_mode must be one of"):
            _ = TelegramProvider(config)
    
    def test_get_provider_name(self, minimal_config: Mapping[str, object]) -> None:
        """Test provider name is correct."""
        provider = TelegramProvider(minimal_config)
        assert provider.get_provider_name() == "telegram"
    
    @pytest.mark.asyncio
    async def test_send_notification_success(
        self, minimal_config: Mapping[str, object], test_message: Message
    ) -> None:
        """Test successful notification sending."""
        provider = TelegramProvider(minimal_config)
        
        with patch('telegram.Bot.send_message') as mock_send:
            mock_send.return_value = AsyncMock()
            
            result = await provider.send_notification(test_message)
            
            assert result is True
            mock_send.assert_called_once()
            
            # Verify the call parameters
            call_args = mock_send.call_args
            assert call_args[1]["chat_id"] == "123456789"
            assert "Test Notification" in call_args[1]["text"]
            assert call_args[1]["parse_mode"] == "HTML"
            assert call_args[1]["disable_web_page_preview"] is True
    
    @pytest.mark.asyncio
    async def test_send_notification_multiple_chats(
        self, full_config: Mapping[str, object], test_message: Message
    ) -> None:
        """Test notification sending to multiple chats."""
        provider = TelegramProvider(full_config)
        
        with patch('telegram.Bot.send_message') as mock_send:
            mock_send.return_value = AsyncMock()
            
            result = await provider.send_notification(test_message)
            
            assert result is True
            assert mock_send.call_count == 2
            
            # Verify both chat IDs were called
            call_args_list = mock_send.call_args_list
            chat_ids = [call[1]["chat_id"] for call in call_args_list]
            assert "123456789" in chat_ids
            assert "-100987654321" in chat_ids
    
    @pytest.mark.asyncio
    async def test_send_notification_api_error(
        self, minimal_config: Mapping[str, object], test_message: Message
    ) -> None:
        """Test handling of Telegram API errors."""
        provider = TelegramProvider(minimal_config)
        
        with patch('telegram.Bot.send_message') as mock_send:
            from telegram.error import TelegramError
            mock_send.side_effect = TelegramError("API Error")
            
            result = await provider.send_notification(test_message)
            
            assert result is False
    
    @pytest.mark.asyncio
    async def test_send_notification_network_error(
        self, minimal_config: Mapping[str, object], test_message: Message
    ) -> None:
        """Test handling of network errors."""
        provider = TelegramProvider(minimal_config)
        
        with patch('telegram.Bot.send_message') as mock_send:
            mock_send.side_effect = ConnectionError("Network Error")
            
            result = await provider.send_notification(test_message)
            
            assert result is False
    
    @pytest.mark.asyncio
    async def test_send_notification_partial_failure(self, test_message: Message) -> None:
        """Test handling when some chats succeed and others fail."""
        config: dict[str, object] = {
            "bot_token": "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
            "chat_ids": ["123456789", "987654321"]
        }
        provider = TelegramProvider(config)
        
        def side_effect(**kwargs: object) -> AsyncMock | None:
            if kwargs.get("chat_id") == "123456789":
                return AsyncMock()  # Success
            else:
                from telegram.error import TelegramError
                raise TelegramError("Chat not found")  # Failure
        
        with patch('telegram.Bot.send_message', side_effect=side_effect):
            result = await provider.send_notification(test_message)
            
            # Should return False if any chat fails
            assert result is False
    
    def test_config_validation_invalid_bot_token(self) -> None:
        """Test config validation fails with invalid bot token format."""
        config = {
            "bot_token": "invalid_token",
            "chat_ids": ["123456789"]
        }
        
        with pytest.raises(ValueError, match="Invalid bot token format"):
            _ = TelegramProvider(config)
    
    def test_config_validation_invalid_chat_id(self) -> None:
        """Test config validation fails with invalid chat ID format."""
        config = {
            "bot_token": "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
            "chat_ids": ["abc123"]
        }
        
        with pytest.raises(ValueError, match="Invalid chat ID format"):
            _ = TelegramProvider(config)