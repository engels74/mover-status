"""
Default configuration values for the Telegram notification provider.

This module defines the default configuration dictionary specific to the Telegram
notification provider. These values will be used if no user configuration is provided
or as a fallback for missing values.
"""

from typing import TypedDict


class TelegramDefaultsType(TypedDict):
    """Type definition for Telegram provider defaults."""
    name: str
    enabled: bool
    bot_token: str
    chat_id: str
    message_template: str
    parse_mode: str
    disable_notification: bool


# Telegram provider default configuration
TELEGRAM_DEFAULTS: TelegramDefaultsType = {
    # Provider identification
    "name": "telegram",
    "enabled": False,

    # API configuration
    "bot_token": "",
    "chat_id": "",

    # Message formatting
    "message_template": (
        "Moving data from SSD Cache to HDD Array. &#10;"
        "Progress: <b>{percent}%</b> complete. &#10;"
        "Remaining data: {remaining_data}.&#10;"
        "Estimated completion time: {etc}.&#10;&#10;"
        "Note: Services like Plex may run slow or be unavailable during the move."
    ),

    # Formatting options
    "parse_mode": "HTML",
    "disable_notification": False,
}
