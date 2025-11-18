"""Telegram provider plugin metadata registration."""

import re
from typing import Final

from mover_status.plugins import PluginMetadata, register_plugin
from mover_status.utils.sanitization import REDACTED, register_sanitization_pattern

# URL sanitization pattern for Telegram Bot API URLs
# Matches: https://api.telegram.org/bot<token>/method
_TELEGRAM_BOT_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"(https?://api\.telegram\.org/bot)([^/?#]+)(/[^?#]*)",
    re.IGNORECASE,
)

register_plugin(
    PluginMetadata(
        identifier="telegram",
        name="Telegram",
        package=__name__,
        version="0.1.0",
        description="Delivers mover status updates to Telegram chats.",
    )
)

# Register URL sanitization pattern at import time (before provider instantiation)
# This ensures sanitization works even in unit tests that don't create providers
register_sanitization_pattern(_TELEGRAM_BOT_PATTERN, rf"\1{REDACTED}\3")
