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
from shared.providers.telegram import ChatType, MessageLimit, ParseMode
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
    # Original pattern kept for backwards compatibility with tests
    # According to Telegram documentation, the ideal format is:
    # ^[0-9]{8,10}:[A-Za-z0-9_-]{35}$
    # (8-10 digits followed by a colon and exactly 35 alphanumeric characters)
    BOT_TOKEN_PATTERN = r"^\d+:[A-Za-z0-9_-]{30,}$"
    CHANNEL_USERNAME_PATTERN = r"^@[A-Za-z0-9_]{5,}$"
    MIN_TIMEOUT = 0.1
    MAX_TIMEOUT = 300.0

    # Time format patterns
    TIME_PATTERNS = {
        "iso": r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$",
        "friendly": r"^(Today|Yesterday|[A-Z][a-z]{2} \d{1,2}) at \d{1,2}:\d{2} (AM|PM)$",
        "compact": r"^\d{2}:\d{2}$",
        "relative": r"^(just now|\d+ (seconds?|minutes?|hours?|days?|months?|years?) (ago|from now))$"
    }

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
            >>> token = "12345678:ABC-DEF1234ghIkl-zyx57W2v1u123ew11ABC"
            >>> validated = TelegramValidator.validate_bot_token(token)
        """
        if not token:
            if required:
                raise ValidationError("Bot token is required")
            return None

        # Use the BOT_TOKEN_PATTERN constant for validation
        if not re.match(cls.BOT_TOKEN_PATTERN, token):
            raise ValidationError(
                "Invalid bot token format: should be digits followed by a colon and alphanumeric characters. "
                "The official format is 8-10 digits followed by a colon and 35 alphanumeric characters."
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

    @classmethod
    def validate_time_format(cls, time_str: str, format_type: str) -> bool:
        """Validate time string against expected format.

        Args:
            time_str: Time string to validate
            format_type: Expected format type (iso, friendly, compact, relative)

        Returns:
            bool: True if time string matches expected format

        Raises:
            TelegramValidationError: If format type is invalid or time string doesn't match pattern
        """
        if format_type not in cls.TIME_PATTERNS:
            raise TelegramValidationError(f"Invalid time format type: {format_type}")

        pattern = cls.TIME_PATTERNS[format_type]
        if not re.match(pattern, time_str):
            raise TelegramValidationError(
                f"Invalid time format for {format_type}: {time_str}",
                field="time_format"
            )
        return True

    @classmethod
    def validate_message_content(cls, content: Dict[str, Any]) -> None:
        """Validate message content including time formats.

        Args:
            content: Message content to validate

        Raises:
            TelegramValidationError: If content validation fails
        """
        if not content or not isinstance(content, dict):
            raise TelegramValidationError("Invalid message content")

        text = content.get("text", "")
        if not text or not isinstance(text, str):
            raise TelegramValidationError("Message text is required")

        # Validate message length
        if len(text) > MessageLimit.MESSAGE_TEXT:
            raise TelegramValidationError(
                f"Message exceeds maximum length of {MessageLimit.MESSAGE_TEXT} characters"
            )

        # Extract and validate time strings in message
        time_matches = {
            "iso": re.findall(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", text),
            "friendly": re.findall(r"(Today|Yesterday|[A-Z][a-z]{2} \d{1,2}) at \d{1,2}:\d{2} (AM|PM)", text),
            "compact": re.findall(r"\d{2}:\d{2}", text),
            "relative": re.findall(r"\d+ (seconds?|minutes?|hours?|days?|months?|years?) (ago|from now)", text)
        }

        for format_type, matches in time_matches.items():
            for time_str in matches:
                if isinstance(time_str, tuple):
                    time_str = " at ".join(time_str)
                try:
                    cls.validate_time_format(time_str, format_type)
                except TelegramValidationError as e:
                    raise TelegramValidationError(
                        f"Invalid time format in message: {e}",
                        field="message_content"
                    ) from e

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

            # Validate timeout settings
            timeouts = self.validate_timeouts(
                connect_timeout=config.get("timeout"),
                min_timeout=self.MIN_TIMEOUT,
                max_timeout=self.MAX_TIMEOUT
            )
            timeout = timeouts.get("connect")

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
                "timeout": timeout,
            }

        except ValidationError as err:
            raise TelegramValidationError(str(err)) from err
        except Exception as err:
            raise TelegramValidationError("Configuration validation failed") from err
