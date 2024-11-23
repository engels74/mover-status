# notifications/providers/discord/provider.py

"""
Discord webhook notification provider implementation.
Handles sending notifications to Discord webhooks with proper rate limiting and error handling.

Example:
    >>> from notifications.discord.provider import DiscordProvider
    >>> provider = DiscordProvider({
    ...     "webhook_url": "https://discord.com/api/webhooks/...",
    ...     "username": "Mover Bot"
    ... })
    >>> async with provider:
    ...     await provider.notify_progress(75.5, "1.2 GB", "2 hours", "15:30")
"""

import asyncio
from datetime import datetime
from typing import Dict, Optional, Union
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
from notifications.providers.discord.types import (
    RATE_LIMIT,
    DiscordColor,
    NotificationResponse,
    RateLimitInfo,
    WebhookPayload,
)
from shared.types.discord import ApiLimits

logger = get_logger(__name__)


class DiscordWebhookError(NotificationError):
    """Raised when Discord webhook request fails."""
    def __init__(self, message: str, code: Optional[int] = None, retry_after: Optional[int] = None):
        """Initialize error with optional status code and retry delay.

        Args:
            message: Error description
            code: Optional HTTP status code
            retry_after: Optional retry delay in seconds
        """
        super().__init__(message, code)
        self.retry_after = retry_after


