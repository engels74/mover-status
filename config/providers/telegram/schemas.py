# config/providers/telegram/schemas.py

"""
Validation schemas for Telegram bot configuration and message formatting.
This module provides Pydantic models for validating and type-checking Telegram-specific
configuration, including bot settings, message entities, and inline keyboards.

Key components:
- BotConfigSchema: Core bot configuration and API settings
- MessageEntitySchema: Text formatting and entity validation
- InlineKeyboardSchema: Interactive button configuration
- Message content validation utilities

Example:
    >>> from config.providers.telegram.schemas import BotConfigSchema
    >>> config = BotConfigSchema(
    ...     bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
    ...     chat_id="-1001234567890",
    ...     parse_mode="HTML",
    ...     rate_limit=20
    ... )
"""

from typing import List, Optional, Union, Dict, Any
from enum import IntEnum, StrEnum

from pydantic import (
    BaseModel,
    Field,
    HttpUrl,
    model_validator,
    ValidationInfo,
)

from config.providers.base import BaseProviderSettings
from config.providers.telegram.types import validate_chat_id
from shared.providers.telegram import (
    MessageEntity,
    MessageLimit,
    ParseMode,
)


class API(IntEnum):
    """API-related constants for Telegram provider."""
    DEFAULT_TIMEOUT = 30
    DEFAULT_RETRIES = 3
    DEFAULT_RETRY_DELAY = 5
    MIN_RETRIES = 1
    MAX_RETRIES = 5
    MIN_RETRY_DELAY = 1
    MAX_RETRY_DELAY = 30
    DEFAULT_RATE_PERIOD = 60
    MIN_RATE_PERIOD = 30
    MAX_RATE_PERIOD = 3600


class ErrorMessages(StrEnum):
    """Error messages for Telegram-specific validation."""
    FIELD_REQUIRED = "Field '{field}' is required {context}"
    INVALID_BUTTON_CONFIG = "Button '{button}' must have exactly one of url or callback_data"
    ROW_TOO_LONG = "Row exceeds maximum number of buttons ({max_buttons})"
    INVALID_CHAT_ID = "Invalid chat ID format: {chat_id}"
    INSECURE_URL = "Only HTTPS URLs are allowed"
    MESSAGE_TOO_LONG = "Message exceeds maximum length"
    TOO_MANY_ENTITIES = "Too many entities in message"
    INVALID_ENTITY_OFFSET = "Entity offset is invalid"
    INVALID_ENTITY_LENGTH = "Entity length is invalid"


class MessageEntitySchema(BaseModel):
    """Schema for validating Telegram message formatting entities.

    This model validates special text entities like bold, italic, links, and code blocks
    according to Telegram Bot API specifications. It ensures proper UTF-16 offsets and
    required fields for specific entity types.

    Attributes:
        type (str): Entity type (bold, italic, code, text_link, etc.)
        offset (int): Starting position in UTF-16 code units
        length (int): Length of entity in UTF-16 code units
        url (Optional[HttpUrl]): URL for text_link entities
        language (Optional[str]): Programming language for code blocks

    Example:
        >>> entity = MessageEntitySchema(
        ...     type="text_link",
        ...     offset=0,
        ...     length=10,
        ...     url="https://example.com"
        ... )
    """
    type: str = Field(
        ...,  # Required field
        description="Type of the entity",
        examples=["bold", "italic", "code", "text_link"]
    )
    offset: int = Field(
        ...,
        ge=0,
        description="Offset in UTF-16 code units"
    )
    length: int = Field(
        ...,
        gt=0,
        description="Length in UTF-16 code units"
    )
    url: Optional[HttpUrl] = Field(
        default=None,
        description="URL for text_link entities"
    )
    language: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=8,
        pattern=r"^[a-zA-Z0-9-]+$",
        description="Programming language for pre entities"
    )

    @model_validator(mode="after")
    def validate_entity_type(self) -> "MessageEntitySchema":
        """Validate entity type and required fields."""
        if self.type == "text_link" and not self.url:
            raise ValueError(ErrorMessages.FIELD_REQUIRED.format(
                field="url",
                context="for text_link entities"
            ))
        if self.type == "pre" and not self.language:
            raise ValueError(ErrorMessages.FIELD_REQUIRED.format(
                field="language",
                context="for pre entities"
            ))
        return self


