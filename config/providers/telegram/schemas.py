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

from typing import List, Optional, Union

from pydantic import (
    BaseModel,
    Field,
    HttpUrl,
    model_validator,
)

from config.constants import API, ErrorMessages
from config.providers.base import ProviderConfigModel
from config.providers.telegram.types import validate_chat_id
from shared.providers.telegram import (
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
    """Schema for Telegram inline keyboard markup validation."""
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


class BotConfigSchema(ProviderConfigModel):
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
    def validate_chat_id_format(self) -> "BotConfigSchema":
        """Validate chat ID format."""
        if not validate_chat_id(self.chat_id):
            raise ValueError(ErrorMessages.INVALID_CHAT_ID.format(
                chat_id=self.chat_id
            ))
        return self

    @model_validator(mode="after")
    def validate_api_url(self) -> "BotConfigSchema":
        """Validate API base URL."""
        if not str(self.api_base_url).startswith("https://"):
            raise ValueError(ErrorMessages.INSECURE_URL.format(
                url=self.api_base_url
            ))
        return self


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
    # Check text length
    if len(text) > MessageLimit.MESSAGE_TEXT:
        raise ValueError(ErrorMessages.MESSAGE_TOO_LONG.format(
            max_length=MessageLimit.MESSAGE_TEXT
        ))

    # Validate entities if present
    if entities:
        if len(entities) > MessageLimit.ENTITIES:
            raise ValueError(ErrorMessages.TOO_MANY_ENTITIES.format(
                max_entities=MessageLimit.ENTITIES
            ))

        # Check entity positions
        text_length = len(text)
        for entity in entities:
            if entity.offset < 0 or entity.offset >= text_length:
                raise ValueError(ErrorMessages.INVALID_ENTITY_OFFSET.format(
                    offset=entity.offset
                ))
            if entity.offset + entity.length > text_length:
                raise ValueError(ErrorMessages.INVALID_ENTITY_LENGTH.format(
                    length=entity.length,
                    offset=entity.offset
                ))

    return True