class DiscordProvider(NotificationProvider):
    """Discord webhook notification provider implementation."""

    def __init__(self, config: Dict[str, Union[str, int, dict]]):
        """Initialize Discord provider.

        Args:
            config: Provider configuration containing webhook settings

        Raises:
            ValueError: If webhook configuration is invalid
        """
        super().__init__(
            rate_limit=RATE_LIMIT["rate_limit"],
            rate_period=RATE_LIMIT["rate_period"],
            retry_attempts=RATE_LIMIT["max_retries"],
            retry_delay=RATE_LIMIT["retry_delay"],
        )
        # Extract webhook configuration
        self.webhook_url = self._validate_webhook_url(config.get("webhook_url"))
        self.username = str(config.get("username", "Mover Bot"))[:ApiLimits.USERNAME_LENGTH]
        self.avatar_url = self._validate_avatar_url(config.get("avatar_url"))
        self.embed_color = int(config.get("embed_color", DiscordColor.INFO))
        self.thread_name = config.get("thread_name")

        # Session management
        self.session: Optional[aiohttp.ClientSession] = None
        self._last_rate_limit: Optional[RateLimitInfo] = None

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

        try:
            parsed = urlparse(url)
            if not all([parsed.scheme, parsed.netloc, parsed.path]):
                raise ValueError("Invalid webhook URL format")

            if parsed.scheme not in ["http", "https"]:
                raise ValueError("Webhook URL must use HTTP(S) protocol")

            if "discord.com" not in parsed.netloc:
                raise ValueError("Webhook URL must be from discord.com domain")

            # Validate path format
            path_parts = parsed.path.strip("/").split("/")
            if len(path_parts) != 4 or path_parts[0:2] != ["api", "webhooks"]:
                raise ValueError("Invalid webhook URL path format")

            return url

        except Exception as err:
            raise ValueError(f"Invalid webhook URL: {err}") from err

    def _validate_avatar_url(self, url: Optional[str]) -> Optional[str]:
        """Validate avatar URL if provided.

        Args:
            url: Avatar URL to validate

        Returns:
            Optional[str]: Validated avatar URL

        Raises:
            ValueError: If URL format is invalid
        """
        if not url:
            return None

        try:
            parsed = urlparse(url)
            if not all([parsed.scheme, parsed.netloc]):
                raise ValueError("Invalid avatar URL format")

            if parsed.scheme not in ["http", "https"]:
                raise ValueError("Avatar URL must use HTTP(S) protocol")

            allowed_domains = {
                "cdn.discordapp.com",
                "media.discordapp.net",
                "i.imgur.com"
            }

            if not any(domain in parsed.netloc for domain in allowed_domains):
                raise ValueError(
                    f"Avatar URL must be from: {', '.join(allowed_domains)}"
                )

            return url

        except Exception as err:
            raise ValueError(f"Invalid avatar URL: {err}") from err

    async def connect(self) -> None:
        """Initialize aiohttp session for webhook requests."""
        if not self.session or self.session.closed:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30)
            )

    async def disconnect(self) -> None:
        """Close aiohttp session."""
        if self.session and not self.session.closed:
            await self.session.close()
            self.session = None

    async def _handle_rate_limit(
        self,
        response: aiohttp.ClientResponse
    ) -> Optional[int]:
        """Handle Discord rate limit response.

        Args:
            response: API response to check for rate limiting

        Returns:
            Optional[int]: Retry delay in seconds if rate limited

        Raises:
            DiscordWebhookError: If rate limit info is invalid
        """
        if response.status == 429:  # Rate limited
            try:
                data = await response.json()
                retry_after = int(data.get("retry_after", 5))
                is_global = data.get("global", False)

                self._last_rate_limit = {
                    "limit": int(response.headers.get("X-RateLimit-Limit", 0)),
                    "remaining": int(response.headers.get("X-RateLimit-Remaining", 0)),
                    "reset_after": float(response.headers.get("X-RateLimit-Reset-After", 0)),
                    "bucket": response.headers.get("X-RateLimit-Bucket", ""),
                }

                logger.warning(
                    "Discord rate limit hit",
                    retry_after=retry_after,
                    is_global=is_global,
                    rate_limit=self._last_rate_limit,
                )

                return retry_after

            except (ValueError, KeyError) as err:
                raise DiscordWebhookError(
                    "Invalid rate limit response",
                    code=response.status
                ) from err

        return None

    async def send_webhook(
        self,
        data: WebhookPayload,
        retries: int = 3
    ) -> NotificationResponse:
        """Send webhook request to Discord.

        Args:
            data: Webhook payload data
            retries: Number of retry attempts

        Returns:
            NotificationResponse: Discord response data

        Raises:
            DiscordWebhookError: If webhook request fails
        """
        if not self.session:
            await self.connect()

        last_error = None
        for attempt in range(retries + 1):
            try:
                async with self.session.post(
                    self.webhook_url,
                    json=data,
                ) as response:
                    # Check for rate limiting
                    if retry_after := await self._handle_rate_limit(response):
                        if attempt < retries:
                            await asyncio.sleep(retry_after)
                            continue
                        raise DiscordWebhookError(
                            "Rate limit exceeded",
                            code=429,
                            retry_after=retry_after
                        )

                    # Handle other responses
                    if response.status == 204:  # Success
                        return NotificationResponse(
                            id="0",  # Discord doesn't return IDs for webhooks
                            type=1,  # Default webhook type
                            channel_id="0",
                            content=data.get("content"),
                            timestamp=datetime.utcnow().isoformat()
                        )

                    error_data = await response.text()
                    raise DiscordWebhookError(
                        f"Discord webhook failed: {error_data}",
                        code=response.status
                    )

            except asyncio.TimeoutError as err:
                last_error = DiscordWebhookError("Discord webhook request timed out")
                last_error.__cause__ = err
            except aiohttp.ClientError as err:
                last_error = DiscordWebhookError(f"Discord webhook request failed: {err}")
                last_error.__cause__ = err

            if attempt < retries:
                await asyncio.sleep(self._retry_delay * (attempt + 1))
                continue

            raise last_error or DiscordWebhookError("Maximum retries exceeded")

    async def send_notification(self, message: str) -> bool:
        """Send notification via Discord webhook.

        Args:
            message: Message to send

        Returns:
            bool: True if notification was sent successfully

        Note:
            This method is part of the NotificationProvider interface but isn't used
            directly as Discord notifications use embeds instead of plain messages.
        """
        webhook_data = create_webhook_data(
            embeds=[{
                "description": message,
                "color": self.embed_color
            }],
            username=self.username
        )
        try:
            await self.send_webhook(webhook_data)
            return True
        except DiscordWebhookError:
            raise
        except Exception as err:
            raise DiscordWebhookError(f"Failed to send notification: {err}") from err

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
        try:
            embed = create_progress_embed(
                percent=percent,
                remaining=remaining,
                elapsed=elapsed,
                etc=etc,
                description=description
            )
            webhook_data = create_webhook_data(
                embeds=[embed],
                username=self.username,
                avatar_url=self.avatar_url,
                thread_name=self.thread_name
            )
            await self.send_webhook(webhook_data)
            return True
        except DiscordWebhookError:
            raise
        except Exception as err:
            raise DiscordWebhookError(f"Failed to send progress update: {err}") from err

    async def notify_completion(self) -> bool:
        """Send completion notification.

        Returns:
            bool: True if notification was sent successfully
        """
        try:
            embed = create_completion_embed()
            webhook_data = create_webhook_data(
                embeds=[embed],
                username=self.username,
                avatar_url=self.avatar_url,
                thread_name=self.thread_name
            )
            await self.send_webhook(webhook_data)
            return True
        except DiscordWebhookError:
            raise
        except Exception as err:
            raise DiscordWebhookError(f"Failed to send completion notification: {err}") from err

    async def notify_error(self, error_message: str) -> bool:
        """Send error notification.

        Args:
            error_message: Error description

        Returns:
            bool: True if notification was sent successfully
        """
        try:
            embed = create_error_embed(error_message)
            webhook_data = create_webhook_data(
                embeds=[embed],
                username=self.username,
                avatar_url=self.avatar_url,
                thread_name=self.thread_name
            )
            await self.send_webhook(webhook_data)
            return True
        except DiscordWebhookError:
            raise
        except Exception as err:
            raise DiscordWebhookError(f"Failed to send error notification: {err}") from err