class InlineKeyboardButtonSchema(BaseModel):
    """Schema for validating Telegram inline keyboard buttons.

    This model ensures that buttons have valid text and exactly one action type
    (URL or callback data) as required by the Telegram Bot API.

    Attributes:
        text (str): Button label text
        url (Optional[HttpUrl]): URL to open when clicked
        callback_data (Optional[str]): Data for callback query

    Example:
        >>> button = InlineKeyboardButtonSchema(
        ...     text="Visit Website",
        ...     url="https://example.com"
        ... )
    """
    text: str = Field(
        ...,
        min_length=1,
        max_length=MessageLimit.BUTTON_TEXT,
        description="Button text"
    )
    url: Optional[HttpUrl] = Field(
        default=None,
        description="URL to open"
    )
    callback_data: Optional[str] = Field(
        default=None,
        max_length=MessageLimit.CALLBACK_DATA,
        pattern=r"^[a-zA-Z0-9_-]+$",
        description="Data to send in callback query"
    )

    @model_validator(mode="after")
    def validate_button_options(self) -> "InlineKeyboardButtonSchema":
        """Validate button has exactly one optional field."""
        options = [
            bool(self.url),
            bool(self.callback_data)
        ]
        if sum(options) != 1:
            raise ValueError(ErrorMessages.INVALID_BUTTON_CONFIG.format(
                button=self.text
            ))
        return self


class InlineKeyboardMarkupSchema(BaseModel):
    """Schema for validating Telegram inline keyboard layouts.

    This model validates the structure of inline keyboards, ensuring they meet
    Telegram's size limits and button arrangement requirements.

    Attributes:
        inline_keyboard (List[List[InlineKeyboardButtonSchema]]): Matrix of keyboard buttons

    Example:
        >>> keyboard = InlineKeyboardMarkupSchema(
        ...     inline_keyboard=[
        ...         [{"text": "Row 1 Button", "url": "https://example.com"}],
        ...         [{"text": "Row 2 Button", "callback_data": "action_1"}]
        ...     ]
        ... )
    """
    inline_keyboard: List[List[InlineKeyboardButtonSchema]] = Field(
        ...,
        max_length=MessageLimit.KEYBOARD_ROWS,
        description="Array of button rows"
    )

    @model_validator(mode="after")
    def validate_keyboard_structure(self) -> "InlineKeyboardMarkupSchema":
        """Validate keyboard dimensions and limits."""
        for row in self.inline_keyboard:
            if len(row) > MessageLimit.BUTTONS_PER_ROW:
                raise ValueError(ErrorMessages.ROW_TOO_LONG.format(
                    max_buttons=MessageLimit.BUTTONS_PER_ROW
                ))
        return self


