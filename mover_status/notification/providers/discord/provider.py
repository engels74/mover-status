"""
Discord notification provider implementation.

This module provides the implementation of the Discord notification provider,
which sends notifications to Discord using webhooks.
"""

import logging
import re
from datetime import datetime
from typing import TypedDict, cast, override, Any
from collections.abc import Mapping

from mover_status.notification.formatter import RawValues
from mover_status.notification.providers.webhook_provider import WebhookProvider
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


class DiscordProvider(WebhookProvider):
    """
    Discord notification provider.

    This class implements the WebhookProvider interface for sending
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

    # Class-level attribute declarations
    embed_colors: EmbedColorsType

    def __init__(
        self,
        name: str,
        config: Mapping[str, Any],  # pyright: ignore[reportExplicitAny]
        metadata: Mapping[str, object] | None = None
    ) -> None:
        """
        Initialize the Discord notification provider.

        Args:
            name: The name of the notification provider.
            config: The provider configuration.
            metadata: Optional metadata about the provider.
        """
        # Initialize the parent class
        super().__init__(name, config, metadata)

        # Extract Discord-specific configuration values
        self.username: str = str(self._get_config_value("username", "Mover Bot"))
        self.message_template: str = str(self._get_config_value("message_template", ""))
        self.use_embeds: bool = bool(self._get_config_value("use_embeds", True))
        self.embed_title: str = str(self._get_config_value("embed_title", "Mover: Moving Data"))

        # Handle embed colors with proper type conversion
        default_colors: EmbedColorsType = {
            "low_progress": 16744576,  # Light Red (0-34%)
            "mid_progress": 16753920,  # Light Orange (35-65%)
            "high_progress": 9498256,  # Light Green (66-99%)
            "complete": 65280,         # Green (100%)
        }
        embed_colors_raw = self._get_config_value("embed_colors", default_colors)
        if isinstance(embed_colors_raw, dict):
            # Convert to proper type after runtime validation
            self.embed_colors = cast(EmbedColorsType, embed_colors_raw)
        else:
            self.embed_colors = default_colors

    @override
    def validate_config(self) -> list[str]:
        """
        Validate the provider configuration.

        Returns:
            A list of error messages. An empty list indicates a valid configuration.
        """
        errors: list[str] = []

        # Check required fields using the webhook_url from the parent class
        if not self.webhook_url:
            errors.append("Discord webhook_url is required")
        elif not re.match(DISCORD_WEBHOOK_URL_PATTERN, self.webhook_url):
            errors.append(f"Invalid webhook_url: {self.webhook_url}")

        return errors

    @override
    def _prepare_payload(
        self,
        message: str,
        raw_values: RawValues,
        **kwargs: object
    ) -> dict[str, object]:
        """
        Prepare the payload for the Discord webhook request.

        Args:
            message: The message to send.
            raw_values: Extracted and validated raw values.
            **kwargs: Additional provider-specific arguments.

        Returns:
            A dictionary representing the payload to send to Discord.
        """
        # Format the message if raw_values are provided and we have a template
        formatted_message = message
        if raw_values and self.message_template:
            formatted_message = format_discord_message(self.message_template, raw_values)
        elif self.message_template and not raw_values:
            # Use the template as-is if no raw values provided
            formatted_message = self.message_template

        # Prepare the base payload
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

        return payload

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
