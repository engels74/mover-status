# notifications/providers/discord/provider.py

"""Discord webhook notification provider implementation.

This module implements a Discord webhook-based notification provider that sends
messages, progress updates, and error notifications to Discord channels.

Configuration:
    The provider requires a Discord webhook URL and supports optional settings:
    - username: Custom webhook username
    - avatar_url: Custom webhook avatar URL
    - thread_name: Target thread for messages
    - color_enabled: Enable/disable message colors
    - embed_color: Default embed color
    - timeout: Request timeout in seconds
    - rate_limit: Maximum requests per period
    - rate_period: Rate limit period in seconds
    - retry_attempts: Maximum retry attempts
    - retry_delay: Initial retry delay in seconds

Key Features:
    - Message types: text, embeds, progress bars, error reports
    - Rate limiting and retry handling
    - Thread-safe async operations
    - Configurable timeouts and retries
    - Custom webhook appearance

Example:
    >>> from notifications.providers.discord import DiscordProvider
    >>>
    >>> # Basic configuration
    >>> config = {
    ...     "webhook_url": "https://discord.com/api/webhooks/123/abc",
    ...     "username": "Status Bot",
    ...     "timeout": 30.0,
    ...     "color_enabled": True
    ... }
    >>>
    >>> async with DiscordProvider(config) as provider:
    ...     # Send basic notification
    ...     await provider.notify("Transfer complete!")
    ...
    ...     # Send progress update
    ...     await provider.notify_progress(
    ...         percent=50,
    ...         remaining="500MB",
    ...         elapsed="1m 30s",
    ...         etc="3m 0s"
    ...     )
    ...
    ...     # Send error notification
    ...     await provider.notify_error(
    ...         "Connection failed",
    ...         error_code=404,
    ...         error_details={"host": "example.com"}
    ...     )

Note:
    This provider implements Discord's webhook rate limits and backoff
    requirements. For details, see:
    https://discord.com/developers/docs/topics/rate-limits
"""

import asyncio
import random
from datetime import datetime
from typing import Any, Dict, Final, Optional, TypedDict, Union

import aiohttp
from pydantic import HttpUrl
from structlog import get_logger

from config.constants import MessagePriority, MessageType, NotificationLevel
from notifications.base import NotificationProvider
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
from notifications.providers.discord.types import NotificationState
from notifications.providers.discord.validators import DiscordValidator
from shared.providers.discord import (
    ASSET_DOMAINS,
    WEBHOOK_DOMAINS,
    AssetDomains,
    DiscordColor,
    DiscordWebhookError,
    Embed,
    WebhookDomains,
    validate_url,
)

logger = get_logger(__name__)

# Default timeout settings
DEFAULT_TIMEOUT = 10.0  # seconds
RETRY_LIMIT: Final[int] = 3
BACKOFF_BASE: Final[float] = 2.0

class DiscordConfig(TypedDict, total=False):
    """Discord webhook provider configuration type definition.

    This TypedDict defines the structure and types for Discord provider configuration,
    supporting both required and optional parameters for webhook customization.

    Required Parameters:
        webhook_url (str): Discord webhook URL for message delivery
            Format: https://discord.com/api/webhooks/{webhook.id}/{webhook.token}

    Optional Parameters:
        username (Optional[str]): Custom username for the webhook
        avatar_url (Optional[str]): Custom avatar URL for the webhook
        thread_name (Optional[str]): Name of thread to create/use
        color_enabled (Optional[bool]): Enable/disable embed colors

    Example:
        >>> config: DiscordConfig = {
        ...     "webhook_url": "https://discord.com/api/webhooks/123/abc",
        ...     "username": "Status Bot",
        ...     "color_enabled": True
        ... }
        >>> provider = DiscordProvider(config)
    """
    webhook_url: str
    username: Optional[str]
    avatar_url: Optional[str]
    thread_name: Optional[str]
    color_enabled: Optional[bool]

