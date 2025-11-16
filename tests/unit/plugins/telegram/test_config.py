"""Tests for Telegram configuration schema."""

import pytest
from pydantic import ValidationError

from mover_status.plugins.telegram.config import TelegramConfig


class TestTelegramConfig:
    """TelegramConfig validation scenarios."""

    def test_valid_configuration_with_all_fields(self) -> None:
        """Configuration accepts valid bot token and chat ID with all optional fields."""
        config = TelegramConfig.model_validate(
            {
                "bot_token": "123456789:ABCdefGHIjklMNOpqrsTUVwxyz-123456788",
                "chat_id": "-1001234567890",
                "parse_mode": "HTML",
                "message_thread_id": 42,
                "disable_notification": True,
            }
        )

        assert config.bot_token == "123456789:ABCdefGHIjklMNOpqrsTUVwxyz-123456788"
        assert config.chat_id == "-1001234567890"
        assert config.parse_mode == "HTML"
        assert config.message_thread_id == 42
        assert config.disable_notification is True

    def test_valid_configuration_minimal(self) -> None:
        """Configuration works with only required fields."""
        config = TelegramConfig(
            bot_token="987654321:ZYXwvuTSRqponMLKjihgfedcba_98765432",
            chat_id="123456789",
        )

        assert config.bot_token == "987654321:ZYXwvuTSRqponMLKjihgfedcba_98765432"
        assert config.chat_id == "123456789"
        assert config.parse_mode == "HTML"  # Default value
        assert config.message_thread_id is None  # Default value
        assert config.disable_notification is False  # Default value

    def test_bot_token_whitespace_normalization(self) -> None:
        """Bot token is stripped of surrounding whitespace."""
        config = TelegramConfig(
            bot_token="  123456789:ABCdefGHIjklMNOpqrsTUVwxyz-12345678  ",
            chat_id="123456789",
        )

        assert config.bot_token == "123456789:ABCdefGHIjklMNOpqrsTUVwxyz-12345678"

    def test_chat_id_whitespace_normalization(self) -> None:
        """Chat ID is stripped of surrounding whitespace."""
        config = TelegramConfig(
            bot_token="123456789:ABCdefGHIjklMNOpqrsTUVwxyz-12345678",
            chat_id="  -1001234567890  ",
        )

        assert config.chat_id == "-1001234567890"

    def test_accepts_channel_username_chat_id(self) -> None:
        """Chat ID can be a channel username with @ prefix."""
        config = TelegramConfig(
            bot_token="123456789:ABCdefGHIjklMNOpqrsTUVwxyz-12345678",
            chat_id="@mychannel",
        )

        assert config.chat_id == "@mychannel"

    def test_accepts_long_channel_username(self) -> None:
        """Channel username can be longer than minimum length."""
        config = TelegramConfig(
            bot_token="123456789:ABCdefGHIjklMNOpqrsTUVwxyz-12345678",
            chat_id="@my_super_long_channel_name_123",
        )

        assert config.chat_id == "@my_super_long_channel_name_123"

    def test_accepts_positive_user_id(self) -> None:
        """Chat ID can be a positive integer for user chats."""
        config = TelegramConfig(
            bot_token="123456789:ABCdefGHIjklMNOpqrsTUVwxyz-12345678",
            chat_id="123456789",
        )

        assert config.chat_id == "123456789"

    def test_accepts_negative_group_id(self) -> None:
        """Chat ID can be a negative integer for group chats."""
        config = TelegramConfig(
            bot_token="123456789:ABCdefGHIjklMNOpqrsTUVwxyz-12345678",
            chat_id="-987654321",
        )

        assert config.chat_id == "-987654321"

    def test_accepts_markdown_parse_mode(self) -> None:
        """Parse mode can be Markdown."""
        config = TelegramConfig(
            bot_token="123456789:ABCdefGHIjklMNOpqrsTUVwxyz-12345678",
            chat_id="123456789",
            parse_mode="Markdown",
        )

        assert config.parse_mode == "Markdown"

    def test_accepts_markdownv2_parse_mode(self) -> None:
        """Parse mode can be MarkdownV2."""
        config = TelegramConfig(
            bot_token="123456789:ABCdefGHIjklMNOpqrsTUVwxyz-12345678",
            chat_id="123456789",
            parse_mode="MarkdownV2",
        )

        assert config.parse_mode == "MarkdownV2"

    def test_accepts_none_parse_mode(self) -> None:
        """Parse mode can be None for plain text."""
        config = TelegramConfig(
            bot_token="123456789:ABCdefGHIjklMNOpqrsTUVwxyz-12345678",
            chat_id="123456789",
            parse_mode=None,
        )

        assert config.parse_mode is None

    def test_accepts_positive_message_thread_id(self) -> None:
        """Message thread ID must be a positive integer."""
        config = TelegramConfig(
            bot_token="123456789:ABCdefGHIjklMNOpqrsTUVwxyz-12345678",
            chat_id="123456789",
            message_thread_id=100,
        )

        assert config.message_thread_id == 100

    def test_rejects_invalid_bot_token_format_no_colon(self) -> None:
        """Bot token without colon separator is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            _ = TelegramConfig(
                bot_token="123456789ABCdefGHIjklMNOpqrsTUVwxyz-1234567",
                chat_id="123456789",
            )
        assert "format" in str(exc_info.value).lower()

    def test_rejects_invalid_bot_token_format_short_token(self) -> None:
        """Bot token with short token portion is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            _ = TelegramConfig(
                bot_token="123456789:SHORT",
                chat_id="123456789",
            )
        assert "format" in str(exc_info.value).lower()

    def test_rejects_invalid_bot_token_format_token_too_short(self) -> None:
        """Bot token with token portion shorter than 35 chars is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            _ = TelegramConfig(
                bot_token="123456789:ABCdefGHIjklMNOpqrsTUVwxyz-123",  # 34 chars
                chat_id="123456789",
            )
        assert "format" in str(exc_info.value).lower()

    def test_rejects_invalid_bot_token_format_invalid_chars(self) -> None:
        """Bot token with invalid characters is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            _ = TelegramConfig(
                bot_token="123456789:ABC@#$%^&*()INVALID!@#$%^&*()12",
                chat_id="123456789",
            )
        assert "format" in str(exc_info.value).lower()

    def test_rejects_invalid_bot_token_format_non_numeric_id(self) -> None:
        """Bot token with non-numeric ID portion is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            _ = TelegramConfig(
                bot_token="ABC123456:ABCdefGHIjklMNOpqrsTUVwxyz-1234567",
                chat_id="123456789",
            )
        assert "format" in str(exc_info.value).lower()

    def test_rejects_empty_chat_id(self) -> None:
        """Empty chat ID is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            _ = TelegramConfig(
                bot_token="123456789:ABCdefGHIjklMNOpqrsTUVwxyz-12345678",
                chat_id="",
            )
        assert "empty" in str(exc_info.value).lower()

    def test_rejects_whitespace_only_chat_id(self) -> None:
        """Whitespace-only chat ID is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            _ = TelegramConfig(
                bot_token="123456789:ABCdefGHIjklMNOpqrsTUVwxyz-12345678",
                chat_id="   ",
            )
        assert "empty" in str(exc_info.value).lower()

    def test_rejects_channel_username_too_short(self) -> None:
        """Channel username shorter than 5 characters is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            _ = TelegramConfig(
                bot_token="123456789:ABCdefGHIjklMNOpqrsTUVwxyz-12345678",
                chat_id="@abc",
            )
        assert "numeric" in str(exc_info.value).lower() or "@username" in str(exc_info.value).lower()

    def test_rejects_channel_username_with_invalid_chars(self) -> None:
        """Channel username with invalid characters is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            _ = TelegramConfig(
                bot_token="123456789:ABCdefGHIjklMNOpqrsTUVwxyz-12345678",
                chat_id="@my-channel!",
            )
        assert "numeric" in str(exc_info.value).lower() or "@username" in str(exc_info.value).lower()

    def test_rejects_invalid_chat_id_format(self) -> None:
        """Chat ID that is neither numeric nor @username is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            _ = TelegramConfig(
                bot_token="123456789:ABCdefGHIjklMNOpqrsTUVwxyz-12345678",
                chat_id="invalid_chat_id",
            )
        assert "numeric" in str(exc_info.value).lower() or "@username" in str(exc_info.value).lower()

    def test_rejects_invalid_parse_mode(self) -> None:
        """Invalid parse mode literal is rejected."""
        with pytest.raises(ValidationError):
            _ = TelegramConfig.model_validate(
                {
                    "bot_token": "123456789:ABCdefGHIjklMNOpqrsTUVwxyz-12345678",
                    "chat_id": "123456789",
                    "parse_mode": "PlainText",
                }
            )

    def test_rejects_case_insensitive_parse_mode(self) -> None:
        """Parse mode is case-sensitive."""
        with pytest.raises(ValidationError):
            _ = TelegramConfig.model_validate(
                {
                    "bot_token": "123456789:ABCdefGHIjklMNOpqrsTUVwxyz-12345678",
                    "chat_id": "123456789",
                    "parse_mode": "html",  # Must be "HTML"
                }
            )

    def test_rejects_zero_message_thread_id(self) -> None:
        """Message thread ID of zero is rejected."""
        with pytest.raises(ValidationError):
            _ = TelegramConfig(
                bot_token="123456789:ABCdefGHIjklMNOpqrsTUVwxyz-12345678",
                chat_id="123456789",
                message_thread_id=0,
            )

    def test_rejects_negative_message_thread_id(self) -> None:
        """Negative message thread ID is rejected."""
        with pytest.raises(ValidationError):
            _ = TelegramConfig(
                bot_token="123456789:ABCdefGHIjklMNOpqrsTUVwxyz-12345678",
                chat_id="123456789",
                message_thread_id=-1,
            )

    def test_missing_bot_token_field(self) -> None:
        """Bot token is a required field."""
        with pytest.raises(ValidationError):
            _ = TelegramConfig.model_validate(
                {
                    "chat_id": "123456789",
                }
            )

    def test_missing_chat_id_field(self) -> None:
        """Chat ID is a required field."""
        with pytest.raises(ValidationError):
            _ = TelegramConfig.model_validate(
                {
                    "bot_token": "123456789:ABCdefGHIjklMNOpqrsTUVwxyz-12345678",
                }
            )
