# notifications/providers/discord/provider.py

"""Discord webhook notification provider implementation."""

import asyncio
import random
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, TypedDict, cast

import aiohttp
from pydantic import HttpUrl
from structlog import get_logger
from typing_extensions import NotRequired

from config.constants import (
    API,
    MessagePriority,
    MessageType,
    NotificationLevel,
)
from config.providers.discord.types import WebhookConfig
from notifications.base import (
    NotificationProvider,
)
from notifications.providers.discord.templates import (
    create_batch_embed,
    create_completion_embed,
    create_debug_embed,
    create_error_embed,
    create_interactive_embed,
    create_progress_embed,
    create_system_embed,
    create_warning_embed,
    create_webhook_payload,
)
from notifications.providers.discord.validators import DiscordValidator
from shared.providers.discord import (
    ASSET_DOMAINS,
    WEBHOOK_DOMAINS,
    DiscordColor,
    DiscordWebhookError,
    Embed,
    get_progress_color,
    validate_url,
)

logger = get_logger(__name__)

class DiscordConfig(TypedDict):
    """Discord webhook provider configuration."""
    webhook_url: str
    username: NotRequired[str]
    avatar_url: NotRequired[str]
    thread_name: NotRequired[str]
    color_enabled: NotRequired[bool]
    embed_color: NotRequired[int]
    timeout: NotRequired[float]
    rate_limit: NotRequired[int]
    rate_period: NotRequired[float]
    retry_attempts: NotRequired[int]
    retry_delay: NotRequired[float]

