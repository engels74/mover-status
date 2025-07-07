"""Tests for Telegram notification provider."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from typing import TYPE_CHECKING

from mover_status.plugins.telegram.provider import TelegramProvider
from mover_status.plugins.telegram.bot.client import ChatInfo, ChatType
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

    @pytest.mark.asyncio
    async def test_get_chat_statistics(self, full_config: Mapping[str, object]) -> None:
        """Test getting chat statistics."""
        provider = TelegramProvider(full_config)

        stats = await provider.get_chat_statistics()

        assert isinstance(stats, dict)
        assert stats["total_chats"] == 2
        assert "chat_types" in stats
        assert "chat_ids" in stats
        assert stats["chat_ids"] == ["123456789", "-100987654321"]

    @pytest.mark.asyncio
    async def test_validate_all_chats_success(self, full_config: Mapping[str, object]) -> None:
        """Test successful validation of all chats."""
        provider = TelegramProvider(full_config)

        with patch('telegram.Bot.get_chat') as mock_get_chat:
            mock_chat = MagicMock()
            mock_chat.type = "private"
            mock_get_chat.return_value = mock_chat

            results = await provider.validate_all_chats()

            assert len(results) == 2
            assert all(success for success in results.values())
            assert "123456789" in results
            assert "-100987654321" in results

    @pytest.mark.asyncio
    async def test_get_all_chat_info_success(self, full_config: Mapping[str, object]) -> None:
        """Test successful retrieval of all chat info."""
        provider = TelegramProvider(full_config)

        def mock_get_chat(chat_id: str) -> MagicMock:
            mock_chat = MagicMock()
            if chat_id.startswith("-100"):
                mock_chat.type = "supergroup"
                mock_chat.title = "Test Group"
            else:
                mock_chat.type = "private"
                mock_chat.title = None
            return mock_chat

        with patch('telegram.Bot.get_chat', side_effect=mock_get_chat):
            results = await provider.get_all_chat_info()

            assert len(results) == 2
            assert all(chat_info is not None for chat_info in results.values())

            # Check user chat
            user_info = results["123456789"]
            assert user_info is not None
            assert isinstance(user_info, ChatInfo)
            assert user_info.chat_type == ChatType.USER

            # Check group chat
            group_info = results["-100987654321"]
            assert group_info is not None
            assert isinstance(group_info, ChatInfo)
            assert group_info.chat_type == ChatType.SUPERGROUP
            assert group_info.title == "Test Group"

    @pytest.mark.asyncio
    async def test_send_notification_by_priority_success(
        self, full_config: Mapping[str, object], test_message: Message
    ) -> None:
        """Test sending notification with priority (all succeed)."""
        provider = TelegramProvider(full_config)

        with patch('telegram.Bot.send_message') as mock_send:
            mock_send.return_value = AsyncMock()

            results = await provider.send_notification_by_priority(test_message)

            assert len(results) == 2
            assert all(success for success in results.values())
            assert mock_send.call_count == 2

    @pytest.mark.asyncio
    async def test_send_notification_by_priority_partial_failure(
        self, full_config: Mapping[str, object], test_message: Message
    ) -> None:
        """Test sending notification with priority (partial failure)."""
        provider = TelegramProvider(full_config)

        def side_effect(**kwargs: object) -> AsyncMock | None:
            chat_id = kwargs.get("chat_id")
            if chat_id == "123456789":  # User chat succeeds
                return AsyncMock()
            else:  # Group chat fails
                from telegram.error import TelegramError
                raise TelegramError("Chat not found")

        with patch('telegram.Bot.send_message', side_effect=side_effect):
            results = await provider.send_notification_by_priority(test_message)

            assert len(results) == 2
            assert results["123456789"] is True
            assert results["-100987654321"] is False

    @pytest.mark.asyncio
    async def test_send_notification_by_priority_user_first(
        self, test_message: Message
    ) -> None:
        """Test that user chats are prioritized when prioritize_users=True."""
        config: dict[str, object] = {
            "bot_token": "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
            "chat_ids": ["123456789", "-100987654321", "987654321"]  # user, group, user
        }
        provider = TelegramProvider(config)

        call_order: list[str] = []

        async def mock_send_with_tracking(**kwargs: object) -> AsyncMock:
            call_order.append(str(kwargs.get("chat_id")))
            return AsyncMock()

        with patch('telegram.Bot.send_message', side_effect=mock_send_with_tracking):
            results = await provider.send_notification_by_priority(
                test_message, prioritize_users=True
            )

            assert len(results) == 3
            assert all(success for success in results.values())

            # Verify users were called before groups
            user_calls = [chat_id for chat_id in call_order if not chat_id.startswith("-")]
            group_calls = [chat_id for chat_id in call_order if chat_id.startswith("-")]

            if user_calls and group_calls:
                last_user_index = max(call_order.index(chat_id) for chat_id in user_calls)
                first_group_index = min(call_order.index(chat_id) for chat_id in group_calls)
                assert last_user_index < first_group_index