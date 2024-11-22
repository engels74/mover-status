# notifications/providers/telegram/config.py

"""
Configuration models for Telegram bot notifications.
Provides Pydantic models for configuration validation and type safety.

Example:
    >>> from notifications.telegram.config import TelegramConfig
    >>> config = TelegramConfig(
    ...     bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
    ...     chat_id="-1001234567890",
    ...     parse_mode="HTML"
    ... )
"""

import re
from typing import Optional

from pydantic import BaseModel, Field, validator

from notifications.telegram.types import (
    RATE_LIMIT,
    ParseMode,
)


class TelegramConfig(BaseModel):
    """Telegram bot configuration settings."""

    bot_token: str = Field(
        ...,  # Required field
        description="Telegram bot API token",
        examples=["123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"]
    )

    chat_id: str = Field(
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

    api_base_url: str = Field(
        default="https://api.telegram.org",
        description="Telegram API base URL"
    )

    message_thread_id: Optional[int] = Field(
        default=None,
        description="Optional thread ID for forum/topic messages",
        ge=1
    )

    @validator("bot_token")
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

        # Token format: numbers:alphanumeric-_
        pattern = r"^\d+:[A-Za-z0-9-_]+$"
        if not re.match(pattern, v):
            raise ValueError("Invalid bot token format")

        return v

    @validator("chat_id")
    def validate_chat_id(cls, v: str) -> str:
        """Validate Telegram chat ID format.

        Args:
            v: Chat ID to validate

        Returns:
            str: Validated chat ID

        Raises:
            ValueError: If chat ID format is invalid
        """
        if not v:
            raise ValueError("Chat ID is required")

        # Channel usernames start with @
        if v.startswith("@"):
            if not re.match(r"^@[A-Za-z0-9_]{5,}$", v):
                raise ValueError("Invalid channel username format")
            return v

        # Group/channel IDs are negative integers
        # Private chat IDs are positive integers
        try:
            int(v)  # Validate it's a number
            return v
        except ValueError as err:
            raise ValueError("Chat ID must be a number or channel username") from err

    @validator("api_base_url")
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
        return v.rstrip("/")  # Remove trailing slashes

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
                    "rate_period": 60
                }
            ]
        }

    def to_provider_config(self) -> dict:
        """Convert configuration to provider-compatible dictionary.

        Returns:
            dict: Configuration dictionary for provider initialization
        """
        return {
            "bot_token": self.bot_token,
            "chat_id": self.chat_id,
            "parse_mode": self.parse_mode,
            "disable_notifications": self.disable_notifications,
            "protect_content": self.protect_content,
            "message_thread_id": self.message_thread_id,
            "api_base_url": self.api_base_url,
            "rate_limit": {
                "limit": self.rate_limit,
                "period": self.rate_period,
                "retry_attempts": self.retry_attempts,
                "retry_delay": self.retry_delay
            }
        }
