"""Discord provider configuration schema."""

from __future__ import annotations

import re
from typing import Annotated, Final
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator

_ALLOWED_DOMAINS: Final[tuple[str, ...]] = (
    "discord.com",
    "discordapp.com",
)
_WEBHOOK_PATH_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^/api/webhooks/\d+/\S+$",
)


class DiscordConfig(BaseModel):
    """Pydantic schema for Discord webhook configuration."""

    webhook_url: Annotated[
        str,
        Field(
            description="Discord webhook URL created from the channel's integrations menu",
        ),
    ]
    username: Annotated[
        str | None,
        Field(
            description="Optional override for the webhook display name",
            min_length=1,
            max_length=80,
        ),
    ] = None
    embed_color: Annotated[
        int | None,
        Field(
            description="24-bit color used for embed accents",
            ge=0x000000,
            le=0xFFFFFF,
        ),
    ] = None

    @field_validator("webhook_url")
    @classmethod
    def validate_webhook_url(cls, value: str) -> str:
        """Validate webhook URL format and domain."""
        cleaned = value.strip()
        parsed = urlparse(cleaned)
        if parsed.scheme.lower() != "https":
            msg = "Webhook URL must use HTTPS"
            raise ValueError(msg)
        host = (parsed.hostname or "").lower()
        if not any(host == domain or host.endswith(f".{domain}") for domain in _ALLOWED_DOMAINS):
            msg = (
                "Webhook URL must point to discord.com or discordapp.com "
                "(including canary/ptb subdomains)"
            )
            raise ValueError(msg)
        if not _WEBHOOK_PATH_PATTERN.match(parsed.path):
            msg = "Webhook URL must include /api/webhooks/<id>/<token> path"
            raise ValueError(msg)
        return cleaned

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str | None) -> str | None:
        """Normalize and validate the optional username."""
        if value is None:
            return None
        trimmed = value.strip()
        if not trimmed:
            msg = "Username cannot be empty when provided"
            raise ValueError(msg)
        return trimmed

    @field_validator("embed_color", mode="before")
    @classmethod
    def normalize_embed_color(cls, value: int | str | None) -> int | None:
        """Normalize color values, allowing hex strings."""
        if value is None:
            return None
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized.startswith("#"):
                normalized = normalized[1:]
            if normalized.startswith("0x"):
                normalized = normalized[2:]
            if not normalized:
                msg = "Embed color string cannot be empty"
                raise ValueError(msg)
            try:
                value = int(normalized, 16)
            except ValueError as exc:  # pragma: no cover - Pydantic attaches context
                msg = f"Invalid embed color string: {value}"
                raise ValueError(msg) from exc
        return value
