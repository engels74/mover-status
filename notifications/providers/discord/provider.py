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

class DiscordWebhookError(Exception):
    """Discord webhook error with context and state tracking."""
    def __init__(
        self,
        message: str,
        code: Optional[int] = None,
        retry_after: Optional[int] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        """Initialize error with optional status code, retry delay, and context.

        Args:
            message: Error description
            code: Optional HTTP status code
            retry_after: Optional retry delay in seconds
            context: Optional error context dictionary
        """
        super().__init__(message)
        self.code = code
        self.retry_after = retry_after
        self.context = context or {}
        self.is_transient = code in {408, 429, 500, 502, 503, 504} if code else False
        self.timestamp = datetime.now()

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
                f"Invalid webhook URL: {webhook_url}. Must be a valid Discord webhook URL.",
                context={"endpoint": webhook_url}
            )

        # Extract validated configuration
        self._webhook_url: str = webhook_url
        self._username: Optional[str] = self._config["username"]
        self._avatar_url: Optional[HttpUrl] = self._config.get("avatar_url")
        self._thread_name: Optional[str] = self._config.get("thread_name")
        self._embed_color: DiscordColor = self._config.get("embed_color", DiscordColor.INFO)
        self._last_message_id: Optional[str] = None
        self._last_rate_limit: Optional[datetime] = None
        self._current_backoff: float = self._retry_delay
        self._state = NotificationState()
        self._consecutive_errors = 0
        
        # Thread safety locks
        self._session_lock = asyncio.Lock()
        self._state_lock = asyncio.Lock()
        self._message_lock = asyncio.Lock()
        self._rate_limit_lock = asyncio.Lock()

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

    async def __aenter__(self) -> "DiscordProvider":
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.disconnect()

    async def connect(self) -> None:
        """Initialize aiohttp session for webhook requests."""
        async with self._session_lock:
            if not self.session or self.session.closed:
                self.session = aiohttp.ClientSession(
                    timeout=aiohttp.ClientTimeout(total=self.timeout)
                )

    async def disconnect(self) -> None:
        """Close aiohttp session."""
        async with self._session_lock:
            if self.session and not self.session.closed:
                try:
                    await self.session.close()
                finally:
                    self.session = None
                    self._last_rate_limit = None
                    self._current_backoff = self._retry_delay

    async def _update_rate_limit_state(self, response: aiohttp.ClientResponse) -> None:
        """Update rate limit state from response headers.

        Args:
            response: API response with rate limit headers
        """
        async with self._rate_limit_lock:
            # Check rate limit headers
            remaining = response.headers.get("X-RateLimit-Remaining")
            reset_after = response.headers.get("X-RateLimit-Reset-After")
            
            if remaining and reset_after:
                try:
                    if int(remaining) == 0:
                        self._last_rate_limit = datetime.now()
                        self._current_backoff = float(reset_after)
                except ValueError:
                    pass

    async def send_notification(
        self,
        message: str,
        level: NotificationLevel = NotificationLevel.INFO,
        priority: MessagePriority = MessagePriority.NORMAL,
        message_type: MessageType = MessageType.CUSTOM,
        **kwargs: Any
    ) -> bool:
        """Send notification via Discord webhook.

        Args:
            message: Message content
            level: Notification level
            priority: Message priority
            message_type: Type of message
            **kwargs: Additional message parameters

        Returns:
            bool: True if message was sent successfully

        Raises:
            DiscordError: If sending fails
        """
        async with self._message_lock:
            try:
                # Create webhook payload
                payload = await self._create_webhook_payload(
                    message, level, message_type, **kwargs
                )

                # Send webhook request
                async with self._session_lock:
                    if not self.session or self.session.closed:
                        await self.connect()

                    response = await self._send_webhook_request(payload)
                    
                    # Update rate limit state
                    await self._update_rate_limit_state(response)
                    
                    return True

            except Exception as err:
                error = self._handle_request_error(err, "send_notification")
                async with self._state_lock:
                    self._state.last_error = error
                    self._state.last_error_time = datetime.now()
                raise error

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

    async def send_webhook(
        self,
        data: WebhookPayload,
        retries: Optional[int] = None,
        require_embeds: bool = True
    ) -> NotificationResponse:
        """Send webhook request to Discord.

        Args:
            data: Webhook payload data
            retries: Optional override for retry attempts
            require_embeds: If True, at least one embed is required

        Returns:
            NotificationResponse: Discord response data

        Raises:
            DiscordWebhookError: If webhook request fails or required embeds are missing
        """
        if not self.session:
            await self.connect()

        if self._state.disabled:
            raise DiscordWebhookError(
                "Provider is disabled due to excessive errors",
                context={"last_error": str(self._state.last_error)}
            )

        # Validate webhook data
        if require_embeds and (not data.get("embeds") or len(data["embeds"]) == 0):
            raise DiscordWebhookError(
                "At least one embed is required for this webhook message",
                context={"endpoint": self._webhook_url}
            )

        max_retries = retries if retries is not None else self._retry_attempts
        last_error = None

        for attempt in range(max_retries + 1):
            try:
                async with self.session.post(
                    self._webhook_url,
                    json=data,
                    headers={"Content-Type": "application/json"}
                ) as response:
                    # Handle rate limiting
                    if retry_after := await self._handle_rate_limit(response, await response.json()):
                        if attempt < max_retries:
                            base_delay = retry_after * (1.5 ** attempt)  # Exponential backoff
                            await asyncio.sleep(base_delay)
                            self._state.total_retries += 1
                            continue
                        raise DiscordWebhookError(
                            "Rate limit exceeded",
                            code=429,
                            retry_after=retry_after,
                            context={
                                "endpoint": self._webhook_url,
                                "attempt": attempt,
                                "max_retries": max_retries
                            }
                        )

                    # Handle successful response
                    if response.status == 204:  # Success without content
                        async with self._state_lock:
                            self._consecutive_errors = 0
                            self._state.last_success = datetime.now()
                            self._state.rate_limited = False
                        return NotificationResponse(
                            id="0",  # Discord doesn't return IDs for webhooks
                            type=1,  # Default webhook type
                            channel_id="0",
                            content=data.get("content", ""),
                            timestamp=datetime.utcnow().isoformat()
                        )

                    # Handle error responses
                    error_text = await response.text()
                    error = DiscordWebhookError(
                        f"Discord webhook failed ({response.status}): {error_text}",
                        code=response.status,
                        context={
                            "endpoint": self._webhook_url,
                            "attempt": attempt,
                            "response": error_text
                        }
                    )
                    await self._update_error_state(error)
                    raise error

            except asyncio.TimeoutError as err:
                last_error = DiscordWebhookError(
                    "Request timed out",
                    code=408,
                    context={
                        "endpoint": self._webhook_url,
                        "attempt": attempt,
                        "timeout": self.timeout
                    }
                )
                last_error.__cause__ = err
            except aiohttp.ClientError as err:
                last_error = DiscordWebhookError(
                    f"Request failed: {err}",
                    context={
                        "endpoint": self._webhook_url,
                        "attempt": attempt
                    }
                )
                last_error.__cause__ = err

            if attempt < max_retries:
                backoff = self._calculate_backoff(attempt)
                await asyncio.sleep(backoff)
                self._state.total_retries += 1
                continue

            # Update error state and raise
            await self._update_error_state(last_error or DiscordWebhookError(
                "Maximum retries exceeded",
                context={
                    "endpoint": self._webhook_url,
                    "attempts": attempt + 1,
                    "max_retries": max_retries
                }
            ))
            raise self._state.last_error

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
                color=self._embed_color
            )

            webhook_data = create_webhook_data(
                embeds=[embed],
                username=self._username,
                avatar_url=self._avatar_url,
                thread_name=self._thread_name
            )

            await self.send_webhook(webhook_data)
            return True

        except Exception as err:
            error = self._handle_request_error(err, "notify_progress")
            async with self._state_lock:
                self._state.last_error = error
                self._state.last_error_time = datetime.now()
            raise error

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
                username=self._username,
                avatar_url=self._avatar_url,
                thread_name=self._thread_name
            )

            await self.send_webhook(webhook_data)
            return True

        except Exception as err:
            error = self._handle_request_error(err, "notify_completion")
            async with self._state_lock:
                self._state.last_error = error
                self._state.last_error_time = datetime.now()
            raise error

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
                username=self._username,
                avatar_url=self._avatar_url,
                thread_name=self._thread_name
            )

            await self.send_webhook(webhook_data)
            return True

        except Exception as err:
            error = self._handle_request_error(err, "notify_error")
            async with self._state_lock:
                self._state.last_error = error
                self._state.last_error_time = datetime.now()
            raise error

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
            NotificationLevel.CRITICAL: DiscordColor.DARK_RED,
            NotificationLevel.INFO_SUCCESS: DiscordColor.SUCCESS,
            NotificationLevel.INFO_FAILURE: DiscordColor.ERROR
        }.get(level, DiscordColor.DEFAULT)

    def _handle_request_error(
        self,
        err: Exception,
        method: str
    ) -> DiscordWebhookError:
        """Handle request errors and create appropriate DiscordWebhookError.

        Args:
            err: Original exception
            method: API method name

        Returns:
            DiscordWebhookError: Wrapped error with context
        """
        if isinstance(err, asyncio.TimeoutError):
            error = DiscordWebhookError(
                "Request timed out",
                code=408,
                context={"endpoint": method}
            )
        elif isinstance(err, aiohttp.ClientError):
            error = DiscordWebhookError(
                f"Request failed: {err}",
                context={"endpoint": method}
            )
        else:
            error = DiscordWebhookError(
                "Maximum retries exceeded",
                context={"endpoint": method}
            )
        error.__cause__ = err
        return error

    async def _update_error_state(self, error: DiscordWebhookError) -> None:
        """Update provider state after an error.

        Args:
            error: The error that occurred
        """
        async with self._state_lock:
            self._consecutive_errors += 1
            self._state.last_error = error
            self._state.last_error_time = datetime.now()
            
            # Reset error count after successful operation
            if not isinstance(error, DiscordWebhookError):
                self._consecutive_errors = 0

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
        """
        if response.status == 429:  # Rate limited
            retry_after = int(data.get("retry_after", 5))
            self._state.rate_limited = True
            self._state.rate_limit_until = datetime.now().timestamp() + retry_after
            logger.warning(
                "Discord rate limit hit",
                retry_after=retry_after,
                endpoint=str(response.url),
                rate_limited_until=self._state.rate_limit_until
            )
            return retry_after
        return None
