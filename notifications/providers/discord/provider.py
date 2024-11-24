# notifications/providers/discord/provider.py

"""
Discord webhook notification provider implementation.
Handles sending notifications via Discord webhooks with proper rate limiting and error handling.

Example:
    >>> from notifications.providers.discord import DiscordProvider
    >>> provider = DiscordProvider({
    ...     "webhook_url": "https://discord.com/api/webhooks/...",
    ...     "username": "Mover Bot"
    ... })
    >>> async with provider:
    ...     await provider.notify_progress(75.5, "1.2 GB", "2 hours", "15:30")
"""

import asyncio
import re
from datetime import datetime
from typing import Any, Dict, Optional, Union
from urllib.parse import urlparse

import aiohttp
from structlog import get_logger

from notifications.base import NotificationError, NotificationProvider
from notifications.providers.discord.schemas import WebhookConfigSchema
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
    def __init__(
        self,
        message: str,
        code: Optional[int] = None,
        retry_after: Optional[int] = None
    ):
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

    @classmethod
    def _validate_webhook_url(cls, webhook_url: str) -> None:
        """Validate Discord webhook URL format.

        Args:
            webhook_url: URL to validate

        Raises:
            ValueError: If URL format is invalid
        """
        if not webhook_url.strip():
            raise ValueError("Webhook URL is required")

        parsed = urlparse(webhook_url)
        if not all([parsed.scheme, parsed.netloc, parsed.path]):
            raise ValueError("Invalid webhook URL format")
        if parsed.scheme not in ["http", "https"]:
            raise ValueError("Webhook URL must use HTTP(S) protocol")
        if "discord.com" not in parsed.netloc:
            raise ValueError("Webhook URL must be from discord.com domain")

        path_parts = parsed.path.strip("/").split("/")
        if len(path_parts) != 4 or path_parts[0:2] != ["api", "webhooks"]:
            raise ValueError("Invalid webhook URL path format")

        webhook_id, token = path_parts[2:4]
        if not webhook_id.isdigit():
            raise ValueError("Invalid webhook ID format")
        if not re.match(r"^[A-Za-z0-9_-]{60,80}$", token):
            raise ValueError("Invalid webhook token format")

    @classmethod
    def _validate_avatar_url(cls, avatar_url: Optional[str]) -> None:
        """Validate avatar URL if provided.

        Args:
            avatar_url: URL to validate

        Raises:
            ValueError: If URL format is invalid
        """
        if not avatar_url:
            return

        try:
            parsed = urlparse(avatar_url)
            if not all([parsed.scheme, parsed.netloc]):
                raise ValueError("Invalid avatar URL format")

            allowed_domains = {
                "cdn.discordapp.com",
                "media.discordapp.net",
                "i.imgur.com"
            }
            if not any(domain in parsed.netloc for domain in allowed_domains):
                raise ValueError(
                    f"Avatar URL must be from: {', '.join(allowed_domains)}"
                )
        except Exception as err:
            raise ValueError(f"Invalid avatar URL: {err}") from err

    @classmethod
    def _validate_basic_settings(cls, config: Dict[str, Any]) -> None:
        """Validate basic configuration settings.

        Args:
            config: Configuration to validate

        Raises:
            ValueError: If settings are invalid
        """
        username = str(config.get("username", "Mover Bot"))
        if not username or len(username) > ApiLimits.USERNAME_LENGTH:
            raise ValueError(f"Username must be 1-{ApiLimits.USERNAME_LENGTH} characters")

        if "embed_color" in config:
            embed_color = int(config["embed_color"])
            if not 0 <= embed_color <= 0xFFFFFF:
                raise ValueError("Embed color must be a valid hex color (0-0xFFFFFF)")

    @classmethod
    def validate_config(cls, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate Discord provider configuration.

        Args:
            config: Configuration dictionary to validate

        Returns:
            Dict[str, Any]: Validated configuration

        Raises:
            ValueError: If configuration is invalid
        """
        try:
            # Validate components
            cls._validate_webhook_url(str(config.get("webhook_url", "")))
            cls._validate_avatar_url(config.get("avatar_url"))
            cls._validate_basic_settings(config)

            # Prepare validated configuration
            validated = {
                "webhook_url": str(config["webhook_url"]),
                "username": str(config.get("username", "Mover Bot")),
                "embed_color": config.get("embed_color", DiscordColor.INFO),
                "avatar_url": config.get("avatar_url"),
                "thread_name": config.get("thread_name"),
                "rate_limit": config.get("rate_limit", RATE_LIMIT["rate_limit"]),
                "rate_period": config.get("rate_period", RATE_LIMIT["rate_period"]),
                "retry_attempts": config.get("retry_attempts", RATE_LIMIT["max_retries"]),
                "retry_delay": config.get("retry_delay", RATE_LIMIT["retry_delay"]),
            }

            # Validate using schema
            WebhookConfigSchema(**validated)
            return validated

        except ValueError:
            raise
        except Exception as err:
            raise ValueError(f"Configuration validation failed: {err}") from err

    def __init__(self, config: Dict[str, Any]):
        """Initialize Discord provider.

        Args:
            config: Provider configuration containing webhook settings

        Raises:
            ValueError: If webhook configuration is invalid
        """
        # Initialize with validated config
        validated_config = self.validate_config(config)
        super().__init__(
            rate_limit=validated_config["rate_limit"],
            rate_period=validated_config["rate_period"],
            retry_attempts=validated_config["retry_attempts"],
            retry_delay=validated_config["retry_delay"],
        )

        self.webhook_url = validated_config["webhook_url"]
        self.username = validated_config["username"]
        self.avatar_url = validated_config["avatar_url"]
        self.embed_color = validated_config["embed_color"]
        self.thread_name = validated_config["thread_name"]

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
        if response.status != 429:  # Not rate limited
            return None

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

    async def send_webhook(
        self,
        data: WebhookPayload,
        retries: Optional[int] = None
    ) -> NotificationResponse:
        """Send webhook request to Discord.

        Args:
            data: Webhook payload data
            retries: Optional override for retry attempts

        Returns:
            NotificationResponse: Discord response data

        Raises:
            DiscordWebhookError: If webhook request fails
        """
        if not self.session:
            await self.connect()

        max_retries = retries if retries is not None else self._retry_attempts
        last_error = None

        for attempt in range(max_retries + 1):
            try:
                async with self.session.post(
                    self.webhook_url,
                    json=data,
                    headers={"Content-Type": "application/json"}
                ) as response:
                    # Check for rate limiting
                    if retry_after := await self._handle_rate_limit(response):
                        if attempt < max_retries:
                            await asyncio.sleep(retry_after)
                            continue
                        raise DiscordWebhookError(
                            "Rate limit exceeded",
                            code=429,
                            retry_after=retry_after
                        )

                    # Handle successful response
                    if response.status == 204:  # Success without content
                        return NotificationResponse(
                            id="0",  # Discord doesn't return IDs for webhooks
                            type=1,  # Default webhook type
                            channel_id="0",
                            content=data.get("content", ""),
                            timestamp=datetime.utcnow().isoformat()
                        )

                    # Handle error responses
                    error_text = await response.text()
                    raise DiscordWebhookError(
                        f"Discord webhook failed ({response.status}): {error_text}",
                        code=response.status
                    )

            except asyncio.TimeoutError as err:
                last_error = DiscordWebhookError(
                    "Discord webhook request timed out",
                    code=None
                )
                last_error.__cause__ = err

            except aiohttp.ClientError as err:
                last_error = DiscordWebhookError(
                    f"Discord webhook request failed: {err}",
                    code=None
                )
                last_error.__cause__ = err

            if attempt < max_retries:
                await asyncio.sleep(self._retry_delay * (attempt + 1))
                continue

            raise last_error or DiscordWebhookError("Maximum retries exceeded")

    async def send_notification(self, message: str) -> bool:
        """Send notification via Discord webhook.

        Args:
            message: Message to send

        Returns:
            bool: True if notification was sent successfully
        """
        webhook_data = create_webhook_data(
            embeds=[{
                "description": message,
                "color": self.embed_color,
                "timestamp": datetime.utcnow().isoformat()
            }],
            username=self.username,
            avatar_url=self.avatar_url,
            thread_name=self.thread_name
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

        except Exception as err:
            raise DiscordWebhookError(f"Failed to send progress update: {err}") from err

    async def notify_completion(
        self,
        stats: Optional[Dict[str, Union[str, int, float]]] = None
    ) -> bool:
        """Send completion notification.

        Args:
            stats: Optional transfer statistics to include

        Returns:
            bool: True if notification was sent successfully
        """
        try:
            embed = create_completion_embed(stats=stats)
            webhook_data = create_webhook_data(
                embeds=[embed],
                username=self.username,
                avatar_url=self.avatar_url,
                thread_name=self.thread_name
            )

            await self.send_webhook(webhook_data)
            return True

        except Exception as err:
            raise DiscordWebhookError(f"Failed to send completion notification: {err}") from err

    async def notify_error(
        self,
        error_message: str,
        error_code: Optional[int] = None,
        error_details: Optional[Dict[str, str]] = None
    ) -> bool:
        """Send error notification.

        Args:
            error_message: Error description
            error_code: Optional error code
            error_details: Optional error details

        Returns:
            bool: True if notification was sent successfully
        """
        try:
            embed = create_error_embed(
                error_message=error_message,
                error_code=error_code,
                error_details=error_details
            )

            webhook_data = create_webhook_data(
                embeds=[embed],
                username=self.username,
                avatar_url=self.avatar_url,
                thread_name=self.thread_name
            )

            await self.send_webhook(webhook_data)
            return True

        except Exception as err:
            raise DiscordWebhookError(
                f"Failed to send error notification: {err}"
            ) from err
