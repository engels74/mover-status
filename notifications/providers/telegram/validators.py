# notifications/providers/telegram/validators.py

"""
Telegram-specific configuration validation.
Handles validation of bot tokens, chat IDs, and Telegram-specific message constraints.

Example:
    >>> validator = TelegramValidator()
    >>> config = {
    ...     "bot_token": "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
    ...     "chat_id": "-1001234567890"
    ... }
    >>> validated = validator.validate_config(config)
"""

import re
from typing import Any, Dict, Optional, Union

from pydantic import HttpUrl

from config.constants import JsonDict
from shared.types.telegram import ChatType, MessageLimit, ParseMode
from utils.validators import (
    BaseProviderValidator,
    ValidationError,
)


class TelegramValidationError(ValidationError):
    """Telegram-specific validation error."""
    pass


class TelegramValidator(BaseProviderValidator):
    """Validates Telegram bot configurations and message content."""

    API_DOMAIN = "api.telegram.org"
    ALLOWED_SCHEMES = ["https"]
    DEFAULT_PARSE_MODE = ParseMode.HTML
    BOT_TOKEN_PATTERN = r"^\d+:[A-Za-z0-9_-]{30,}$"
    CHANNEL_USERNAME_PATTERN = r"^@[A-Za-z0-9_]{5,}$"

    @classmethod
    def validate_bot_token(
        cls,
        token: Optional[str],
        required: bool = True
    ) -> Optional[str]:
        """Validate Telegram bot token format.

        Args:
            token: Bot token to validate
            required: Whether token is required

        Returns:
            Optional[str]: Validated bot token or None

        Raises:
            ValidationError: If bot token is invalid

        Example:
            >>> token = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
            >>> validated = TelegramValidator.validate_bot_token(token)
        """
        if not token:
            if required:
                raise ValidationError("Bot token is required")
            return None

        # Token format: <bot_id>:<token>
        parts = token.split(":")
        if len(parts) != 2:
            raise ValidationError("Invalid bot token format: missing separator")

        bot_id, token_part = parts

        if not bot_id.isdigit():
            raise ValidationError("Invalid bot token format: invalid bot ID")

        if not re.match(r"^[A-Za-z0-9_-]{30,}$", token_part):
            raise ValidationError(
                "Invalid bot token format: token must be at least 30 characters"
            )

        return token

    @classmethod
    def validate_chat_id(
        cls,
        chat_id: Optional[Union[int, str]],
        required: bool = True
    ) -> Optional[Union[int, str]]:
        """Validate Telegram chat ID format.

        Args:
            chat_id: Chat ID to validate
            required: Whether chat ID is required

        Returns:
            Optional[Union[int, str]]: Validated chat ID or None

        Raises:
            ValidationError: If chat ID is invalid

        Example:
            >>> chat_id = "-1001234567890"
            >>> validated = TelegramValidator.validate_chat_id(chat_id)
        """
        if chat_id is None:
            if required:
                raise ValidationError("Chat ID is required")
            return None

        # Handle integer chat IDs
        if isinstance(chat_id, int):
            return chat_id

        chat_id_str = str(chat_id)

        # Channel username format (@channel)
        if chat_id_str.startswith("@"):
            if not re.match(cls.CHANNEL_USERNAME_PATTERN, chat_id_str):
                raise ValidationError(
                    "Invalid channel username format. Must start with @ "
                    "followed by 5+ alphanumeric characters or underscores"
                )
            return chat_id_str

        # Group/supergroup format (-100{9,10 digits})
        if chat_id_str.startswith("-100"):
            remaining = chat_id_str[4:]
            if not remaining.isdigit() or len(remaining) not in (9, 10):
                raise ValidationError(
                    "Invalid group ID format. Must be -100 followed by 9-10 digits"
                )
            return chat_id_str

        # Private chat or basic group ID
        if not chat_id_str.replace("-", "").isdigit():
            raise ValidationError("Invalid chat ID format. Must be a number")

        return int(chat_id_str)

    @classmethod
    def validate_parse_mode(
        cls,
        mode: Optional[str]
    ) -> ParseMode:
        """Validate message parse mode.

        Args:
            mode: Parse mode to validate

        Returns:
            ParseMode: Validated parse mode

        Raises:
            ValidationError: If parse mode is invalid

        Example:
            >>> mode = "HTML"
            >>> validated = TelegramValidator.validate_parse_mode(mode)
        """
        if not mode:
            return cls.DEFAULT_PARSE_MODE

        try:
            return ParseMode(mode)
        except ValueError as err:
            valid_modes = ", ".join(m.value for m in ParseMode)
            raise ValidationError(
                f"Invalid parse mode. Must be one of: {valid_modes}"
            ) from err

    @classmethod
    def validate_api_url(
        cls,
        url: Optional[Union[str, HttpUrl]]
    ) -> Optional[str]:
        """Validate Telegram API base URL.

        Args:
            url: API URL to validate

        Returns:
            Optional[str]: Validated API URL or None

        Raises:
            URLValidationError: If API URL is invalid

        Example:
            >>> url = "https://api.telegram.org"
            >>> validated = TelegramValidator.validate_api_url(url)
        """
        if not url:
            return f"https://{cls.API_DOMAIN}"

        url_str = cls.validate_url(
            url,
            required_domain=cls.API_DOMAIN,
            allowed_schemes=cls.ALLOWED_SCHEMES,
            required=False
        )
        if not url_str:
            return None

        return url_str.rstrip("/")

    @classmethod
    def validate_message_thread_id(
        cls,
        thread_id: Optional[int]
    ) -> Optional[int]:
        """Validate message thread ID.

        Args:
            thread_id: Thread ID to validate

        Returns:
            Optional[int]: Validated thread ID or None

        Raises:
            ValidationError: If thread ID is invalid

        Example:
            >>> thread_id = 123456
            >>> validated = TelegramValidator.validate_message_thread_id(thread_id)
        """
        if thread_id is None:
            return None

        if not isinstance(thread_id, int):
            raise ValidationError("Message thread ID must be an integer")

        if thread_id <= 0:
            raise ValidationError("Message thread ID must be positive")

        return thread_id

    @classmethod
    def validate_message_length(
        cls,
        text: str,
        limit: Optional[int] = None
    ) -> str:
        """Validate message text length.

        Args:
            text: Message text to validate
            limit: Optional custom length limit

        Returns:
            str: Validated message text

        Raises:
            ValidationError: If message is too long

        Example:
            >>> text = "Hello, world!"
            >>> validated = TelegramValidator.validate_message_length(text)
        """
        if not text:
            raise ValidationError("Message text cannot be empty")

        max_length = limit or MessageLimit.MESSAGE_TEXT
        if len(text.encode('utf-16-le')) // 2 > max_length:
            raise ValidationError(f"Message exceeds {max_length} characters (UTF-16)")

        return text

    def validate_config(self, config: Dict[str, Any]) -> JsonDict:
        """Validate complete Telegram bot configuration.

        Args:
            config: Configuration dictionary to validate

        Returns:
            JsonDict: Validated configuration dictionary

        Raises:
            TelegramValidationError: If configuration is invalid

        Example:
            >>> config = {
            ...     "bot_token": "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
            ...     "chat_id": "-1001234567890",
            ...     "parse_mode": "HTML"
            ... }
            >>> validated = validator.validate_config(config)
        """
        try:
            # Validate required fields
            bot_token = self.validate_bot_token(config.get("bot_token"), required=True)
            chat_id = self.validate_chat_id(config.get("chat_id"), required=True)

            # Validate optional fields
            parse_mode = self.validate_parse_mode(config.get("parse_mode"))
            api_url = self.validate_api_url(config.get("api_base_url"))
            thread_id = self.validate_message_thread_id(config.get("message_thread_id"))

            # Validate message settings
            max_length = config.get("max_message_length", MessageLimit.MESSAGE_TEXT)
            if not 1 <= max_length <= MessageLimit.MESSAGE_TEXT:
                raise ValidationError(
                    f"Message length limit must be between 1 and {MessageLimit.MESSAGE_TEXT}"
                )

            # Validate rate limits
            rate_limit = config.get("rate_limit", 20)
            rate_period = config.get("rate_period", 60)
            self.validate_rate_limits(rate_limit, rate_period)

            # Validate boolean flags
            disable_notifications = bool(config.get("disable_notifications", False))
            protect_content = bool(config.get("protect_content", False))

            # Optional chat type
            chat_type = None
            if "chat_type" in config:
                try:
                    chat_type = ChatType(config["chat_type"])
                except ValueError as err:
                    valid_types = ", ".join(t.value for t in ChatType)
                    raise ValidationError(
                        f"Invalid chat type. Must be one of: {valid_types}"
                    ) from err

            return {
                "bot_token": bot_token,
                "chat_id": chat_id,
                "parse_mode": parse_mode,
                "api_base_url": api_url,
                "message_thread_id": thread_id,
                "max_message_length": max_length,
                "disable_notifications": disable_notifications,
                "protect_content": protect_content,
                "chat_type": chat_type,
                "rate_limit": rate_limit,
                "rate_period": rate_period,
            }

        except ValidationError as err:
            raise TelegramValidationError(str(err)) from err
        except Exception as err:
            raise TelegramValidationError("Configuration validation failed") from err
