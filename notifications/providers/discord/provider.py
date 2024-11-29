# notifications/providers/discord/provider.py

"""
Discord webhook notification provider implementation.
Handles sending notifications via Discord webhooks with proper rate limiting and error handling.

Example:
    >>> from notifications.providers.discord import DiscordProvider, DiscordConfig
    >>> config = DiscordConfig(
    ...     webhook_url="https://discord.com/api/webhooks/...",
    ...     username="Mover Bot"
    ... )
    >>> provider = DiscordProvider(config.to_provider_config())
    >>> async with provider:
    ...     await provider.notify_progress(75.5, "1.2 GB", "2 hours", "15:30")
"""

import asyncio
from datetime import datetime
from typing import Any, Dict, Final, Optional, Union

import aiohttp
from pydantic import HttpUrl
from structlog import get_logger

from config.constants import MessagePriority, MessageType, NotificationLevel
from notifications.base import NotificationError, NotificationProvider
from notifications.providers.discord.templates import (
    create_batch_embed,
    create_completion_embed,
    create_debug_embed,
    create_error_embed,
    create_interactive_embed,
    create_progress_embed,
    create_system_embed,
    create_warning_embed,
    create_webhook_data,
)
from notifications.providers.discord.types import (
    NotificationResponse,
    RateLimitInfo,
    WebhookPayload,
)
from notifications.providers.discord.validators import DiscordValidator
from shared.providers.discord import WEBHOOK_DOMAINS, DiscordColor, Embed, validate_url

logger = get_logger(__name__)

# Default timeout settings
DEFAULT_TIMEOUT: Final[int] = 30
MAX_TIMEOUT: Final[int] = 300  # 5 minutes

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
        self.is_transient = code in {408, 429, 500, 502, 503, 504} if code else False

