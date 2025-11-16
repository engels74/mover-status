"""Telegram provider configuration schema."""

from __future__ import annotations

import re
from typing import Annotated, Final, Literal

from pydantic import BaseModel, Field, field_validator

_BOT_TOKEN_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^\d+:[A-Za-z0-9_-]{35,}$",
)
_CHAT_ID_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^(@[a-zA-Z0-9_]{5,}|-?\d+)$",
)


class TelegramConfig(BaseModel):
    """Pydantic schema for Telegram bot configuration."""

    bot_token: Annotated[
        str,
        Field(
            description="Telegram bot token from BotFather",
        ),
    ]
    chat_id: Annotated[
        str,
        Field(
            description="Target chat ID (user, group, or channel)",
        ),
    ]
    parse_mode: Annotated[
        Literal["HTML", "Markdown", "MarkdownV2"] | None,
        Field(
            description="Message formatting mode",
        ),
    ] = "HTML"
    message_thread_id: Annotated[
        int | None,
        Field(
            description="Message thread ID for topic/forum messages",
            ge=1,
        ),
    ] = None
    disable_notification: Annotated[
        bool,
        Field(
            description="Send notification silently",
        ),
    ] = False

    @field_validator("bot_token")
    @classmethod
    def validate_bot_token(cls, value: str) -> str:
        """Validate bot token format."""
        cleaned = value.strip()
        if not _BOT_TOKEN_PATTERN.match(cleaned):
            msg = "Bot token must be in format: <numeric_id>:<token> (token: 35+ alphanumeric chars, _, -)"
            raise ValueError(msg)
        return cleaned

    @field_validator("chat_id")
    @classmethod
    def validate_chat_id(cls, value: str) -> str:
        """Validate chat ID format."""
        cleaned = value.strip()
        if not cleaned:
            msg = "Chat ID cannot be empty"
            raise ValueError(msg)
        if not _CHAT_ID_PATTERN.match(cleaned):
            msg = "Chat ID must be numeric (user/group) or @username (channel)"
            raise ValueError(msg)
        return cleaned
