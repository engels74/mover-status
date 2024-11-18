# config/providers/telegram/settings.py

"""
Telegram-specific configuration models and settings.
Extends base provider settings with Telegram Bot API configuration.

Example:
    >>> from config.providers.telegram.settings import TelegramSettings
    >>> settings = TelegramSettings(
    ...     enabled=True,
    ...     bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
    ...     chat_id="-1001234567890"
    ... )
"""

import re
from typing import Any, Dict, Optional, Union

from pydantic import Field, HttpUrl, field_validator

from config.providers.base import BaseProviderSettings
from config.providers.telegram.schemas import BotConfigSchema
from shared.providers.telegram import (
    ChatType,
    MessageLimit,
    ParseMode,
    validate_chat_id,
)


class TelegramSettings(BaseProviderSettings):
    """Telegram bot configuration settings."""

    bot_token: Optional[str] = Field(
        default=None,
        description="Telegram bot API token",
        examples=["123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"]
    )

    chat_id: Optional[Union[int, str]] = Field(
        default=None,
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

    api_base_url: HttpUrl = Field(
        default="https://api.telegram.org",
        description="Telegram API base URL"
    )

    max_message_length: int = Field(
        default=MessageLimit.MESSAGE_TEXT,
        description="Maximum message length in characters"
    )

    chat_type: Optional[ChatType] = Field(
        default=None,
        description="Type of chat (private, group, supergroup, channel)"
    )

    @field_validator("bot_token")
    @classmethod
    def validate_bot_token(cls, v: Optional[str], info: Any) -> Optional[str]:
        """Validate Telegram bot token format and presence.

        Args:
            v: Bot token to validate
            info: Validation context information

        Returns:
            Optional[str]: Validated bot token

        Raises:
            ValueError: If token is invalid or missing when enabled
        """
        enabled = info.data.get("enabled", False)

        if enabled and not v:
            raise ValueError("Bot token must be provided when Telegram is enabled")

        if v:
            # Token format: numbers:alphanumeric-_
            pattern = r"^\d+:[A-Za-z0-9_-]{30,}$"
            if not re.match(pattern, v):
                raise ValueError(
                    "Invalid bot token format. Expected format: NUMBER:ALPHANUMERIC"
                )

        return v

    @field_validator("chat_id")
    @classmethod
    def validate_chat_id_field(cls, v: Optional[Union[int, str]], info: Any) -> Optional[Union[int, str]]:
        """Validate Telegram chat ID format.

        Args:
            v: Chat ID to validate
            info: Validation context information

        Returns:
            Optional[Union[int, str]]: Validated chat ID

        Raises:
            ValueError: If chat ID is invalid or missing when enabled
        """
        enabled = info.data.get("enabled", False)

        if enabled and v is None:
            raise ValueError("Chat ID must be provided when Telegram is enabled")

        if v is not None:
            if not validate_chat_id(v):
                raise ValueError(
                    "Invalid chat ID format. Must be an integer, '-100' prefixed ID, "
                    "or channel username starting with '@'"
                )

        return v

    @field_validator("api_base_url")
    @classmethod
    def validate_api_url(cls, v: HttpUrl) -> HttpUrl:
        """Validate API base URL.

        Args:
            v: API URL to validate

        Returns:
            HttpUrl: Validated API URL

        Raises:
            ValueError: If URL is invalid
        """
        parsed = str(v).rstrip("/")
        if not parsed.startswith(("http://", "https://")):
            raise ValueError("API URL must start with http:// or https://")

        if "api.telegram.org" not in parsed:
            raise ValueError("API URL must be from api.telegram.org domain")

        return HttpUrl(parsed)

    @field_validator("max_message_length")
    @classmethod
    def validate_message_length(cls, v: int) -> int:
        """Validate maximum message length.

        Args:
            v: Message length to validate

        Returns:
            int: Validated message length

        Raises:
            ValueError: If length exceeds Telegram limits
        """
        if not 1 <= v <= MessageLimit.MESSAGE_TEXT:
            raise ValueError(
                f"Message length must be between 1 and {MessageLimit.MESSAGE_TEXT}"
            )
        return v

    def to_provider_config(self) -> Dict:
        """Convert settings to Telegram provider configuration.

        Returns:
            Dict: Telegram provider configuration dictionary
        """
        # Get base configuration
        config = super().to_provider_config()

        # Create bot config using schema
        bot_config = None
        if self.bot_token and self.chat_id:
            bot_config = BotConfigSchema(
                bot_token=self.bot_token,
                chat_id=str(self.chat_id),
                parse_mode=self.parse_mode,
                disable_notifications=self.disable_notifications,
                protect_content=self.protect_content,
                message_thread_id=self.message_thread_id,
                api_base_url=str(self.api_base_url)
            ).model_dump()

        # Add Telegram-specific configuration
        config.update({
            "bot_config": bot_config,
            "max_message_length": self.max_message_length,
            "chat_type": self.chat_type.value if self.chat_type else None
        })

        return config

    model_config = {
        "validate_assignment": True,
        "extra": "forbid",
        "json_schema_extra": {
            "examples": [
                {
                    "enabled": True,
                    "bot_token": "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
                    "chat_id": "-1001234567890",
                    "parse_mode": "HTML",
                    "disable_notifications": False,
                    "rate_limit": {
                        "rate_limit": 20,
                        "rate_period": 60,
                        "retry_attempts": 3,
                        "retry_delay": 5
                    }
                }
            ]
        }
    }