class DiscordProvider(NotificationProvider):
    """Discord webhook notification provider implementation."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize Discord provider.

        Args:
            config: Provider configuration containing webhook settings

        Raises:
            ValueError: If webhook configuration is invalid
            DiscordWebhookError: If webhook URL is invalid
        """
        # Validate configuration using dedicated validator
        validator = DiscordValidator()
        self._config = validator.validate_config(config)

        super().__init__(
            rate_limit=self._config["rate_limit"],
            rate_period=self._config["rate_period"],
            retry_attempts=self._config["retry_attempts"],
            retry_delay=self._config["retry_delay"],
        )

        # Validate and extract webhook URL
        webhook_url = self._config["webhook_url"]
        if not webhook_url or not validate_url(webhook_url, WEBHOOK_DOMAINS):
            raise DiscordWebhookError(
                f"Invalid webhook URL: {webhook_url}. Must be a valid Discord webhook URL."
            )

        # Extract validated configuration
        self.webhook_url: str = webhook_url
        self.username: str = self._config["username"]
        self.avatar_url: Optional[HttpUrl] = self._config.get("avatar_url")
        self.embed_color: int = self._config.get("embed_color", DiscordColor.INFO)
        self.thread_name: Optional[str] = self._config.get("thread_name")

        # Request timeout configuration
        timeout = self._config.get("timeout", DEFAULT_TIMEOUT)
        if not isinstance(timeout, (int, float)) or timeout <= 0 or timeout > MAX_TIMEOUT:
            logger.warning(
                "Invalid timeout value, using default",
                timeout=timeout,
                default=DEFAULT_TIMEOUT
            )
            timeout = DEFAULT_TIMEOUT
        self.timeout: float = float(timeout)

        # Session and rate limit management
        self.session: Optional[aiohttp.ClientSession] = None
        self._last_rate_limit: Optional[RateLimitInfo] = None
        self._current_backoff: float = self._retry_delay

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
                timeout=aiohttp.ClientTimeout(total=self.timeout)
            )

    async def disconnect(self) -> None:
        """Close aiohttp session."""
        if self.session and not self.session.closed:
            try:
                await self.session.close()
            finally:
                self.session = None
                self._last_rate_limit = None
                self._current_backoff = self._retry_delay

    async def _update_rate_limit_info(
        self,
        response: aiohttp.ClientResponse
    ) -> Optional[RateLimitInfo]:
        """Update rate limit information from response headers.

        Args:
            response: API response to extract rate limit info from

        Returns:
            Optional[RateLimitInfo]: Updated rate limit information
        """
        try:
            self._last_rate_limit = {
                "limit": int(response.headers.get("X-RateLimit-Limit", 0)),
                "remaining": int(response.headers.get("X-RateLimit-Remaining", 0)),
                "reset_after": float(response.headers.get("X-RateLimit-Reset-After", 0)),
                "bucket": response.headers.get("X-RateLimit-Bucket", ""),
            }
            return self._last_rate_limit
        except (ValueError, KeyError, TypeError):
            return None

    async def _handle_rate_limit(
        self,
        response: aiohttp.ClientResponse,
        data: Dict[str, Any]
    ) -> Optional[int]:
        """Handle Discord rate limit response.

        Args:
            response: API response
            data: Response data dictionary

        Returns:
            Optional[int]: Retry delay in seconds if rate limited

        Raises:
            DiscordWebhookError: If rate limit info is invalid
        """
        if response.status != 429:
            return None

        try:
            retry_after = float(data.get("retry_after", 5))
            is_global = data.get("global", False)

            # Update rate limit info
            rate_info = await self._update_rate_limit_info(response)

            logger.warning(
                "Discord rate limit hit",
                retry_after=retry_after,
                is_global=is_global,
                rate_info=rate_info,
            )

            return int(retry_after + 0.5)  # Round up to nearest second

        except (ValueError, KeyError) as err:
            raise DiscordWebhookError(
                "Invalid rate limit response",
                code=response.status
            ) from err

    def _calculate_backoff(self, attempt: int) -> float:
        """Calculate exponential backoff delay.

        Args:
            attempt: Current attempt number

        Returns:
            float: Delay in seconds
        """
        # Exponential backoff with jitter
        import random
        max_backoff = min(self._retry_delay * (2 ** attempt), 30)  # Cap at 30 seconds
        return random.uniform(0, max_backoff)

    async def send_notification(
        self,
        message: str,
        level: NotificationLevel = NotificationLevel.INFO,
        priority: MessagePriority = MessagePriority.NORMAL,
        message_type: MessageType = MessageType.CUSTOM,
        **kwargs
    ) -> bool:
        """Send notification via Discord webhook.

        Args:
            message: Message to send
            level: Notification priority level
            priority: Message priority level
            message_type: Type of message
            **kwargs: Additional message-specific arguments

        Returns:
            bool: True if notification was sent successfully

        Raises:
            DiscordWebhookError: If webhook request fails
        """
        try:
            # Create appropriate embed based on message type
            embed = self._create_typed_embed(message, message_type, level, **kwargs)

            # Create webhook payload
            payload = create_webhook_data(
                embeds=[embed],
                username=self.username,
                avatar_url=self.avatar_url,
                forum_config=kwargs.get("forum_config")
            )

            # Send webhook request
            async with self._get_session() as session:
                async with session.post(
                    self.webhook_url,
                    json=payload,
                    timeout=self.timeout
                ) as response:
                    if response.status == 429:  # Rate limited
                        retry_after = float(response.headers.get("Retry-After", self._retry_delay))
                        logger.warning(
                            "Rate limited by Discord",
                            retry_after=retry_after,
                            message_type=message_type.value
                        )
                        await asyncio.sleep(retry_after)
                        return False

                    if not response.ok:
                        error_data = await response.json()
                        raise DiscordWebhookError(
                            f"Webhook request failed: {error_data.get('message', 'Unknown error')}",
                            response_code=response.status,
                            error_data=error_data
                        )

                    return True

        except Exception as err:
            raise DiscordWebhookError(
                f"Failed to send notification: {err}",
                context={"message_type": message_type.value}
            ) from err

    def _create_typed_embed(
        self,
        message: str,
        message_type: MessageType,
        level: NotificationLevel,
        **kwargs
    ) -> Embed:
        """Create appropriate embed based on message type.

        Args:
            message: Message content
            message_type: Type of message
            level: Notification level
            **kwargs: Additional message-specific arguments

        Returns:
            Embed: Formatted Discord embed
        """
        if message_type == MessageType.PROGRESS:
            return create_progress_embed(
                percent=kwargs.get("percent", 0),
                remaining=kwargs.get("remaining", "Unknown"),
                elapsed=kwargs.get("elapsed", "Unknown"),
                etc=kwargs.get("etc", "Unknown"),
                description=message
            )

        elif message_type == MessageType.COMPLETION:
            return create_completion_embed(
                description=message,
                stats=kwargs.get("stats")
            )

        elif message_type == MessageType.ERROR:
            return create_error_embed(
                error_message=message,
                error_code=kwargs.get("error_code"),
                error_details=kwargs.get("error_details")
            )

        elif message_type == MessageType.WARNING:
            return create_warning_embed(
                warning_message=message,
                warning_details=kwargs.get("warning_details"),
                suggestion=kwargs.get("suggestion")
            )

        elif message_type == MessageType.SYSTEM:
            return create_system_embed(
                status=message,
                metrics=kwargs.get("metrics"),
                issues=kwargs.get("issues")
            )

        elif message_type == MessageType.BATCH:
            return create_batch_embed(
                operation=kwargs.get("operation", "Operation"),
                items=kwargs.get("items", []),
                summary=message
            )

        elif message_type == MessageType.INTERACTIVE:
            return create_interactive_embed(
                title=kwargs.get("title", "Interactive Message"),
                description=message,
                actions=kwargs.get("actions", []),
                expires_in=kwargs.get("expires_in")
            )

        elif message_type == MessageType.DEBUG:
            return create_debug_embed(
                message=message,
                context=kwargs.get("context"),
                stack_trace=kwargs.get("stack_trace")
            )

        # Default to custom message type
        return Embed(
            title=kwargs.get("title", "Notification"),
            description=message,
            color=self._get_level_color(level),
            timestamp=datetime.utcnow().isoformat()
        )

    def _get_level_color(self, level: NotificationLevel) -> int:
        """Get Discord color based on notification level.

        Args:
            level: Notification level

        Returns:
            int: Discord color code
        """
        return {
            NotificationLevel.DEBUG: DiscordColor.GREYPLE,
            NotificationLevel.INFO: DiscordColor.INFO,
            NotificationLevel.WARNING: DiscordColor.WARNING,
            NotificationLevel.ERROR: DiscordColor.ERROR,
            NotificationLevel.CRITICAL: DiscordColor.DARK_RED
        }.get(level, DiscordColor.DEFAULT)

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
                    # Update rate limit info for all responses
                    await self._update_rate_limit_info(response)

                    # Handle rate limiting
                    if retry_after := await self._handle_rate_limit(response, await response.json()):
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
                    "Request timed out",
                    code=408
                )
                last_error.__cause__ = err
            except aiohttp.ClientError as err:
                last_error = DiscordWebhookError(f"Request failed: {err}")
                last_error.__cause__ = err

            if attempt < max_retries:
                backoff = self._calculate_backoff(attempt)
                await asyncio.sleep(backoff)
                continue

        raise last_error or DiscordWebhookError("Maximum retries exceeded")

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

        Raises:
            DiscordWebhookError: If notification fails
        """
        try:
            embed = create_progress_embed(
                percent=percent,
                remaining=remaining,
                elapsed=elapsed,
                etc=etc,
                description=description,
                color=self.embed_color
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

        Raises:
            DiscordWebhookError: If notification fails
        """
        try:
            embed = create_completion_embed(
                stats=stats,
                color=DiscordColor.SUCCESS
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

        Raises:
            DiscordWebhookError: If notification fails
        """
        try:
            embed = create_error_embed(
                error_message=error_message,
                error_code=error_code,
                error_details=error_details,
                color=DiscordColor.ERROR
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
            raise DiscordWebhookError(f"Failed to send error notification: {err}") from err
