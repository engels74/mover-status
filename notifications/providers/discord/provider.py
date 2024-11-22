# notifications/providers/discord/provider.py

"""
Discord webhook notification provider implementation.
Handles sending notifications to Discord webhooks with proper rate limiting and error handling.

Example:
    >>> from notifications.discord.provider import DiscordProvider
    >>> provider = DiscordProvider({"webhook_url": "https://discord.com/api/webhooks/..."})
    >>> await provider.notify_progress(75.5, "1.2 GB", "2 hours", "15:30")
"""

import asyncio
from typing import Dict, Optional
from urllib.parse import urlparse

import aiohttp
from structlog import get_logger

from notifications.base import NotificationError, NotificationProvider
from notifications.providers.discord.templates import (
    create_completion_embed,
    create_error_embed,
    create_progress_embed,
    create_webhook_data,
)
from notifications.providers.discord.types import RATE_LIMIT

logger = get_logger(__name__)

class DiscordWebhookError(NotificationError):
    """Raised when Discord webhook request fails."""

class DiscordProvider(NotificationProvider):
    """Discord webhook notification provider implementation."""

    def __init__(self, config: Dict[str, str]):
        """Initialize Discord provider.

        Args:
            config: Provider configuration containing webhook_url

        Raises:
            ValueError: If webhook URL is invalid or missing
        """
        super().__init__(
            rate_limit=RATE_LIMIT["rate_limit"],
            rate_period=RATE_LIMIT["rate_period"],
            retry_attempts=RATE_LIMIT["max_retries"],
            retry_delay=RATE_LIMIT["retry_delay"],
        )
        self.webhook_url = self._validate_webhook_url(config.get("webhook_url"))
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self) -> "DiscordProvider":
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.disconnect()

    def _validate_webhook_url(self, url: Optional[str]) -> str:
        """Validate Discord webhook URL.

        Args:
            url: Webhook URL to validate

        Returns:
            str: Validated webhook URL

        Raises:
            ValueError: If URL is invalid or missing
        """
        if not url:
            raise ValueError("Discord webhook URL is required")

        parsed = urlparse(url)
        if not all([parsed.scheme, parsed.netloc]):
            raise ValueError("Invalid webhook URL format")

        if "discord.com" not in parsed.netloc:
            raise ValueError("Webhook URL must be from discord.com domain")

        return url

    async def connect(self) -> None:
        """Initialize aiohttp session for webhook requests."""
        if not self.session or self.session.closed:
            self.session = aiohttp.ClientSession()

    async def disconnect(self) -> None:
        """Close aiohttp session."""
        if self.session and not self.session.closed:
            await self.session.close()
            self.session = None

    async def send_webhook(self, data: Dict) -> bool:
        """Send webhook request to Discord.

        Args:
            data: Webhook payload data

        Returns:
            bool: True if request was successful

        Raises:
            DiscordWebhookError: If webhook request fails
        """
        if not self.session:
            await self.connect()

        try:
            async with self.session.post(
                self.webhook_url,
                json=data,
                timeout=30
            ) as response:
                if response.status == 204:  # Discord returns 204 No Content on success
                    logger.debug("Discord webhook sent successfully")
                    return True

                error_data = await response.text()
                raise DiscordWebhookError(
                    f"Discord webhook failed with status {response.status}: {error_data}"
                )

        except asyncio.TimeoutError as err:
            raise DiscordWebhookError("Discord webhook request timed out") from err
        except aiohttp.ClientError as err:
            raise DiscordWebhookError(f"Discord webhook request failed: {err}") from err

    async def send_notification(self, message: str) -> bool:
        """Send notification via Discord webhook.

        Args:
            message: Message to send (not used, kept for interface compatibility)

        Returns:
            bool: True if notification was sent successfully

        Note:
            This method is part of the NotificationProvider interface but isn't used
            directly as Discord notifications use embeds instead of plain messages.
        """
        webhook_data = create_webhook_data(
            embeds=[{
                "description": message,
                "color": 0x0099FF  # Light blue
            }]
        )
        return await self.send_webhook(webhook_data)

    async def notify_progress(
        self,
        percent: float,
        remaining: str,
        elapsed: str,
        etc: str,
        description: Optional[str] = None
    ) -> bool:
        """Send progress update notification.

        Args:
            percent: Progress percentage
            remaining: Remaining data amount
            elapsed: Elapsed time
            etc: Estimated time of completion
            description: Optional description

        Returns:
            bool: True if notification was sent successfully
        """
        embed = create_progress_embed(
            percent=percent,
            remaining=remaining,
            elapsed=elapsed,
            etc=etc,
            description=description
        )
        webhook_data = create_webhook_data(embeds=[embed])
        return await self.send_webhook(webhook_data)

    async def notify_completion(self) -> bool:
        """Send completion notification.

        Returns:
            bool: True if notification was sent successfully
        """
        embed = create_completion_embed()
        webhook_data = create_webhook_data(embeds=[embed])
        return await self.send_webhook(webhook_data)

    async def notify_error(self, error_message: str) -> bool:
        """Send error notification.

        Args:
            error_message: Error description

        Returns:
            bool: True if notification was sent successfully
        """
        embed = create_error_embed(error_message)
        webhook_data = create_webhook_data(embeds=[embed])
        return await self.send_webhook(webhook_data)
