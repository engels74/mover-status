# notifications/providers/telegram/config.py

"""
Telegram bot configuration management and validation.
Handles configuration parsing and validation using Pydantic models.

Example:
    >>> from notifications.providers.telegram import TelegramConfig
    >>> config = TelegramConfig(
    ...     enabled=True,
    ...     bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
    ...     chat_id="-1001234567890"
    ... )
    >>> provider_config = config.to_provider_config()
"""

from typing import Any, Dict, Optional, Union

from pydantic import Field, HttpUrl, field_validator

from config.providers.base import BaseProviderSettings
from notifications.providers.telegram.schemas import BotConfigSchema
from notifications.providers.telegram.validators import TelegramValidator
from shared.providers.telegram import (
    ChatType,
    MessageLimit,
    ParseMode,
)


class TelegramConfig(BaseProviderSettings):
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

    _validator: TelegramValidator = TelegramValidator()

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

        try:
            if v is not None:
                cls._validator.validate_bot_token(v, required=enabled)
            elif enabled:
                raise ValueError("Bot token must be provided when Telegram is enabled")
            return v
        except Exception as err:
            raise ValueError(str(err)) from err

    @field_validator("chat_id")
    @classmethod
    def validate_chat_id(cls, v: Optional[Union[int, str]], info: Any) -> Optional[Union[int, str]]:
        """Validate Telegram chat ID format.

        Args:
            v: Chat ID to validate
            info: Validation context information

        Returns:
            Optional[Union[int, str]]: Validated chat ID

        Raises:
            ValueError: If chat ID format is invalid
        """
        enabled = info.data.get("enabled", False)

        try:
            if v is not None:
                return cls._validator.validate_chat_id(v, required=enabled)
            elif enabled:
                raise ValueError("Chat ID must be provided when Telegram is enabled")
            return v
        except Exception as err:
            raise ValueError(str(err)) from err

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
        try:
            cls._validator.validate_api_url(str(v))
            return v
        except Exception as err:
            raise ValueError(str(err)) from err

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
            raise ValueError(f"Message length must be between 1 and {MessageLimit.MESSAGE_TEXT}")
        return v

    def to_provider_config(self) -> Dict[str, Any]:
        """Convert settings to Telegram provider configuration.

        Returns:
            Dict[str, Any]: Telegram provider configuration dictionary

        Example:
            >>> config = TelegramConfig(
            ...     bot_token="123456:ABC-DEF",
            ...     chat_id="-1001234567890"
            ... )
            >>> provider_config = config.to_provider_config()
            >>> assert "bot_token" in provider_config
        """
        # Get base configuration
        config = super().to_provider_config()

        # Create bot config using schema
        bot_config = None
        if self.bot_token and self.chat_id:
            try:
                bot_config = BotConfigSchema(
                    bot_token=self.bot_token,
                    chat_id=self.chat_id,
                    parse_mode=self.parse_mode,
                    disable_notifications=self.disable_notifications,
                    protect_content=self.protect_content,
                    message_thread_id=self.message_thread_id,
                    api_base_url=str(self.api_base_url),
                    max_message_length=self.max_message_length
                ).model_dump()

                # Validate complete bot configuration
                self._validator.validate_config(bot_config)
            except Exception as err:
                raise ValueError(f"Invalid bot configuration: {err}") from err

        # Add Telegram-specific configuration
        config.update({
            "bot_config": bot_config,
            "chat_type": self.chat_type.value if self.chat_type else None
        })

        return config

    class Config:
        """Pydantic model configuration."""
        validate_assignment = True
        extra = "forbid"
        json_schema_extra = {
            "examples": [
                {
                    "enabled": True,
                    "bot_token": "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
                    "chat_id": "-1001234567890",
                    "parse_mode": "HTML",
                    "rate_limit": {
                        "rate_limit": 20,
                        "rate_period": 60,
                        "retry_attempts": 3,
                        "retry_delay": 5
                    }
                }
            ]
        }
