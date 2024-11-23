# config/providers/telegram/schemas.py

"""
Validation schemas for Telegram bot configuration.
Provides Pydantic models for configuration validation and type safety.

Example:
    >>> from config.providers.telegram.schemas import BotConfigSchema
    >>> config = BotConfigSchema(
    ...     bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
    ...     chat_id="-1001234567890"
    ... )
"""

import re
from typing import List, Optional, Union

from pydantic import (
    BaseModel,
    Field,
    HttpUrl,
    field_validator,
    model_validator,
)

from shared.types.telegram import (
    MessageEntity,
    MessageLimit,
    ParseMode,
)


class MessageEntitySchema(BaseModel):
    """Schema for Telegram message entity validation."""
    type: str = Field(
        ...,
        description="Type of the entity"
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
    user: Optional[dict] = Field(
        default=None,
        description="User object for text_mention entities"
    )
    language: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=64,
        description="Programming language for pre entities"
    )

    @field_validator('type')
    @classmethod
    def validate_entity_type(cls, v: str) -> str:
        """Validate entity type is supported."""
        allowed_types = {
            "bold", "italic", "underline", "strikethrough",
            "code", "pre", "text_link", "text_mention", "url",
            "email", "phone_number", "hashtag", "mention"
        }
        if v not in allowed_types:
            raise ValueError(f"Unsupported entity type: {v}")
        return v


class InlineKeyboardButtonSchema(BaseModel):
    """Schema for Telegram inline keyboard button validation."""
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
        description="Data to send in callback query"
    )

    @model_validator(mode='after')
    def validate_button(self) -> 'InlineKeyboardButtonSchema':
        """Validate button has exactly one of the optional fields."""
        fields = [self.url, self.callback_data]
        if len([f for f in fields if f is not None]) != 1:
            raise ValueError("Button must have exactly one of: url, callback_data")
        return self


class InlineKeyboardMarkupSchema(BaseModel):
    """Schema for Telegram inline keyboard markup validation."""
    inline_keyboard: List[List[InlineKeyboardButtonSchema]] = Field(
        ...,
        max_length=MessageLimit.KEYBOARD_ROWS,
        description="Array of button rows"
    )

    @model_validator(mode='after')
    def validate_keyboard(self) -> 'InlineKeyboardMarkupSchema':
        """Validate keyboard structure and limits."""
        for row in self.inline_keyboard:
            if len(row) > MessageLimit.BUTTONS_PER_ROW:
                raise ValueError(
                    f"Maximum {MessageLimit.BUTTONS_PER_ROW} buttons per row allowed"
                )
        return self


class BotConfigSchema(BaseModel):
    """Schema for Telegram bot configuration validation."""
    bot_token: str = Field(
        ...,
        description="Telegram bot API token",
        pattern=r"^\d+:[A-Za-z0-9_-]+$"
    )
    chat_id: Union[int, str] = Field(
        ...,
        description="Target chat ID or @username"
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
    api_base_url: HttpUrl = Field(
        default="https://api.telegram.org",
        description="Telegram Bot API base URL"
    )
    rate_limit: int = Field(
        default=20,
        ge=1,
        le=60,
        description="Rate limit per minute"
    )
    rate_period: int = Field(
        default=60,
        ge=30,
        le=3600,
        description="Rate limit period in seconds"
    )
    retry_attempts: int = Field(
        default=3,
        ge=1,
        le=5,
        description="Maximum retry attempts"
    )
    retry_delay: int = Field(
        default=5,
        ge=1,
        le=30,
        description="Delay between retries in seconds"
    )

    @field_validator('chat_id')
    @classmethod
    def validate_chat_id(cls, v: Union[int, str]) -> Union[int, str]:
        """Validate chat ID format."""
        if isinstance(v, int):
            return v

        if isinstance(v, str):
            if v.startswith("@"):
                # Channel username validation
                if not re.match(r"^@[A-Za-z0-9_]{5,}$", v):
                    raise ValueError("Invalid channel username format")
                return v

            try:
                # Convert to int for numeric chat IDs
                chat_id = int(v)
                if str(chat_id) != v:  # Ensure no decimal points
                    raise ValueError()
                return chat_id
            except ValueError as err:
                raise ValueError(
                    "Chat ID must be an integer or valid channel username"
                ) from err

        raise ValueError("Chat ID must be an integer or string")

    @field_validator('api_base_url')
    @classmethod
    def validate_api_url(cls, v: HttpUrl) -> HttpUrl:
        """Validate API base URL."""
        if "api.telegram.org" not in str(v):
            raise ValueError("API URL must be from api.telegram.org domain")
        return v

    class Config:
        """Pydantic model configuration."""
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
    if not text:
        raise ValueError("Message text cannot be empty")

    if len(text) > MessageLimit.MESSAGE_TEXT:
        raise ValueError(f"Text exceeds {MessageLimit.MESSAGE_TEXT} characters")

    if entities:
        if len(entities) > MessageLimit.ENTITIES:
            raise ValueError(f"Maximum {MessageLimit.ENTITIES} entities allowed")

        # Validate entity positions
        text_length = len(text)
        for entity in entities:
            offset = entity["offset"]
            length = entity["length"]
            if offset < 0 or length <= 0 or offset + length > text_length:
                raise ValueError("Invalid entity position or length")

    return True


def validate_keyboard_markup(markup: dict) -> bool:
    """Validate inline keyboard markup structure.

    Args:
        markup: Keyboard markup to validate

    Returns:
        bool: True if markup is valid

    Raises:
        ValueError: If markup structure is invalid
    """
    if "inline_keyboard" not in markup:
        raise ValueError("Missing inline_keyboard field")

    keyboard = markup["inline_keyboard"]
    if not isinstance(keyboard, list) or not all(isinstance(row, list) for row in keyboard):
        raise ValueError("Invalid keyboard structure")

    if len(keyboard) > MessageLimit.KEYBOARD_ROWS:
        raise ValueError(f"Maximum {MessageLimit.KEYBOARD_ROWS} keyboard rows allowed")

    for row in keyboard:
        if len(row) > MessageLimit.BUTTONS_PER_ROW:
            raise ValueError(f"Maximum {MessageLimit.BUTTONS_PER_ROW} buttons per row allowed")

        for button in row:
            if not isinstance(button, dict):
                raise ValueError("Invalid button structure")
            if "text" not in button:
                raise ValueError("Missing button text")
            if len(button["text"]) > MessageLimit.BUTTON_TEXT:
                raise ValueError(f"Button text exceeds {MessageLimit.BUTTON_TEXT} characters")

    return True