class DiscordProvider(NotificationProvider):
    """Discord webhook notification provider with advanced message formatting and delivery."""

    ALLOWED_DOMAINS = WEBHOOK_DOMAINS
    ALLOWED_ASSET_DOMAINS = ASSET_DOMAINS

    def __init__(self, config: WebhookConfig) -> None:
        """Initialize Discord webhook provider.

        Args:
            config: Provider configuration
        """
        # Validate configuration using dedicated validator
        validator = DiscordValidator()
        self._config = validator.validate_config(cast(Dict[str, Any], config))

        # Extract rate limiting and retry settings with proper type conversion
        rate_limit = self._config.get("rate_limit")
        rate_period = self._config.get("rate_period")
        retry_attempts = self._config.get("retry_attempts")
        retry_delay = self._config.get("retry_delay")

        # Convert values with proper type safety
        try:
            # First convert everything to float, then to int where needed
            rate_limit_float = float(str(rate_limit)) if rate_limit is not None else float(API.DEFAULT_RATE_LIMIT)
            rate_period_float = float(str(rate_period)) if rate_period is not None else float(API.DEFAULT_RATE_PERIOD)
            retry_attempts_float = float(str(retry_attempts)) if retry_attempts is not None else float(API.DEFAULT_RETRY_ATTEMPTS)
            retry_delay_val = float(str(retry_delay)) if retry_delay is not None else API.DEFAULT_RETRY_DELAY

            # Convert to int where needed, ensuring we're passing ints not floats
            rate_limit_val = int(rate_limit_float)
            rate_period_val = int(rate_period_float)
            retry_attempts_val = int(retry_attempts_float)

            # Validate ranges
            if rate_limit_val < 1:
                rate_limit_val = API.DEFAULT_RATE_LIMIT
            if rate_period_val < 1:
                rate_period_val = API.DEFAULT_RATE_PERIOD
            if retry_attempts_val < 0:
                retry_attempts_val = API.DEFAULT_RETRY_ATTEMPTS
            if retry_delay_val < 0.1:
                retry_delay_val = API.DEFAULT_RETRY_DELAY

        except (TypeError, ValueError) as e:
            logger.warning("Invalid config values, using defaults", error=str(e))
            rate_limit_val = API.DEFAULT_RATE_LIMIT
            rate_period_val = API.DEFAULT_RATE_PERIOD
            retry_attempts_val = API.DEFAULT_RETRY_ATTEMPTS
            retry_delay_val = API.DEFAULT_RETRY_DELAY

        # Initialize base class with validated integer values
        super().__init__(
            rate_limit=int(rate_limit_val),  # Ensure int
            rate_period=int(rate_period_val),  # Ensure int
            retry_attempts=int(retry_attempts_val),  # Ensure int
            retry_delay=float(retry_delay_val),
        )

        # Validate and extract webhook URL
        webhook_url = str(self._config["webhook_url"])
        if not webhook_url or not validate_url(webhook_url, WEBHOOK_DOMAINS):
            raise DiscordWebhookError(
                f"Invalid webhook URL: {webhook_url}. Must be a valid Discord webhook URL.",
                context={"endpoint": webhook_url}
            )

        # Extract validated configuration with proper type conversion
        self._webhook_url: str = webhook_url

        # Handle optional string fields
        username = self._config.get("username")
        self._username: Optional[str] = str(username) if username is not None else None

        # Handle avatar URL with proper type conversion
        avatar_url = self._config.get("avatar_url")
        self._avatar_url: Optional[HttpUrl] = HttpUrl(str(avatar_url)) if avatar_url is not None else None

        # Handle thread name
        thread_name = self._config.get("thread_name")
        self._thread_name: Optional[str] = str(thread_name) if thread_name is not None else None

        # Handle boolean and color settings
        color_enabled = self._config.get("color_enabled")
        self._color_enabled: bool = bool(color_enabled) if color_enabled is not None else True

        # Handle embed color with proper type conversion
        embed_color = self._config.get("embed_color")
        if embed_color is not None:
            try:
                color_float = float(str(embed_color))
                self._embed_color = DiscordColor(int(color_float))
            except (TypeError, ValueError):
                logger.warning("Invalid embed color value, using default", value=embed_color)
                self._embed_color = DiscordColor.INFO
        else:
            self._embed_color = DiscordColor.INFO

        self._last_message_id: Optional[str] = None
        self._last_rate_limit: Optional[datetime] = None
        self._current_backoff: float = self._retry_delay
        self._state = self._state  # Initialize state from instance, not class

        # Thread safety locks
        self._session_lock = asyncio.Lock()
        self._state_lock = asyncio.Lock()
        self._message_lock = asyncio.Lock()
        self._rate_limit_lock = asyncio.Lock()

        # Request timeout configuration
        timeout = self._config.get("timeout", API.DEFAULT_TIMEOUT)
        if not isinstance(timeout, (int, float)) or timeout <= 0 or timeout > 300:
            logger.warning(
                "Invalid timeout value, using default",
                timeout=timeout,
                default=API.DEFAULT_TIMEOUT
            )
            timeout = API.DEFAULT_TIMEOUT
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

    async def send_webhook(self, data: Dict[str, Any]) -> bool:
        """Send data to Discord webhook."""
        try:
            if not self._session:
                await self.connect()
                if not self._session:  # Double check after connect
                    raise DiscordWebhookError("Failed to create session")

            timeout = aiohttp.ClientTimeout(total=self._timeout)
            async with self._session.post(
                self._webhook_url,
                json=data,
                timeout=timeout
            ) as response:
                await self._update_rate_limit_state(response)
                response_data = await response.json()
                await self._handle_send_webhook_response(response, response_data)
                return True

        except Exception as e:
            error = self._handle_request_error(e, "send_webhook")
            await self._update_error_state(error)
            raise error from e

    async def send_notification(
        self,
        message: str,
        level: NotificationLevel = NotificationLevel.INFO,
        priority: MessagePriority = MessagePriority.NORMAL,
        message_type: MessageType = MessageType.CUSTOM,
        **kwargs: Any
    ) -> bool:
        """Send notification via Discord webhook."""
        try:
            embed = self._create_typed_embed(message, message_type, level, **kwargs)

            # Create embed dictionary with proper typing
            embed_dict: Dict[str, Any] = {
                "title": embed.get("title"),
                "description": embed.get("description"),
                "color": embed.get("color"),
                "fields": embed.get("fields", []),
                "footer": embed.get("footer"),
                "timestamp": embed.get("timestamp")
            }

            # Create forum config with proper typing
            forum_config: Optional[Dict[str, str]] = None
            if self._thread_name:
                forum_config = {
                    "enabled": "true",
                    "channel_id": "",  # Required by ForumConfig but not used in this context
                    "thread_title": self._thread_name
                }

            # Create webhook payload with proper typing
            payload = create_webhook_payload(
                embeds=[embed_dict],  # Now properly typed as List[Dict[str, Any]]
                username=str(self._username) if self._username else "Mover Bot",
                avatar_url=str(self._avatar_url) if self._avatar_url else None,
                forum_config=forum_config  # Now properly typed as Optional[Dict[str, str]]
            )

            return await self.send_webhook(cast(Dict[str, Any], payload))
        except Exception as err:
            error = self._handle_request_error(err, "send_notification")
            async with self._state_lock:
                self._state.last_error = str(error)
                self._state.last_error_time = datetime.now()
            return False

    async def notify_progress(
        self,
        percent: float,
        message: str,
        **kwargs: Any
    ) -> bool:
        """Send progress notification."""
        try:
            # Create forum config with thread name if present
            forum_config: Optional[Dict[str, str]] = None
            if self._thread_name:
                forum_config = {
                    "enabled": "true",
                    "channel_id": "",  # Required by ForumConfig but not used in this context
                    "thread_title": self._thread_name
                }

            return await self.notify(
                message,
                level=NotificationLevel.INFO,
                message_type=MessageType.PROGRESS,
                percent=percent,
                forum_config=forum_config,
                **kwargs
            )
        except Exception as err:
            error = self._handle_request_error(err, "notify_progress")
            async with self._state_lock:
                self._state.last_error = str(error)
                self._state.last_error_time = datetime.now()
            return False

    async def notify_completion(
        self,
        message: str,
        **kwargs: Any
    ) -> bool:
        """Send completion notification."""
        try:
            # Create forum config with thread name if present
            forum_config: Optional[Dict[str, str]] = None
            if self._thread_name:
                forum_config = {
                    "enabled": "true",
                    "channel_id": "",  # Required by ForumConfig but not used in this context
                    "thread_title": self._thread_name
                }

            return await self.notify(
                message,
                level=NotificationLevel.INFO,
                message_type=MessageType.COMPLETION,
                forum_config=forum_config,
                **kwargs
            )
        except Exception as err:
            error = self._handle_request_error(err, "notify_completion")
            async with self._state_lock:
                self._state.last_error = str(error)
                self._state.last_error_time = datetime.now()
            return False

    async def notify_batch(
        self,
        message: str,
        **kwargs: Any
    ) -> bool:
        """Send batch notification."""
        try:
            # Create forum config with thread name if present
            forum_config: Optional[Dict[str, str]] = None
            if self._thread_name:
                forum_config = {
                    "enabled": "true",
                    "channel_id": "",  # Required by ForumConfig but not used in this context
                    "thread_title": self._thread_name
                }

            return await self.notify(
                message,
                level=NotificationLevel.INFO,
                message_type=MessageType.BATCH,
                forum_config=forum_config,
                **kwargs
            )
        except Exception as err:
            error = self._handle_request_error(err, "notify_batch")
            async with self._state_lock:
                self._state.last_error = str(error)
                self._state.last_error_time = datetime.now()
            return False

    async def notify_error(
        self,
        message: str,
        error: Optional[Exception] = None,
        **kwargs: Any
    ) -> bool:
        """Send error notification."""
        try:
            # Create forum config with thread name if present
            forum_config: Optional[Dict[str, str]] = None
            if self._thread_name:
                forum_config = {
                    "enabled": "true",
                    "channel_id": "",  # Required by ForumConfig but not used in this context
                    "thread_title": self._thread_name
                }

            return await self.notify(
                message,
                level=NotificationLevel.ERROR,
                message_type=MessageType.ERROR,
                error=error,
                forum_config=forum_config,
                **kwargs
            )
        except Exception as err:
            error = self._handle_request_error(err, "notify_error")
            async with self._state_lock:
                self._state.last_error = str(error)
                self._state.last_error_time = datetime.now()
            return False

    async def notify_warning(
        self,
        warning_message: str,
        warning_details: Optional[Dict[str, Any]] = None,
        suggestion: Optional[str] = None,
        use_native_timestamps: bool = True
    ) -> None:
        """Send a warning notification."""
        # Create warning message
        message = warning_message
        if warning_details:
            details = "\n".join(f"**{k}:** {v}" for k, v in warning_details.items())
            message = f"{message}\n\n**Details:**\n{details}"
        if suggestion:
            message = f"{message}\n\n**Suggestion:**\n{suggestion}"

        embed = create_warning_embed(
            message=message,
            title="Warning",
            color=DiscordColor.WARNING,
            use_native_timestamps=use_native_timestamps
        )

        await self.send_webhook(cast(Dict[str, Any], create_webhook_payload([embed])))

    async def notify_system(
        self,
        status: str,
        metrics: Optional[Dict[str, Any]] = None,
        issues: Optional[List[str]] = None,
        use_native_timestamps: bool = True
    ) -> None:
        """Send a system status notification."""
        # Create status message
        message = status
        if metrics:
            metrics_text = "\n".join(f"**{k}:** {v}" for k, v in metrics.items())
            message = f"{message}\n\n**Metrics:**\n{metrics_text}"
        if issues:
            issues_text = "\n".join(f"• {issue}" for issue in issues)
            message = f"{message}\n\n**Issues:**\n{issues_text}"

        embed = create_system_embed(
            message=message,
            title="System Status",
            color=DiscordColor.SYSTEM,
            use_native_timestamps=use_native_timestamps
        )

        await self.send_webhook(cast(Dict[str, Any], create_webhook_payload([embed])))

    async def notify_interactive(self, message: str, **kwargs: Any) -> None:
        """Send interactive notification."""
        try:
            # Create forum config with proper typing
            forum_config: Optional[Dict[str, str]] = None
            if self._thread_name:
                forum_config = {
                    "enabled": "true",
                    "channel_id": "",  # Required by ForumConfig but not used in this context
                    "thread_title": self._thread_name
                }

            embed = create_interactive_embed(message, **kwargs)
            payload = create_webhook_payload(
                embeds=[embed],
                username=str(self._username) if self._username else "Mover Bot",
                avatar_url=str(self._avatar_url) if self._avatar_url else None,
                forum_config=forum_config
            )

            await self.send_webhook(cast(Dict[str, Any], payload))
        except Exception as e:
            logger.error("Failed to send interactive notification", error=str(e))
            raise

    async def notify_debug(self, message: str, **kwargs: Any) -> None:
        """Send debug notification."""
        try:
            # Create forum config with proper typing
            forum_config: Optional[Dict[str, str]] = None
            if self._thread_name:
                forum_config = {
                    "enabled": "true",
                    "channel_id": "",  # Required by ForumConfig but not used in this context
                    "thread_title": self._thread_name
                }

            embed = create_debug_embed(message, **kwargs)
            payload = create_webhook_payload(
                embeds=[embed],
                username=str(self._username) if self._username else "Mover Bot",
                avatar_url=str(self._avatar_url) if self._avatar_url else None,
                forum_config=forum_config
            )

            await self.send_webhook(cast(Dict[str, Any], payload))
        except Exception as e:
            logger.error("Failed to send debug notification", error=str(e))
            raise

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

    def _get_retry_delay(self) -> float:
        """Calculate retry delay with jitter.

        Returns:
            float: Delay in seconds
        """
        jitter = random.uniform(0, 0.1)  # Add small random jitter
        return float(self._retry_delay) + jitter

    def _create_typed_embed(
        self,
        message: str,
        message_type: MessageType,
        level: NotificationLevel,
        **kwargs: Any
    ) -> Embed:
        """Create appropriate embed based on message type."""
        if message_type == MessageType.WARNING:
            return cast(Embed, create_warning_embed(
                message=message,
                title="Warning",
                color=self._get_level_color(level),
                use_native_timestamps=kwargs.get("use_native_timestamps", True)
            ))

        elif message_type == MessageType.SYSTEM:
            return cast(Embed, create_system_embed(
                message=message,
                title="System Status",
                color=self._get_level_color(level),
                use_native_timestamps=kwargs.get("use_native_timestamps", True)
            ))

        elif message_type == MessageType.PROGRESS:
            return cast(Embed, create_progress_embed(
                percent=kwargs.get("percent", 0),
                remaining=kwargs.get("remaining", "Unknown"),
                elapsed=kwargs.get("elapsed", "Unknown"),
                etc=kwargs.get("etc", "Unknown"),
                description=message
            ))

        elif message_type == MessageType.COMPLETION:
            return cast(Embed, create_completion_embed(
                description=message,
                stats=kwargs.get("stats")
            ))

        elif message_type == MessageType.ERROR:
            return cast(Embed, create_error_embed(
                error_message=message,
                error_code=kwargs.get("error_code"),
                error_details=kwargs.get("error_details")
            ))

        elif message_type == MessageType.BATCH:
            return cast(Embed, create_batch_embed(
                operation=kwargs.get("operation", "Operation"),
                items=kwargs.get("items", []),
                summary=message
            ))

        elif message_type == MessageType.INTERACTIVE:
            return cast(Embed, create_interactive_embed(
                title=kwargs.get("title", "Interactive Message"),
                description=message,
                actions=kwargs.get("actions", []),
                expires_in=kwargs.get("expires_in")
            ))

        elif message_type == MessageType.DEBUG:
            return cast(Embed, create_debug_embed(
                message=message,
                context=kwargs.get("context"),
                stack_trace=kwargs.get("stack_trace")
            ))

        # Default to custom message type
        return cast(Embed, {
            "title": kwargs.get("title", "Notification"),
            "description": message,
            "color": self._get_level_color(level),
            "timestamp": datetime.utcnow().isoformat()
        })

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
            self._state.last_error = str(error)
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

    def _create_embed(
        self,
        title: str,
        description: str,
        color: int,
        footer_text: str
    ) -> Embed:
        """Create an embed that strictly matches Embed TypedDict."""
        return {
            'type': cast(Literal['rich'], 'rich'),  # Using already imported cast
            'title': title,
            'description': description,
            'color': color,
            'timestamp': datetime.now().isoformat(),
            'footer': {'text': footer_text}  # Matches EmbedFooter definition
        }


    def _create_status_embed(self, status: str, color: int) -> Embed:
        """Create a status embed with standard format."""
        return cast(Embed, self._create_embed(
            title="Status Update",
            description=status,
            color=color,
            footer_text="MoverStatus Bot"
        ))

    def _create_progress_embed(self, progress: float, message: str) -> Embed:
        """Create a progress update embed."""
        return cast(Embed, self._create_embed(
            title="Progress Update",
            description=message,
            color=get_progress_color(progress),
            footer_text=f"{progress:.1f}% Complete"
        ))

    def _create_error_embed(self, error: str) -> Embed:
        """Create an error notification embed."""
        return cast(Embed, self._create_embed(
            title="Error",
            description=error,
            color=DiscordColor.ERROR,
            footer_text="Error Report"
        ))

    def _create_warning_embed(self, warning: str) -> Embed:
        """Create a warning notification embed."""
        return cast(Embed, self._create_embed(
            title="Warning",
            description=warning,
            color=DiscordColor.WARNING,
            footer_text="Warning Notice"
        ))

    def _create_info_embed(self, info: str) -> Embed:
        """Create an informational notification embed."""
        return cast(Embed, self._create_embed(
            title="Information",
            description=info,
            color=DiscordColor.INFO,
            footer_text="Info Update"
        ))

    def _create_debug_embed(self, debug: str) -> Embed:
        """Create a debug notification embed."""
        return cast(Embed, self._create_embed(
            title="Debug",
            description=debug,
            color=DiscordColor.DEBUG,
            footer_text="Debug Info"
        ))

    def _create_system_embed(self, message: str) -> Embed:
        """Create a system notification embed."""
        return cast(Embed, self._create_embed(
            title="System Message",
            description=message,
            color=DiscordColor.SYSTEM,
            footer_text="System Notification"
        ))

    def _create_completion_embed(self, message: str) -> Embed:
        """Create a completion notification embed."""
        return cast(Embed, self._create_embed(
            title="Task Complete",
            description=message,
            color=DiscordColor.SUCCESS,
            footer_text="Completion Notice"
        ))