class DiscordProvider(NotificationProvider):
    """Discord webhook notification provider with advanced message formatting and delivery.

    This provider implements Discord webhook integration with support for rich message
    formatting, rate limiting, and error handling. It extends the base NotificationProvider
    with Discord-specific functionality and robust error recovery mechanisms.

    Features:
        - Rich Message Formatting:
            * Customizable embeds with dynamic colors
            * Progress bar visualization
            * Support for system, error, warning, and debug messages
            * Thread support for organized discussions

        - Reliability & Performance:
            * Automatic rate limit handling
            * Configurable retry logic
            * Connection pooling
            * Thread-safe operations

        - Monitoring & Error Handling:
            * Comprehensive error tracking
            * Rate limit monitoring
            * Message delivery statistics
            * Structured logging

    Configuration:
        The provider is configured through a DiscordConfig dictionary containing
        webhook settings and customization options. See DiscordConfig for details.

    Rate Limiting:
        - Implements Discord's rate limit guidelines
        - Automatic backoff on rate limit errors
        - Configurable rate limit parameters
        - State tracking for rate limit headers

    Thread Safety:
        All operations are protected by appropriate locks:
        - _session_lock: Protects session lifecycle
        - _state_lock: Protects provider state
        - _message_lock: Ensures sequential message sending
        - _rate_limit_lock: Manages rate limit state

    Example:
        >>> config = {
        ...     "webhook_url": "https://discord.com/api/webhooks/123/abc",
        ...     "username": "Status Bot",
        ...     "rate_limit": 30,  # messages per minute
        ...     "retry_attempts": 3
        ... }
        >>>
        >>> async with DiscordProvider(config) as provider:
        ...     # Send system notification
        ...     await provider.notify(
        ...         "Backup started",
        ...         type=MessageType.SYSTEM,
        ...         level=NotificationLevel.INFO
        ...     )
        ...
        ...     # Send progress update
        ...     await provider.notify(
        ...         "Processing files",
        ...         type=MessageType.PROGRESS,
        ...         progress=50,
        ...         total=100
        ...     )
        ...
        ...     # Send completion notification
        ...     await provider.notify(
        ...         "Backup completed",
        ...         type=MessageType.COMPLETION,
        ...         level=NotificationLevel.SUCCESS
        ...     )

    Note:
        - Always use the provider as an async context manager for proper resource cleanup
        - Configure appropriate timeouts for your use case
        - Monitor rate limit state for optimal performance
        - Use structured error handling for production deployments
    """

    ALLOWED_DOMAINS: Final[WebhookDomains] = WEBHOOK_DOMAINS
    ALLOWED_ASSET_DOMAINS: Final[AssetDomains] = ASSET_DOMAINS

    def __init__(self, config: DiscordConfig):
        """Initialize a new Discord webhook provider instance.

        Creates a new provider instance with the specified configuration, setting up
        connection management, rate limiting, and thread safety mechanisms.

        Args:
            config (DiscordConfig): Provider configuration containing:
                - webhook_url: Discord webhook URL
                - username: Optional custom username
                - avatar_url: Optional custom avatar URL
                - thread_name: Optional thread to post in
                - color_enabled: Optional color support flag
                - embed_color: Optional default embed color
                - timeout: Optional request timeout (default: 10.0s)
                - rate_limit: Optional rate limit (requests/period)
                - rate_period: Optional rate limit period in seconds
                - retry_attempts: Optional max retry attempts
                - retry_delay: Optional initial retry delay

        Raises:
            ValueError: If configuration validation fails
            DiscordWebhookError: If webhook URL is invalid

        Example:
            >>> config = {
            ...     "webhook_url": "https://discord.com/api/webhooks/123/abc",
            ...     "username": "Status Bot",
            ...     "timeout": 30.0,
            ...     "rate_limit": 30
            ... }
            >>> provider = DiscordProvider(config)
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
        self._color_enabled: bool = self._config.get("color_enabled", True)
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
        if not isinstance(timeout, (int, float)) or timeout <= 0 or timeout > 300:
            logger.warning(
                "Invalid timeout value, using default",
                timeout=timeout,
                default=DEFAULT_TIMEOUT
            )
            timeout = DEFAULT_TIMEOUT
        self._timeout: float = float(timeout)

        # Session and rate limit management
        self._session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self) -> "DiscordProvider":
        """Enter the async context manager, initializing resources.

        This method is called when entering an async context manager block.
        It ensures that the provider is properly initialized and connected.

        Returns:
            DiscordProvider: The initialized provider instance

        Example:
            >>> async with DiscordProvider(config) as provider:
            ...     await provider.notify("Hello, Discord!")
        """
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit the async context manager, cleaning up resources.

        This method is called when exiting an async context manager block.
        It ensures proper cleanup of resources, including closing connections.

        Args:
            exc_type: Type of exception that was raised, if any
            exc_val: Exception instance that was raised, if any
            exc_tb: Traceback of exception that was raised, if any

        Example:
            >>> async with DiscordProvider(config) as provider:
            ...     await provider.notify("Hello!")
            ... # Session is automatically cleaned up here
        """
        await self.disconnect()

    async def connect(self) -> None:
        """Initialize the HTTP session for webhook requests.

        Creates a new aiohttp ClientSession if one doesn't exist or if the
        existing session is closed. The session is configured with the
        provider's timeout settings.

        Thread Safety:
            This method is protected by _session_lock for thread safety.

        Example:
            >>> provider = DiscordProvider(config)
            >>> await provider.connect()
            >>> # Session is now ready for use
        """
        async with self._session_lock:
            if not self._session or self._session.closed:
                self._session = aiohttp.ClientSession(
                    timeout=aiohttp.ClientTimeout(total=self._timeout)
                )

    async def disconnect(self) -> None:
        """Close the HTTP session and clean up resources.

        Closes the aiohttp ClientSession if it exists and is open.
        Also resets rate limiting and backoff state.

        Thread Safety:
            This method is protected by _session_lock for thread safety.

        Example:
            >>> await provider.disconnect()
            >>> # All resources are now cleaned up
        """
        async with self._session_lock:
            if self._session and not self._session.closed:
                try:
                    await self._session.close()
                finally:
                    self._session = None
                    self._last_rate_limit = None
                    self._current_backoff = self._retry_delay

    async def _update_rate_limit_state(self, response: aiohttp.ClientResponse) -> None:
        """Update the provider's rate limit state based on response headers.

        Processes Discord's rate limit headers to update the provider's internal
        rate limit state, including remaining requests and reset timing.

        Args:
            response (aiohttp.ClientResponse): Response containing rate limit headers:
                - X-RateLimit-Remaining: Number of remaining requests
                - X-RateLimit-Reset-After: Seconds until limit resets

        Thread Safety:
            This method is protected by _rate_limit_lock for thread safety.

        Note:
            Discord's rate limit headers:
            - X-RateLimit-Limit: Total requests allowed
            - X-RateLimit-Remaining: Requests remaining
            - X-RateLimit-Reset: Epoch time when limit resets
            - X-RateLimit-Reset-After: Seconds until reset
            - X-RateLimit-Bucket: Rate limit bucket ID

        Example:
            >>> async with session.post(webhook_url, json=data) as response:
            ...     await provider._update_rate_limit_state(response)
            ...     if response.status == 429:  # Rate limited
            ...         await asyncio.sleep(float(response.headers["Retry-After"]))
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

    async def _handle_send_webhook_response(
        self,
        response: aiohttp.ClientResponse,
        data: Dict[str, Any]
    ) -> None:
        """Handle the webhook response and manage error states.

        Processes the webhook response, handling various status codes and updating
        the provider's state accordingly. Handles rate limits and other errors.

        Args:
            response (aiohttp.ClientResponse): Response from the webhook request
            data (Dict[str, Any]): Original webhook payload that was sent

        Raises:
            DiscordWebhookError: If the request fails due to:
                - Rate limiting (429)
                - Invalid request (4xx)
                - Server error (5xx)

        Error Handling:
            - 429: Rate limit exceeded, includes retry timing
            - 400-499: Client errors (invalid payload, permissions, etc.)
            - 500-599: Server errors

        Example:
            >>> async with session.post(webhook_url, json=data) as response:
            ...     try:
            ...         await provider._handle_send_webhook_response(response, data)
            ...     except DiscordWebhookError as e:
            ...         if e.code == 429:  # Rate limited
            ...             await asyncio.sleep(e.retry_after)
        """
        if response.status == 429:
            # Rate limited
            retry_after = float(response.headers.get("Retry-After", 5))
            error = DiscordWebhookError(
                "Rate limit exceeded",
                code=response.status,
                retry_after=retry_after,
                context={
                    "retry_after": retry_after,
                    "data": data
                }
            )
            await self._update_error_state(error)
            raise error

        elif response.status >= 400:
            # Other errors
            error = DiscordWebhookError(
                f"Webhook request failed with status {response.status}",
                code=response.status,
                context={
                    "status": response.status,
                    "data": data
                }
            )
            await self._update_error_state(error)
            raise error

    async def send_webhook(
        self,
        data: Dict[str, Any],
        max_retries: int = 3
    ) -> bool:
        """Send webhook request with retries.

        Args:
            data (Dict[str, Any]): Webhook payload to send
            max_retries (int): Maximum number of retries (default: 3)

        Returns:
            bool: True if request succeeded

        Raises:
            DiscordWebhookError: If request fails after retries

        Example:
            >>> data = {"content": "Hello, Discord!"}
            >>> await provider.send_webhook(data)
        """
        attempt = 0
        last_error = None

        while attempt <= max_retries:
            try:
                # Ensure session is connected
                if not self._session or self._session.closed:
                    await self.connect()

                # Send request
                async with self._session.post(
                    self._webhook_url,
                    json=data,
                    timeout=self._timeout
                ) as response:
                    # Handle response
                    await self._handle_send_webhook_response(response, data)

                    # Update rate limit state
                    await self._update_rate_limit_state(response)

                    # Reset error state on success
                    async with self._state_lock:
                        self._consecutive_errors = 0
                        self._current_backoff = self._retry_delay
                        self._state.last_success = datetime.now()
                        self._state.total_retries = 0

                    return True

            except DiscordWebhookError as err:
                last_error = err
                attempt += 1

                if attempt <= max_retries:
                    # Calculate backoff delay
                    delay = self._calculate_backoff(attempt)
                    await asyncio.sleep(delay)
                    continue

                raise DiscordWebhookError(
                    f"Max retries ({max_retries}) exceeded",
                    context={
                        "attempts": attempt,
                        "max_retries": max_retries,
                        "last_error": str(last_error)
                    }
                ) from err

            except asyncio.TimeoutError as err:
                last_error = DiscordWebhookError(
                    "Request timed out",
                    context={"timeout": self._timeout}
                )
                await self._update_error_state(last_error)
                raise last_error from err

            except Exception as err:
                error = self._handle_request_error(err, "send_webhook")
                await self._update_error_state(error)
                raise error from err

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
            message (str): Message content
            level (NotificationLevel): Notification level (default: INFO)
            priority (MessagePriority): Message priority (default: NORMAL)
            message_type (MessageType): Type of message (default: CUSTOM)
            **kwargs: Additional message parameters

        Returns:
            bool: True if message was sent successfully

        Raises:
            DiscordError: If sending fails

        Example:
            >>> await provider.send_notification("Hello, Discord!")
        """
        async with self._message_lock:
            try:
                # Create webhook payload
                payload = await self._create_webhook_payload(
                    message, level, message_type, **kwargs
                )

                # Send webhook request
                async with self._session_lock:
                    if not self._session or self._session.closed:
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
                raise error from err

    def _calculate_backoff(self, attempt: int) -> float:
        """Calculate exponential backoff delay.

        Args:
            attempt (int): Current attempt number

        Returns:
            float: Delay in seconds
        """
        # Exponential backoff with jitter
        max_backoff = min(self._retry_delay * (2 ** attempt), 30)  # Cap at 30 seconds
        return random.uniform(0, max_backoff)

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
            percent (float): Progress percentage
            remaining (str): Remaining data amount
            elapsed (str): Elapsed time
            etc (str): Estimated time of completion
            description (Optional[str]): Optional description

        Returns:
            bool: True if notification was sent successfully

        Raises:
            DiscordWebhookError: If notification fails

        Example:
            >>> await provider.notify_progress(50, "10MB", "10s", "10s")
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
            raise error from err

    async def notify_completion(
        self,
        stats: Optional[Dict[str, Union[str, int, float]]] = None
    ) -> bool:
        """Send completion notification.

        Args:
            stats (Optional[Dict[str, Union[str, int, float]]]): Optional transfer statistics to include

        Returns:
            bool: True if notification was sent successfully

        Raises:
            DiscordWebhookError: If notification fails

        Example:
            >>> await provider.notify_completion({"files": 10, "size": "10MB"})
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
            raise error from err

    async def notify_error(
        self,
        error_message: str,
        error_code: Optional[int] = None,
        error_details: Optional[Dict[str, str]] = None
    ) -> bool:
        """Send error notification.

        Args:
            error_message (str): Error description
            error_code (Optional[int]): Optional error code
            error_details (Optional[Dict[str, str]]): Optional error details

        Returns:
            bool: True if notification was sent successfully

        Raises:
            DiscordWebhookError: If notification fails

        Example:
            >>> await provider.notify_error("Connection failed", 404, {"host": "example.com"})
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
            raise error from err

    def _create_typed_embed(
        self,
        message: str,
        message_type: MessageType,
        level: NotificationLevel,
        **kwargs
    ) -> Embed:
        """Create appropriate embed based on message type.

        Args:
            message (str): Message content
            message_type (MessageType): Type of message
            level (NotificationLevel): Notification level
            **kwargs: Additional message-specific arguments

        Returns:
            Embed: Formatted Discord embed

        Example:
            >>> embed = provider._create_typed_embed("Hello!", MessageType.CUSTOM, NotificationLevel.INFO)
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

    def _get_level_color(self, level: NotificationLevel) -> Optional[int]:
        """Get Discord color based on notification level.

        Args:
            level (NotificationLevel): Notification level

        Returns:
            Optional[int]: Discord color code, or None if colors are disabled

        Example:
            >>> color = provider._get_level_color(NotificationLevel.INFO)
        """
        if not self._color_enabled:
            return None

        return {
            NotificationLevel.DEBUG: DiscordColor.DEBUG,
            NotificationLevel.INFO: DiscordColor.INFO,
            NotificationLevel.WARNING: DiscordColor.WARNING,
            NotificationLevel.ERROR: DiscordColor.ERROR,
            NotificationLevel.CRITICAL: DiscordColor.ERROR,
        }.get(level, DiscordColor.INFO)

    def _handle_request_error(
        self,
        err: Exception,
        method: str
    ) -> DiscordWebhookError:
        """Handle request errors and create appropriate DiscordWebhookError.

        Args:
            err (Exception): Original exception
            method (str): API method name

        Returns:
            DiscordWebhookError: Wrapped error with context

        Example:
            >>> error = provider._handle_request_error(err, "send_webhook")
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
            error (DiscordWebhookError): The error that occurred

        Example:
            >>> await provider._update_error_state(error)
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
            response (aiohttp.ClientResponse): API response
            data (Dict[str, Any]): Response data dictionary

        Returns:
            Optional[int]: Retry delay in seconds if rate limited

        Example:
            >>> delay = await provider._handle_rate_limit(response, data)
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
