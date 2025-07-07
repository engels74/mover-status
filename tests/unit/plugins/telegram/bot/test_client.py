"""Tests for Telegram bot client."""

from __future__ import annotations

import asyncio
import pytest

from unittest.mock import AsyncMock, patch, MagicMock
from typing import TYPE_CHECKING

from mover_status.plugins.telegram.bot.client import TelegramBotClient, ChatType, ChatInfo

if TYPE_CHECKING:
    pass


class TestTelegramBotClient:
    """Test suite for TelegramBotClient."""
    
    @pytest.fixture
    def valid_bot_token(self) -> str:
        """Valid bot token for testing."""
        return "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
    
    @pytest.fixture
    def client(self, valid_bot_token: str) -> TelegramBotClient:
        """Create a bot client for testing."""
        return TelegramBotClient(bot_token=valid_bot_token)
    
    @pytest.fixture
    def user_chat_ids(self) -> list[str]:
        """User chat IDs for testing."""
        return ["123456789", "987654321"]
    
    @pytest.fixture
    def group_chat_ids(self) -> list[str]:
        """Group chat IDs for testing."""
        return ["-100123456789", "-100987654321"]
    
    @pytest.fixture
    def channel_chat_ids(self) -> list[str]:
        """Channel chat IDs for testing."""
        return ["-1001234567890", "-1009876543210"]
    
    @pytest.fixture
    def mixed_chat_ids(self, user_chat_ids: list[str], group_chat_ids: list[str], channel_chat_ids: list[str]) -> list[str]:
        """Mixed chat IDs (users, groups, channels) for testing."""
        return user_chat_ids + group_chat_ids + channel_chat_ids
    
    def test_client_initialization(self, valid_bot_token: str) -> None:
        """Test client initialization with valid parameters."""
        client = TelegramBotClient(
            bot_token=valid_bot_token,
            timeout=60.0,
            max_retries=5,
            retry_delay=2.0
        )
        
        assert client.bot_token == valid_bot_token
        assert client.timeout == 60.0
        assert client.max_retries == 5
        assert client.retry_delay == 2.0
    
    def test_client_initialization_invalid_token(self) -> None:
        """Test client initialization fails with invalid token."""
        with pytest.raises(ValueError, match="Invalid bot token format"):
            _ = TelegramBotClient(bot_token="invalid_token")
    
    @pytest.mark.asyncio
    async def test_send_message_to_multiple_chats_success(
        self, client: TelegramBotClient, mixed_chat_ids: list[str]
    ) -> None:
        """Test successful message sending to multiple chats of different types."""
        with patch('telegram.Bot.send_message') as mock_send:
            mock_send.return_value = AsyncMock()
            
            result = await client.send_message_to_multiple_chats(
                chat_ids=mixed_chat_ids,
                text="Test message",
                parse_mode="HTML",
                disable_web_page_preview=True
            )
            
            assert result is True
            assert mock_send.call_count == len(mixed_chat_ids)
            
            # Verify all chat IDs were called
            call_args_list = mock_send.call_args_list
            called_chat_ids = [call[1]["chat_id"] for call in call_args_list]
            for chat_id in mixed_chat_ids:
                assert chat_id in called_chat_ids
    
    @pytest.mark.asyncio
    async def test_send_message_to_multiple_chats_empty_list(self, client: TelegramBotClient) -> None:
        """Test handling of empty chat ID list."""
        result = await client.send_message_to_multiple_chats(
            chat_ids=[],
            text="Test message"
        )
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_send_message_to_multiple_chats_partial_failure(
        self, client: TelegramBotClient, mixed_chat_ids: list[str]
    ) -> None:
        """Test handling when some chats succeed and others fail."""
        def side_effect(**kwargs: object) -> AsyncMock | None:
            chat_id = kwargs.get("chat_id")
            if chat_id in mixed_chat_ids[:2]:  # First two succeed
                return AsyncMock()
            else:
                from telegram.error import TelegramError
                raise TelegramError("Chat not found")
        
        with patch('telegram.Bot.send_message', side_effect=side_effect):
            result = await client.send_message_to_multiple_chats(
                chat_ids=mixed_chat_ids,
                text="Test message"
            )
            
            # Should return False if any chat fails
            assert result is False
    
    @pytest.mark.asyncio
    async def test_send_message_to_multiple_chats_all_failures(
        self, client: TelegramBotClient, mixed_chat_ids: list[str]
    ) -> None:
        """Test handling when all chats fail."""
        with patch('telegram.Bot.send_message') as mock_send:
            from telegram.error import TelegramError
            mock_send.side_effect = TelegramError("API Error")
            
            result = await client.send_message_to_multiple_chats(
                chat_ids=mixed_chat_ids,
                text="Test message"
            )
            
            assert result is False
            assert mock_send.call_count == len(mixed_chat_ids)
    
    @pytest.mark.asyncio
    async def test_send_message_to_multiple_chats_concurrent_execution(
        self, client: TelegramBotClient, mixed_chat_ids: list[str]
    ) -> None:
        """Test that messages are sent concurrently, not sequentially."""
        call_times: list[float] = []
        
        async def mock_send_with_delay(**_kwargs: object) -> AsyncMock:
            import time
            call_times.append(time.time())
            await asyncio.sleep(0.1)  # Simulate network delay
            return AsyncMock()
        
        with patch('telegram.Bot.send_message', side_effect=mock_send_with_delay):
            start_time = asyncio.get_event_loop().time()
            
            result = await client.send_message_to_multiple_chats(
                chat_ids=mixed_chat_ids,
                text="Test message"
            )
            
            end_time = asyncio.get_event_loop().time()
            
            assert result is True
            
            # Verify concurrent execution - total time should be close to single delay
            # rather than sum of all delays
            total_time = end_time - start_time
            expected_sequential_time = 0.1 * len(mixed_chat_ids)
            assert total_time < expected_sequential_time * 0.5  # Much faster than sequential
    
    @pytest.mark.asyncio
    async def test_send_message_to_user_chats(
        self, client: TelegramBotClient, user_chat_ids: list[str]
    ) -> None:
        """Test sending messages specifically to user chats."""
        with patch('telegram.Bot.send_message') as mock_send:
            mock_send.return_value = AsyncMock()
            
            result = await client.send_message_to_multiple_chats(
                chat_ids=user_chat_ids,
                text="User notification",
                parse_mode="HTML"
            )
            
            assert result is True
            assert mock_send.call_count == len(user_chat_ids)
            
            # Verify user chat IDs format
            call_args_list = mock_send.call_args_list
            for call in call_args_list:
                chat_id: str = str(call[1]["chat_id"])
                assert chat_id in user_chat_ids
                assert not chat_id.startswith("-")  # User IDs are positive
    
    @pytest.mark.asyncio
    async def test_send_message_to_group_chats(
        self, client: TelegramBotClient, group_chat_ids: list[str]
    ) -> None:
        """Test sending messages specifically to group chats."""
        with patch('telegram.Bot.send_message') as mock_send:
            mock_send.return_value = AsyncMock()
            
            result = await client.send_message_to_multiple_chats(
                chat_ids=group_chat_ids,
                text="Group notification",
                parse_mode="Markdown"
            )
            
            assert result is True
            assert mock_send.call_count == len(group_chat_ids)
            
            # Verify group chat IDs format
            call_args_list = mock_send.call_args_list
            for call in call_args_list:
                chat_id: str = str(call[1]["chat_id"])
                assert chat_id in group_chat_ids
                assert chat_id.startswith("-100")  # Group IDs start with -100
    
    @pytest.mark.asyncio
    async def test_send_message_to_channel_chats(
        self, client: TelegramBotClient, channel_chat_ids: list[str]
    ) -> None:
        """Test sending messages specifically to channel chats."""
        with patch('telegram.Bot.send_message') as mock_send:
            mock_send.return_value = AsyncMock()
            
            result = await client.send_message_to_multiple_chats(
                chat_ids=channel_chat_ids,
                text="Channel notification",
                parse_mode="MarkdownV2"
            )
            
            assert result is True
            assert mock_send.call_count == len(channel_chat_ids)
            
            # Verify channel chat IDs format
            call_args_list = mock_send.call_args_list
            for call in call_args_list:
                chat_id: str = str(call[1]["chat_id"])
                assert chat_id in channel_chat_ids
                assert chat_id.startswith("-100")  # Channel IDs also start with -100
    
    @pytest.mark.asyncio
    async def test_send_message_rate_limiting_handling(
        self, client: TelegramBotClient, mixed_chat_ids: list[str]
    ) -> None:
        """Test handling of rate limiting across multiple chats."""
        call_count = 0
        
        def side_effect(**_kwargs: object) -> AsyncMock | None:
            nonlocal call_count
            call_count += 1
            
            if call_count <= 2:  # First two calls get rate limited
                from telegram.error import RetryAfter
                raise RetryAfter(retry_after=1)  # Short delay for testing (int)
            else:
                return AsyncMock()
        
        with patch('telegram.Bot.send_message', side_effect=side_effect):
            result = await client.send_message_to_multiple_chats(
                chat_ids=mixed_chat_ids[:3],  # Test with 3 chats
                text="Test message"
            )
            
            assert result is True
            # Should have more calls due to retries
            assert call_count > 3
    
    @pytest.mark.asyncio
    async def test_send_message_different_parse_modes(
        self, client: TelegramBotClient, mixed_chat_ids: list[str]
    ) -> None:
        """Test sending messages with different parse modes to multiple chats."""
        parse_modes = ["HTML", "Markdown", "MarkdownV2"]
        
        for parse_mode in parse_modes:
            with patch('telegram.Bot.send_message') as mock_send:
                mock_send.return_value = AsyncMock()
                
                result = await client.send_message_to_multiple_chats(
                    chat_ids=mixed_chat_ids,
                    text=f"Test message with {parse_mode}",
                    parse_mode=parse_mode
                )
                
                assert result is True
                
                # Verify parse mode was used for all calls
                call_args_list = mock_send.call_args_list
                for call in call_args_list:
                    assert call[1]["parse_mode"] == parse_mode

    def test_classify_chat_type(self, client: TelegramBotClient) -> None:
        """Test chat type classification based on chat ID format."""
        # User chats (positive IDs)
        assert client.classify_chat_type("123456789") == ChatType.USER
        assert client.classify_chat_type("987654321") == ChatType.USER

        # Supergroups and channels (-100 prefix)
        assert client.classify_chat_type("-100123456789") == ChatType.SUPERGROUP
        assert client.classify_chat_type("-1001234567890") == ChatType.SUPERGROUP

        # Legacy groups (negative but not -100)
        assert client.classify_chat_type("-123456789") == ChatType.GROUP

    def test_categorize_chats(self, client: TelegramBotClient, mixed_chat_ids: list[str]) -> None:
        """Test chat categorization functionality."""
        categorized = client.categorize_chats(mixed_chat_ids)

        # Verify structure
        assert isinstance(categorized, dict)
        assert all(chat_type in categorized for chat_type in ChatType)

        # Verify user chats
        user_chats = categorized[ChatType.USER]
        assert len(user_chats) == 2
        assert all(not chat_id.startswith("-") for chat_id in user_chats)

        # Verify supergroup/channel chats
        supergroup_chats = categorized[ChatType.SUPERGROUP]
        assert len(supergroup_chats) == 4  # Both groups and channels use -100 prefix
        assert all(chat_id.startswith("-100") for chat_id in supergroup_chats)

        # Verify no legacy groups in this test
        assert len(categorized[ChatType.GROUP]) == 0

    @pytest.mark.asyncio
    async def test_send_message_by_chat_type_prioritize_users(
        self, client: TelegramBotClient, mixed_chat_ids: list[str]
    ) -> None:
        """Test sending messages with user prioritization."""
        call_order: list[str] = []

        async def mock_send_with_tracking(**kwargs: object) -> AsyncMock:
            call_order.append(str(kwargs.get("chat_id")))
            return AsyncMock()

        with patch('telegram.Bot.send_message', side_effect=mock_send_with_tracking):
            results = await client.send_message_by_chat_type(
                chat_ids=mixed_chat_ids,
                text="Test message",
                prioritize_users=True
            )

            assert len(results) == len(mixed_chat_ids)
            assert all(success for success in results.values())

            # Verify users were called first
            user_calls = [chat_id for chat_id in call_order if not chat_id.startswith("-")]
            group_calls = [chat_id for chat_id in call_order if chat_id.startswith("-")]

            # All user calls should come before group calls
            if user_calls and group_calls:
                last_user_index = max(call_order.index(chat_id) for chat_id in user_calls)
                first_group_index = min(call_order.index(chat_id) for chat_id in group_calls)
                assert last_user_index < first_group_index

    @pytest.mark.asyncio
    async def test_validate_chat_permissions_success(
        self, client: TelegramBotClient, mixed_chat_ids: list[str]
    ) -> None:
        """Test successful chat permission validation."""
        with patch('telegram.Bot.get_chat') as mock_get_chat:
            mock_chat = MagicMock()
            mock_chat.type = "private"
            mock_get_chat.return_value = mock_chat

            results = await client.validate_chat_permissions(mixed_chat_ids)

            assert len(results) == len(mixed_chat_ids)
            assert all(success for success in results.values())
            assert mock_get_chat.call_count == len(mixed_chat_ids)

    @pytest.mark.asyncio
    async def test_validate_chat_permissions_failures(
        self, client: TelegramBotClient, mixed_chat_ids: list[str]
    ) -> None:
        """Test chat permission validation with failures."""
        def side_effect(chat_id: str) -> MagicMock:
            if chat_id.startswith("-100"):  # Fail for supergroups/channels
                from telegram.error import TelegramError
                raise TelegramError("Forbidden: bot is not a member")
            else:
                mock_chat = MagicMock()
                mock_chat.type = "private"
                return mock_chat

        with patch('telegram.Bot.get_chat', side_effect=side_effect):
            results = await client.validate_chat_permissions(mixed_chat_ids)

            assert len(results) == len(mixed_chat_ids)

            # Users should succeed, groups/channels should fail
            for chat_id, success in results.items():
                if chat_id.startswith("-100"):
                    assert success is False
                else:
                    assert success is True

    @pytest.mark.asyncio
    async def test_get_chat_info_success(
        self, client: TelegramBotClient, mixed_chat_ids: list[str]
    ) -> None:
        """Test successful chat info retrieval."""
        def mock_get_chat(chat_id: str) -> MagicMock:
            mock_chat = MagicMock()
            if chat_id.startswith("-100"):
                mock_chat.type = "supergroup"
                mock_chat.title = f"Test Group {chat_id}"
            else:
                mock_chat.type = "private"
                mock_chat.title = None
            return mock_chat

        with patch('telegram.Bot.get_chat', side_effect=mock_get_chat):
            results = await client.get_chat_info(mixed_chat_ids)

            assert len(results) == len(mixed_chat_ids)

            for chat_id, chat_info in results.items():
                assert chat_info is not None
                assert isinstance(chat_info, ChatInfo)
                assert chat_info.chat_id == chat_id

                if chat_id.startswith("-100"):
                    assert chat_info.chat_type == ChatType.SUPERGROUP
                    assert chat_info.title is not None
                else:
                    assert chat_info.chat_type == ChatType.USER

    @pytest.mark.asyncio
    async def test_send_message_with_fallback_primary_success(
        self, client: TelegramBotClient, user_chat_ids: list[str], group_chat_ids: list[str]
    ) -> None:
        """Test fallback messaging when primary chats succeed."""
        with patch('telegram.Bot.send_message') as mock_send:
            mock_send.return_value = AsyncMock()

            result = await client.send_message_with_fallback(
                primary_chat_ids=user_chat_ids,
                fallback_chat_ids=group_chat_ids,
                text="Test message"
            )

            assert result is True
            # Should only call primary chats
            assert mock_send.call_count == len(user_chat_ids)

    @pytest.mark.asyncio
    async def test_send_message_with_fallback_primary_fails(
        self, client: TelegramBotClient, user_chat_ids: list[str], group_chat_ids: list[str]
    ) -> None:
        """Test fallback messaging when primary chats fail."""
        call_count = 0

        def side_effect(**kwargs: object) -> AsyncMock | None:
            nonlocal call_count
            call_count += 1

            chat_id = kwargs.get("chat_id")
            if chat_id in user_chat_ids:  # Primary chats fail
                from telegram.error import TelegramError
                raise TelegramError("Chat not found")
            else:  # Fallback chats succeed
                return AsyncMock()

        with patch('telegram.Bot.send_message', side_effect=side_effect):
            result = await client.send_message_with_fallback(
                primary_chat_ids=user_chat_ids,
                fallback_chat_ids=group_chat_ids,
                text="Test message"
            )

            assert result is True
            # Should call both primary and fallback chats
            expected_calls = len(user_chat_ids) + len(group_chat_ids)
            assert call_count == expected_calls
