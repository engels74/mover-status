# notifications/providers/telegram/config.py

"""
Runtime configuration management for Telegram bot notifications.
Handles validation, normalization, and conversion of bot API configuration settings.

Example:
    >>> from notifications.providers.telegram import TelegramConfig
    >>> config = TelegramConfig(
    ...     bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
    ...     chat_id="-1001234567890",
    ...     parse_mode="HTML"
    ... )
    >>> provider_config = config.to_provider_config()
"""

import re
from typing import Optional, Union

from pydantic import BaseModel, Field, field_validator
from structlog import get_logger

from notifications.providers.telegram.types import (
    RATE_LIMIT,
    ChatType,
    ParseMode,
    validate_chat_id,
)
from shared.types.telegram import MessageLimit

logger = get_logger(__name__)


class TelegramConfig(BaseModel):
    """Telegram bot configuration settings."""

    bot_token: str = Field(
        ...,  # Required field
        description="Telegram bot API token",
        examples=["123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"]
    )

    chat_id: Union[int, str] = Field(
        ...,  # Required field
        description="Telegram chat ID (group, channel, or user)",
        examples=["-1001234567890", "@channelname"]
    )

    parse_mode: ParseMode = Field(
        default=ParseMode.HTML,
        description="Message parsing mode for formatting"
    )

    disable_notifications: bool = Field(
        default=False,
        description="Send messages silently without notifications"
    )

    protect_content: bool = Field(
        default=False,
        description="Prevent message forwarding and saving"
    )

    message_thread_id: Optional[int] = Field(
        default=None,
        gt=0,
        description="Optional thread ID for forum/topic messages"
    )

    api_base_url: str = Field(
        default="https://api.telegram.org",
        description="Telegram API base URL"
    )

    max_message_length: int = Field(
        default=MessageLimit.MESSAGE_TEXT,
        ge=1,
        le=MessageLimit.MESSAGE_TEXT,
        description="Maximum message length in characters"
    )

    chat_type: Optional[ChatType] = Field(
        default=None,
        description="Type of chat (private, group, supergroup, channel)"
    )

    rate_limit: int = Field(
        default=RATE_LIMIT["rate_limit"],
        ge=1,
        le=60,
        description="Maximum number of messages per minute"
    )

    rate_period: int = Field(
        default=RATE_LIMIT["rate_period"],
        ge=30,
        le=3600,
        description="Rate limit period in seconds"
    )

    retry_attempts: int = Field(
        default=RATE_LIMIT["max_retries"],
        ge=1,
        le=5,
        description="Number of retry attempts for failed messages"
    )

    retry_delay: int = Field(
        default=RATE_LIMIT["retry_delay"],
        ge=1,
        le=30,
        description="Delay between retry attempts in seconds"
    )

    @field_validator("bot_token")
    def validate_bot_token(cls, v: str) -> str:
        """Validate Telegram bot token format.

        Args:
            v: Bot token to validate

        Returns:
            str: Validated bot token

        Raises:
            ValueError: If token format is invalid
        """
        if not v:
            raise ValueError("Bot token is required")

        # Token format: <bot_id>:<token>
        parts = v.split(":")
        if len(parts) != 2:
            raise ValueError("Invalid bot token format: missing separator")

        bot_id, token = parts

        if not bot_id.isdigit():
            raise ValueError("Invalid bot token format: invalid bot ID")

        if not re.match(r"^[A-Za-z0-9_-]{30,}$", token):
            raise ValueError("Invalid bot token format: invalid token")

        return v

    @field_validator("chat_id")
    def validate_chat_id(cls, v: Union[int, str]) -> Union[int, str]:
        """Validate Telegram chat ID format.

        Args:
            v: Chat ID to validate

        Returns:
            Union[int, str]: Validated chat ID

        Raises:
            ValueError: If chat ID format is invalid
        """
        if not validate_chat_id(v):
            raise ValueError(
                "Invalid chat ID format. Must be an integer, '-100' prefixed ID, "
                "or channel username starting with '@'"
            )
        return v

    @field_validator("api_base_url")
    def validate_api_url(cls, v: str) -> str:
        """Validate API base URL format.

        Args:
            v: API URL to validate

        Returns:
            str: Validated API URL

        Raises:
            ValueError: If URL format is invalid
        """
        if not v.startswith(("http://", "https://")):
            raise ValueError("API URL must start with http:// or https://")

        if "telegram.org" not in v.lower():
            raise ValueError("API URL must be from telegram.org domain")

        return v.rstrip("/")  # Remove trailing slashes

    def to_provider_config(self) -> dict:
        """Convert configuration to provider-compatible dictionary.

        Returns:
            dict: Configuration dictionary for provider initialization

        Example:
            >>> config = TelegramConfig(
            ...     bot_token="123456:ABC-DEF",
            ...     chat_id="-1001234567890"
            ... )
            >>> provider_config = config.to_provider_config()
            >>> assert "bot_token" in provider_config
        """
        config = {
            "bot_token": self.bot_token,
            "chat_id": self.chat_id,
            "parse_mode": self.parse_mode,
            "disable_notifications": self.disable_notifications,
            "protect_content": self.protect_content,
            "api_base_url": self.api_base_url,
            "max_message_length": self.max_message_length,
            "rate_limit": {
                "limit": self.rate_limit,
                "period": self.rate_period,
                "retry_attempts": self.retry_attempts,
                "retry_delay": self.retry_delay
            }
        }

        # Add optional settings if set
        if self.message_thread_id is not None:
            config["message_thread_id"] = self.message_thread_id
        if self.chat_type is not None:
            config["chat_type"] = self.chat_type

        return config

    class Config:
        """Pydantic model configuration."""
        frozen = True  # Make the config immutable
        validate_assignment = True
        allow_mutation = False
        extra = "forbid"  # Prevent additional fields
        title = "Telegram Bot Configuration"
        json_schema_extra = {
            "examples": [
                {
                    "bot_token": "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
                    "chat_id": "-1001234567890",
                    "parse_mode": "HTML",
                    "rate_limit": 20,
                    "rate_period": 60,
                    "retry_attempts": 3,
                    "retry_delay": 5
                }
            ]
        }
