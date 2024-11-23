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
    model_validator,
)

from config.providers.telegram.types import validate_chat_id
from shared.types.telegram import (
    MessageEntity,
    MessageLimit,
    ParseMode,
)


class MessageEntitySchema(BaseModel):
    """Schema for Telegram message entity validation."""
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
    user: Optional[dict] = Field(
        default=None,
        description="User object for text_mention entities"
    )
    language: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=64,
        pattern=r"^[a-zA-Z0-9_-]+$",
        description="Programming language for pre entities"
    )

    @model_validator(mode='after')
    def validate_entity_requirements(self) -> 'MessageEntitySchema':
        """Validate entity type-specific requirements."""
        if self.type == "text_link" and not self.url:
            raise ValueError("URL is required for text_link entities")
        if self.type == "text_mention" and not self.user:
            raise ValueError("User object is required for text_mention entities")
        if self.type == "pre" and self.language and not re.match(r"^[a-zA-Z0-9_-]+$", self.language):
            raise ValueError("Invalid language format for pre entity")
        return self


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
        pattern=r"^[a-zA-Z0-9_-]+$",
        description="Data to send in callback query"
    )

    @model_validator(mode='after')
    def validate_button_options(self) -> 'InlineKeyboardButtonSchema':
        """Validate button has exactly one optional field."""
        option_count = sum(1 for opt in [self.url, self.callback_data] if opt is not None)
        if option_count != 1:
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
    def validate_keyboard_structure(self) -> 'InlineKeyboardMarkupSchema':
        """Validate keyboard dimensions and limits."""
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
        pattern=r"^\d+:[A-Za-z0-9_-]{35,}$",
        examples=["123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"]
    )
    chat_id: Union[int, str] = Field(
        ...,
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

    @model_validator(mode='after')
    def validate_chat_id_format(self) -> 'BotConfigSchema':
        """Validate chat ID format."""
        if not validate_chat_id(self.chat_id):
            raise ValueError("Invalid chat ID format")
        return self

    @model_validator(mode='after')
    def validate_api_url(self) -> 'BotConfigSchema':
        """Validate API base URL."""
        url_str = str(self.api_base_url).rstrip('/')
        if "api.telegram.org" not in url_str:
            raise ValueError("API URL must be from api.telegram.org domain")
        return self

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

    if len(text.encode('utf-16')) // 2 > MessageLimit.MESSAGE_TEXT:
        raise ValueError(f"Text exceeds {MessageLimit.MESSAGE_TEXT} UTF-16 code units")

    if entities:
        if len(entities) > MessageLimit.ENTITIES:
            raise ValueError(f"Maximum {MessageLimit.ENTITIES} entities allowed")

        text_length = len(text.encode('utf-16')) // 2
        for entity in entities:
            offset = entity["offset"]
            length = entity["length"]
            if offset < 0 or length <= 0 or offset + length > text_length:
                raise ValueError("Invalid entity position or length")

    return True
