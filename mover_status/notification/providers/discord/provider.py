"""
Discord notification provider implementation.

This module provides the implementation of the Discord notification provider,
which sends notifications to Discord using webhooks.
"""

import logging
import re
from datetime import datetime
from typing import TypedDict, cast, override

import requests

from mover_status.notification.base import NotificationProvider
from mover_status.notification.formatter import RawValues
from mover_status.notification.providers.discord.formatter import (
    create_embed,
    format_discord_message,
)

# Get logger for this module
logger = logging.getLogger(__name__)

# Discord webhook URL pattern
DISCORD_WEBHOOK_URL_PATTERN = r"^https://discord\.com/api/webhooks/\d+/\S+$"


class EmbedColorsType(TypedDict):
    """Type definition for Discord embed colors."""
    low_progress: int
    mid_progress: int
    high_progress: int
    complete: int


class DiscordConfig(TypedDict, total=False):
    """Type definition for Discord provider configuration."""
    enabled: bool
    webhook_url: str
    username: str
    message_template: str
    use_embeds: bool
    embed_title: str
    embed_colors: EmbedColorsType


class DiscordProvider(NotificationProvider):
    """
    Discord notification provider.

    This class implements the NotificationProvider interface for sending
    notifications to Discord using webhooks.

    Attributes:
        name: The name of the notification provider.
        webhook_url: The Discord webhook URL.
        username: The username to display for the webhook.
        message_template: The template to use for formatting messages.
        use_embeds: Whether to use embeds for messages.
        embed_title: The title to use for embeds.
        embed_colors: The colors to use for embeds based on progress.
        enabled: Whether the provider is enabled.
    """

    def __init__(self, config: DiscordConfig) -> None:
        """
        Initialize the Discord notification provider.

        Args:
            config: The provider configuration.
        """
        super().__init__("discord")
        self.webhook_url: str = config.get("webhook_url", "")
        self.username: str = config.get("username", "Mover Bot")
        self.message_template: str = config.get("message_template", "")
        self.use_embeds: bool = config.get("use_embeds", True)
        self.embed_title: str = config.get("embed_title", "Mover: Moving Data")
        self.embed_colors: EmbedColorsType = config.get("embed_colors", {
            "low_progress": 16744576,  # Light Red (0-34%)
            "mid_progress": 16753920,  # Light Orange (35-65%)
            "high_progress": 9498256,  # Light Green (66-99%)
            "complete": 65280,         # Green (100%)
        })
        self.enabled: bool = config.get("enabled", False)

    @override
    def validate_config(self) -> list[str]:
        """
        Validate the provider configuration.

        Returns:
            A list of error messages. An empty list indicates a valid configuration.
        """
        errors: list[str] = []

        # Check required fields
        if not self.webhook_url:
            errors.append("Discord webhook_url is required")
        elif not re.match(DISCORD_WEBHOOK_URL_PATTERN, self.webhook_url):
            errors.append(f"Invalid webhook_url: {self.webhook_url}")

        return errors

    def _get_color_for_progress(self, percent: int) -> int:
        """
        Get the color for the given progress percentage.

        Args:
            percent: The progress percentage.

        Returns:
            The color code for the progress.
        """
        if percent >= 100:
            return self.embed_colors["complete"]
        elif percent >= 66:
            return self.embed_colors["high_progress"]
        elif percent >= 35:
            return self.embed_colors["mid_progress"]
        else:
            return self.embed_colors["low_progress"]

    @override
    def send_notification(self, message: str, **kwargs: object) -> bool:
        """
        Send a notification to Discord.

        Args:
            message: The message to send.
            **kwargs: Additional arguments.
                raw_values: Optional raw values to format the message with.

        Returns:
            True if the notification was sent successfully, False otherwise.
        """
        if not self.enabled:
            logger.info("Discord notifications are disabled")
            return False

        # Validate configuration
        errors = self.validate_config()
        if errors:
            logger.error("Invalid Discord configuration: %s", ", ".join(errors))
            return False

        # Format the message if raw_values are provided
        raw_values: RawValues = {}
        formatted_message = message

        if "raw_values" in kwargs and isinstance(kwargs["raw_values"], dict):
            # Get the raw values dictionary from kwargs and cast it to a known type
            raw_dict = cast(dict[str, object], kwargs["raw_values"])

            # Use a sentinel value to distinguish between missing keys and None values
            sentinel = object()

            try:
                # Extract and validate percent value
                percent_val = raw_dict.get("percent", sentinel)

                if percent_val is not sentinel:
                    # Runtime type checking for percent
                    if isinstance(percent_val, (int, float)):
                        # After runtime type checking, we know this is safe to assign
                        raw_values["percent"] = percent_val
            except (KeyError, TypeError, AttributeError):
                # Handle any unexpected errors when accessing the dictionary
                logger.debug("Error extracting percent value from raw_values")

            try:
                # Extract and validate remaining_bytes value
                bytes_val = raw_dict.get("remaining_bytes", sentinel)

                if bytes_val is not sentinel:
                    # Runtime type checking for remaining_bytes
                    if isinstance(bytes_val, int):
                        raw_values["remaining_bytes"] = bytes_val
            except (KeyError, TypeError, AttributeError):
                # Handle any unexpected errors when accessing the dictionary
                logger.debug("Error extracting remaining_bytes value from raw_values")

            try:
                # Extract and validate eta value
                eta_val = raw_dict.get("eta", sentinel)

                if eta_val is not sentinel:
                    # Runtime type checking for eta
                    if eta_val is None or isinstance(eta_val, float):
                        # After runtime type checking, we know this is safe to assign
                        raw_values["eta"] = eta_val
            except (KeyError, TypeError, AttributeError):
                # Handle any unexpected errors when accessing the dictionary
                logger.debug("Error extracting eta value from raw_values")

            # Use the message template if the message is empty
            template = message if message else self.message_template
            formatted_message = format_discord_message(template, raw_values)

        # Prepare the payload
        payload: dict[str, object] = {
            "username": self.username,
            "content": None,
        }

        # Add embeds if enabled
        if self.use_embeds:
            # Get the current date and time
            datetime_str = datetime.now().strftime("%B %d (%Y) - %H:%M:%S")

            # Determine the color based on progress
            color = self.embed_colors["low_progress"]
            if "percent" in raw_values:
                percent = int(raw_values["percent"])
                color = self._get_color_for_progress(percent)

            # Create the embed
            embed = create_embed(
                title=self.embed_title,
                color=color,
                fields=[{
                    "name": datetime_str,
                    "value": formatted_message,
                }],
            )

            # Add version information to the footer if available
            if "version" in kwargs and isinstance(kwargs["version"], str):
                version = kwargs["version"]
                embed["footer"] = {"text": f"Version: v{version}"}

            # Add the embed to the payload
            payload["embeds"] = [embed]
        else:
            # Use the formatted message as content
            payload["content"] = formatted_message

        try:
            # Send the request to the Discord webhook
            logger.debug("Sending notification to Discord: %s", self.webhook_url)
            response = requests.post(
                url=self.webhook_url,
                json=payload,
                timeout=10,
            )
            response.raise_for_status()

            # Discord returns 204 No Content on success
            if response.status_code == 204:
                logger.info("Notification sent to Discord successfully")
                return True
            else:
                logger.error("Discord API returned unexpected status code: %d", response.status_code)
                return False

        except requests.exceptions.RequestException as e:
            logger.error("Error sending notification to Discord: %s", e)
            return False
