"""
Default configuration values for the Mover Status Monitor.

This module defines the default configuration dictionary that will be used
if no user configuration is provided or as a fallback for missing values.
"""

from typing import Dict, Any


# Default configuration dictionary
DEFAULT_CONFIG: Dict[str, Dict[str, Any]] = {
    # Notification settings
    "notification": {
        # Enable/disable notification platforms
        "use_telegram": False,
        "use_discord": False,

        # Telegram configuration
        "telegram_bot_token": "",
        "telegram_chat_id": "",

        # Discord configuration
        "discord_webhook_url": "",
        "discord_name": "Mover Bot",

        # Notification frequency (percentage increments)
        "notification_increment": 25,
    },

    # Monitoring settings
    "monitoring": {
        # Path to the mover executable
        "mover_executable": "/usr/local/sbin/mover",

        # Path to the cache directory to monitor
        "cache_directory": "/mnt/cache",

        # Polling interval in seconds
        "poll_interval": 1,
    },

    # Message templates
    "messages": {
        # Telegram message template (HTML formatting)
        "telegram_moving": (
            "Moving data from SSD Cache to HDD Array. &#10;"
            "Progress: <b>{percent}%</b> complete. &#10;"
            "Remaining data: {remaining_data}.&#10;"
            "Estimated completion time: {etc}.&#10;&#10;"
            "Note: Services like Plex may run slow or be unavailable during the move."
        ),

        # Discord message template (Markdown formatting)
        "discord_moving": (
            "Moving data from SSD Cache to HDD Array.\n"
            "Progress: **{percent}%** complete.\n"
            "Remaining data: {remaining_data}.\n"
            "Estimated completion time: {etc}.\n\n"
            "Note: Services like Plex may run slow or be unavailable during the move."
        ),

        # Completion message (used for both platforms)
        "completion": "Moving has been completed!",
    },

    # Path settings
    "paths": {
        # List of paths to exclude from monitoring
        "exclude": [],
    },

    # Debug settings
    "debug": {
        # Enable dry run mode (test notifications without monitoring)
        "dry_run": False,

        # Enable debug logging
        "enable_debug": False,
    },
}