class BotConfigSchema(BaseProviderSettings):
    """Schema for comprehensive Telegram bot configuration validation.

    This model validates all aspects of a Telegram bot's configuration, including
    authentication, chat targeting, message formatting, rate limiting, and retry policies.
    It extends the base provider configuration with Telegram-specific requirements.

    Attributes:
        bot_token (str): Bot API authentication token
        chat_id (Union[int, str]): Target chat identifier
        parse_mode (ParseMode): Message formatting mode
        disable_notification (bool): Silent message delivery option
        protect_content (bool): Content forwarding protection
        message_thread_id (Optional[int]): Forum topic thread ID
        api_base_url (str): Bot API endpoint URL
        rate_limit (int): Messages per minute limit
        rate_period (int): Rate limit window in seconds
        retry_attempts (int): Maximum API retry attempts
        retry_delay (int): Delay between retries
        timeout (float): API request timeout

    Example:
        >>> config = BotConfigSchema(
        ...     bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
        ...     chat_id="@channelname",
        ...     parse_mode="HTML",
        ...     rate_limit=20,
        ...     timeout=30.0
        ... )
    """
    bot_token: str = Field(
        ...,  # Required field
        description="Telegram bot API token",
        pattern=r"^\d+:[A-Za-z0-9_-]{35,}$",
        examples=["123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"]
    )
    chat_id: Union[int, str] = Field(
        ...,  # Required field
        description="Target chat ID or @username",
        examples=["-1001234567890", "@channelname"]
    )
    parse_mode: ParseMode = Field(
        default=ParseMode.HTML,
        description="Message parsing mode"
    )
    disable_notification: bool = Field(
        default=False,
        description="Send message silently"
    )
    protect_content: bool = Field(
        default=False,
        description="Protect message from forwarding/saving"
    )
    message_thread_id: Optional[int] = Field(
        default=None,
        gt=0,
        description="Message thread ID for forum topics"
    )
    api_base_url: str = Field(
        default="https://api.telegram.org",
        description="Telegram Bot API base URL",
        pattern=r"^https://.+"
    )
    rate_limit: int = Field(
        default=MessageLimit.MESSAGES_PER_MINUTE,
        ge=1,
        le=MessageLimit.MESSAGES_PER_MINUTE,
        description="Rate limit per minute"
    )
    rate_period: int = Field(
        default=API.DEFAULT_RATE_PERIOD,
        ge=API.MIN_RATE_PERIOD,
        le=API.MAX_RATE_PERIOD,
        description="Rate limit period in seconds"
    )
    retry_attempts: int = Field(
        default=API.DEFAULT_RETRIES,
        ge=API.MIN_RETRIES,
        le=API.MAX_RETRIES,
        description="Maximum retry attempts"
    )
    retry_delay: int = Field(
        default=API.DEFAULT_RETRY_DELAY,
        ge=API.MIN_RETRY_DELAY,
        le=API.MAX_RETRY_DELAY,
        description="Delay between retries in seconds"
    )
    timeout: float = Field(
        default=API.DEFAULT_TIMEOUT,
        ge=0.1,
        le=300.0,
        description="Request timeout in seconds",
        examples=[10.0, 30.0, 60.0]
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "bot_token": "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
                    "chat_id": "-1001234567890",
                    "parse_mode": "HTML",
                    "rate_limit": MessageLimit.MESSAGES_PER_MINUTE,
                    "rate_period": API.DEFAULT_RATE_PERIOD
                }
            ]
        }
    }

    @model_validator(mode="after")
    def validate_chat_id_format(self, info: ValidationInfo) -> "BotConfigSchema":
        """Validate chat ID format."""
        if not validate_chat_id(self.chat_id):
            raise ValueError(ErrorMessages.INVALID_CHAT_ID.format(
                chat_id=self.chat_id
            ))
        return self

    @model_validator(mode="after")
    def validate_api_url(self, info: ValidationInfo) -> "BotConfigSchema":
        """Validate API base URL."""
        if not str(self.api_base_url).startswith("https://"):
            raise ValueError(ErrorMessages.INSECURE_URL)
        return self

    @model_validator(mode="after")
    def validate_entities(self, info: ValidationInfo) -> "BotConfigSchema":
        """Validate message entities if present."""
        text = getattr(self, "text", None)
        entities = getattr(self, "entities", None)

        if text and entities:
            self.validate_entity_bounds(text, entities)
        return self

    def validate_entity_bounds(self, text: str, entities: List[MessageEntity]) -> None:
        """Validate entity offsets and lengths."""
        text_length = len(text)
        
        for entity in entities:
            # Safely access TypedDict fields with get()
            offset = entity.get("offset")
            length = entity.get("length")
            
            if offset is None or length is None:
                raise ValueError(ErrorMessages.FIELD_REQUIRED.format(
                    field="offset or length",
                    context="for entities"
                ))
                
            if offset < 0 or offset >= text_length:
                raise ValueError(ErrorMessages.INVALID_ENTITY_OFFSET)
                
            if length <= 0 or offset + length > text_length:
                raise ValueError(ErrorMessages.INVALID_ENTITY_LENGTH)


def validate_message_content(
    text: str,
    entities: Optional[List[MessageEntity]] = None
) -> bool:
    """Validate message content against Telegram limits.

    Args:
        text: Message text to validate
        entities: Optional message entities

    Returns:
        bool: True if content is valid

    Raises:
        ValueError: If content exceeds Telegram limits
    """
    if len(text) > MessageLimit.MESSAGE_TEXT:
        raise ValueError(ErrorMessages.MESSAGE_TOO_LONG)

    if not entities:
        return True

    if len(entities) > MessageLimit.ENTITIES:
        raise ValueError(ErrorMessages.TOO_MANY_ENTITIES)

    for entity in entities:
        # Safely access TypedDict fields with get()
        offset = entity.get("offset")
        length = entity.get("length")
        
        if offset is None or length is None:
            raise ValueError(ErrorMessages.FIELD_REQUIRED.format(
                field="offset or length",
                context="for entities"
            ))
            
        if offset < 0 or offset >= len(text):
            raise ValueError(ErrorMessages.INVALID_ENTITY_OFFSET)
            
        if length <= 0 or offset + length > len(text):
            raise ValueError(ErrorMessages.INVALID_ENTITY_LENGTH)

    return True
