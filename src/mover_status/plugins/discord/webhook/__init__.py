"""Discord webhook client for sending notifications."""

from __future__ import annotations

from .client import DiscordWebhookClient, DiscordEmbed
from .error_handling import (
    DiscordApiError,
    DiscordErrorType,
    DiscordErrorClassifier,
    WebhookValidator,
    AdvancedRateLimiter,
    with_discord_error_handling,
)

__all__ = [
    "DiscordWebhookClient",
    "DiscordEmbed",
    "DiscordApiError",
    "DiscordErrorType",
    "DiscordErrorClassifier",
    "WebhookValidator",
    "AdvancedRateLimiter",
    "with_discord_error_handling",
]
