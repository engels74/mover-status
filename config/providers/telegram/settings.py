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
from typing import Any, Dict, Optional

from pydantic import Field, field_validator

from config.providers.base import BaseProviderSettings


class TelegramSettings(BaseProviderSettings):
    """Telegram bot configuration settings."""

    bot_token: Optional[str] = Field(
        default=None,
        description="Telegram bot API token",
        examples=["123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"]
    )

    chat_id: Optional[str] = Field(
        default=None,
        description="Telegram chat ID (group, channel, or user)",
        examples=["-1001234567890", "@channelname"]
    )

    parse_mode: str = Field(
        default="HTML",
        pattern="^(HTML|MarkdownV2|None)$",
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
            pattern = r"^\d+:[A-Za-z0-9-_]+$"
            if not re.match(pattern, v):
                raise ValueError("Invalid bot token format")

        return v

    @field_validator("chat_id")
    @classmethod
    def validate_chat_id(cls, v: Optional[str], info: Any) -> Optional[str]:
        """Validate Telegram chat ID format.

        Args:
            v: Chat ID to validate
            info: Validation context information

        Returns:
            Optional[str]: Validated chat ID

        Raises:
            ValueError: If chat ID is invalid or missing when enabled
        """
        enabled = info.data.get("enabled", False)

        if enabled and not v:
            raise ValueError("Chat ID must be provided when Telegram is enabled")

        if v:
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

        return v

    @field_validator("api_base_url")
    @classmethod
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

    def to_provider_config(self) -> Dict:
        """Convert settings to Telegram provider configuration.

        Returns:
            Dict: Telegram provider configuration dictionary
        """
        config = super().to_provider_config()
        config.update({
            "bot_token": self.bot_token,
            "chat_id": self.chat_id,
            "parse_mode": self.parse_mode,
            "disable_notifications": self.disable_notifications,
            "protect_content": self.protect_content,
            "message_thread_id": self.message_thread_id,
            "api_base_url": self.api_base_url
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
