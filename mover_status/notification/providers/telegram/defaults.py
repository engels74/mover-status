"""
Default configuration values for the Telegram notification provider.

This module defines the default configuration dictionary specific to the Telegram
notification provider. These values will be used if no user configuration is provided
or as a fallback for missing values.
"""

from typing import Any


# Telegram provider default configuration
TELEGRAM_DEFAULTS: dict[str, Any] = {
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
