# shared/providers/telegram/constants.py

"""Telegram-specific constants."""

from enum import StrEnum
from typing import Final, List


class TelegramDomains(StrEnum):
    """Telegram API domains."""
    API = "api.telegram.org"
    UPDATES = "updates.telegram.org"
    FILE = "file.telegram.org"
    GAMES = "games.telegram.org"
    PASSPORT = "passport.telegram.org"


ALLOWED_DOMAINS: Final[List[str]] = [
    "telegram.org",
    "telegram.me",
    "t.me",
    *[domain.value for domain in TelegramDomains]
]
