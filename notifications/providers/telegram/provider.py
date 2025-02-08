# notifications/providers/telegram/provider.py

"""Telegram bot notification provider implementation.

This module implements a Telegram Bot API-based notification provider with support
for message threading, rate limiting, and automatic error recovery.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, Dict, Final, Optional, Set, Tuple, TypedDict, Union
from urllib.parse import urljoin

import aiohttp
from aiohttp import ClientTimeout
from structlog import get_logger

from config.constants import (
    API,
    MessagePriority,
    MessageType,
    NotificationLevel,
)
from notifications.base import (
    NotificationProvider,
    NotificationState,
)
from notifications.providers.telegram.templates import (
    create_batch_message,
    create_completion_message,
    create_debug_message,
    create_error_message,
    create_interactive_message,
    create_progress_message,
    create_system_message,
    create_warning_message,
)
from shared.providers.telegram import (
    ParseMode,
    TelegramDomains,
)
from shared.providers.telegram.errors import (
    TelegramApiError,
    TelegramError,
)

logger = get_logger(__name__)

# Constants
MAX_CONSECUTIVE_ERRORS: Final[int] = 5
BACKOFF_BASE: Final[float] = 2.0
DEFAULT_TIMEOUT: Final[float] = 10.0  # seconds

class TelegramConfig(TypedDict, total=False):
    """Telegram provider configuration type."""
    bot_token: str
    chat_id: Union[int, str]
    thread_id: Optional[int]

class TelegramProvider(NotificationProvider):
    """Telegram bot notification provider.

    This class implements a notification provider that sends messages through
    the Telegram Bot API. It supports various message types, priority-based
    rate limiting, and automatic error recovery.

    Features:
        - Priority-based rate limiting
        - Automatic retry with exponential backoff
        - Thread-safe async operations
        - Message thread support
        - Content protection options
        - Custom parse modes (HTML/Markdown)

    Example:
        >>> config = {
        ...     "bot_token": "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
        ...     "chat_id": "-1001234567890",
        ...     "parse_mode": "HTML",
        ...     "disable_notifications": False
        ... }
        >>> async with TelegramProvider(config) as provider:
        ...     # Send a high-priority notification
        ...     await provider.notify(
        ...         "Critical system alert",
        ...         level=NotificationLevel.ERROR,
        ...         priority=MessagePriority.HIGH
        ...     )
    """

    def __init__(
        self,
        bot_token: str,
        chat_id: str,
        parse_mode: ParseMode = ParseMode.HTML,
        rate_limit: int = API.DEFAULT_RATE_LIMIT,
        rate_period: int = API.DEFAULT_RATE_PERIOD,
        retry_attempts: int = API.DEFAULT_RETRY_ATTEMPTS,
        retry_delay: float = API.DEFAULT_RETRY_DELAY,
        timeout: float = API.DEFAULT_TIMEOUT
    ):
        """Initialize the Telegram notification provider.

        Sets up the provider with the specified configuration, initializing
        priority-based rate limits, retry settings, and connection management.

        Args:
            bot_token (str): Telegram bot API token
            chat_id (str): Target chat/channel ID
            parse_mode (ParseMode): Message parsing mode (HTML/Markdown)
            rate_limit (int): Maximum requests per period
            rate_period (int): Rate limit period in seconds
            retry_attempts (int): Maximum retry attempts
            retry_delay (float): Initial retry delay in seconds
            timeout (float): Request timeout in seconds

        Raises:
            ValueError: If configuration validation fails
            TelegramError: If bot token or chat ID is invalid

        Note:
            Priority-based rate limits are automatically adjusted:
            - Low priority: 50% of base rate limit
            - Normal priority: Base rate limit
            - High priority: 200% of base rate limit
        """
        # Validate configuration using dedicated validator
        self._config = self.validate_config({
            "bot_token": bot_token,
            "chat_id": chat_id,
            "parse_mode": parse_mode,
            "rate_limit": rate_limit,
            "rate_period": rate_period,
            "retry_attempts": retry_attempts,
            "retry_delay": retry_delay,
            "timeout": timeout
        })

        # Initialize priority-based rate limits and retries
        self._priority_rate_limits = {
            MessagePriority.LOW: self._config["rate_limit"] // 2,  # Lower rate limit for low priority
            MessagePriority.NORMAL: self._config["rate_limit"],    # Default rate limit
            MessagePriority.HIGH: self._config["rate_limit"] * 2   # Higher rate limit for high priority
        }
        self._priority_retry_attempts = {
            MessagePriority.LOW: max(1, self._config["retry_attempts"] // 2),  # Fewer retries for low priority
            MessagePriority.NORMAL: self._config["retry_attempts"],            # Default retries
            MessagePriority.HIGH: self._config["retry_attempts"] * 2          # More retries for high priority
        }

        super().__init__(
            rate_limit=self._config["rate_limit"],
            rate_period=self._config["rate_period"],
            retry_attempts=self._config["retry_attempts"],
            retry_delay=self._config["retry_delay"],
        )

        # Extract validated configuration
        self.bot_token: str = self._config["bot_token"]
        self.chat_id: str = self._config["chat_id"]
        self.parse_mode: ParseMode = self._config["parse_mode"]
        self.timeout: float = self._config["timeout"]
        self._session: Optional[aiohttp.ClientSession] = None
        self._last_message_id: Optional[int] = None
        self._message_priority: MessagePriority = MessagePriority.NORMAL
        self._state = NotificationState()  # Initialize state
        self._consecutive_errors: int = 0
        self._last_error_time: Optional[datetime] = None
        self._tags: Set[str] = set(self._config.get("tags", []))

        # Thread safety
        self._session_lock = asyncio.Lock()
        self._state_lock = asyncio.Lock()
        self._message_lock = asyncio.Lock()

    async def __aenter__(self) -> "TelegramProvider":
        """Enter the async context manager.

        Initializes the provider's resources, including the HTTP session.
        This method is called when entering an async context manager block.

        Returns:
            TelegramProvider: The initialized provider instance

        Example:
            >>> async with TelegramProvider(config) as provider:
            ...     await provider.notify("Hello!")
        """
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit the async context manager.

        Cleans up provider resources, including closing the HTTP session.
        This method is called when exiting an async context manager block.

        Args:
            exc_type: Type of exception that was raised, if any
            exc_val: Exception instance that was raised, if any
            exc_tb: Traceback of exception that was raised, if any

        Example:
            >>> async with TelegramProvider(config) as provider:
            ...     await provider.notify("Hello!")
            ... # Session is automatically cleaned up here
        """
        await self.disconnect()

    async def connect(self) -> None:
        """Initialize aiohttp session for API requests.

        Creates a new aiohttp ClientSession if one doesn't exist or if the
        existing session is closed. The session is configured with the
        provider's timeout settings.

        Thread Safety:
            This method is protected by _session_lock for thread safety.

        Example:
            >>> provider = TelegramProvider(config)
            >>> await provider.connect()
            >>> # Session is now ready for use
        """
        async with self._session_lock:
            if not self._session or self._session.closed:
                self._session = aiohttp.ClientSession(
                    timeout=ClientTimeout(total=self.timeout)
                )

    async def disconnect(self) -> None:
        """Close aiohttp session.

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
                await self._session.close()
                self._session = None

    async def _handle_response(self, response_data: Dict[str, Any], method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle Telegram API response data."""
        if not response_data.get("ok"):
            error_code = response_data.get("error_code")
            error_msg = response_data.get("description", "Unknown error")
            raise TelegramApiError(
                error_msg,
                code=error_code,
                context={"method": method, "data": data}
            )
        return response_data["result"]

    async def _execute_request(self, url: str, data: Dict[str, Any]) -> Tuple[aiohttp.ClientResponse, Dict[str, Any]]:
        """Execute a request to the Telegram API with retries."""
        if not self._session:
            await self.connect()
            if not self._session:  # Double check after connect
                raise TelegramError("Failed to establish session")

        try:
            async with self._session.post(url, json=data, timeout=ClientTimeout(total=self.timeout)) as response:
                response_data = await response.json()
                return response, response_data
        except AttributeError as e:
            raise TelegramError("Failed to execute request: " + str(e)) from e

    async def _send_api_request(
        self,
        method: str,
        data: Dict[str, Any],
        retries: Optional[int] = None
    ) -> Dict[str, Any]:
        """Send request to Telegram API with retries."""
        if not self._session:
            await self.connect()
            if not self._session:  # Double check after connect
                raise TelegramError("Failed to establish session")

        if self._state.disabled:
            raise TelegramError("Provider is disabled")

        max_retries = retries if retries is not None else self._retry_attempts
        retry_delay = self._retry_delay
        url = urljoin(f"https://{TelegramDomains.API}/bot{self.bot_token}/", method)

        for attempt in range(max_retries + 1):
            try:
                response, response_data = await self._execute_request(url, data)
                # Handle rate limiting
                if response.status == 429:
                    retry_after = response_data.get("parameters", {}).get("retry_after", retry_delay)
                    await self._handle_rate_limit(retry_after)
                    continue

                return await self._handle_response(response_data, method, data)

            except aiohttp.ClientError as err:
                if attempt == max_retries:
                    raise TelegramError(
                        f"Request failed after {max_retries} retries: {err}",
                        context={"endpoint": method, "error": str(err)}
                    ) from err
                await asyncio.sleep(retry_delay * (2 ** attempt))  # Exponential backoff

            except asyncio.TimeoutError as err:
                if attempt == max_retries:
                    raise TelegramError(
                        f"Request timed out after {max_retries} retries",
                        context={"endpoint": method, "error": str(err)}
                    ) from err
                await asyncio.sleep(retry_delay * (2 ** attempt))  # Exponential backoff

        # This should never be reached due to the error handling above
        raise TelegramError("Unexpected error in API request")

    async def _handle_rate_limit(self, retry_after: float) -> None:
        """Handle rate limiting by updating state and waiting."""
        self._state.rate_limited = True
        self._state.rate_limit_until = datetime.now().timestamp() + retry_after

        # Wait for the rate limit to expire
        await asyncio.sleep(retry_after)

        self._state.rate_limited = False
        self._state.rate_limit_until = None

    def _format_message(
        self,
        message: str,
        message_type: MessageType = MessageType.CUSTOM,
        level: NotificationLevel = NotificationLevel.INFO,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """Format message based on type and level."""
        if message_type == MessageType.PROGRESS:
            return create_progress_message(
                percent=kwargs.get("percent", 0),
                remaining_data=kwargs.get("remaining", "Unknown"),
                elapsed_time=kwargs.get("elapsed", "Unknown"),
                etc=kwargs.get("etc", "Unknown"),
                priority=self._get_level_priority(level),
                add_keyboard=kwargs.get("add_keyboard", True),
                description=message if message else None
            )
        elif message_type == MessageType.COMPLETION:
            return create_completion_message(
                stats=kwargs.get("stats"),
                priority=self._get_level_priority(level),
                include_stats=kwargs.get("include_stats", True)
            )
        elif message_type == MessageType.ERROR:
            return create_error_message(
                error_message=message,
                parse_mode=ParseMode.HTML,
                include_debug=kwargs.get("include_debug", False),
                debug_info=kwargs.get("debug_info"),
                priority=self._get_level_priority(level)
            )
        elif message_type == MessageType.WARNING:
            warning_data = create_warning_message(
                warning_message=message,
                warning_details=kwargs.get("warning_details"),
                suggestion=kwargs.get("suggestion")
            )
            return {"text": warning_data, "parse_mode": self.parse_mode}

        elif message_type == MessageType.SYSTEM:
            system_data = create_system_message(
                status=message,
                metrics=kwargs.get("metrics"),
                issues=kwargs.get("issues")
            )
            return {"text": system_data, "parse_mode": self.parse_mode}

        elif message_type == MessageType.BATCH:
            batch_data = create_batch_message(
                operation=kwargs.get("operation", "Operation"),
                items=kwargs.get("items", []),
                summary=message
            )
            return {"text": batch_data, "parse_mode": self.parse_mode}

        elif message_type == MessageType.INTERACTIVE:
            text, keyboard = create_interactive_message(
                title=kwargs.get("title", "Interactive Message"),
                description=message,
                actions=kwargs.get("actions", []),
                expires_in=kwargs.get("expires_in")
            )
            return {
                "text": text,
                "reply_markup": keyboard,
                "parse_mode": self.parse_mode
            }

        elif message_type == MessageType.DEBUG:
            debug_data = create_debug_message(
                message=message,
                context=kwargs.get("context"),
                stack_trace=kwargs.get("stack_trace")
            )
            return {"text": debug_data, "parse_mode": self.parse_mode}

        else:  # MessageType.CUSTOM
            return {
                "text": message,
                "parse_mode": self.parse_mode
            }

    def _get_level_priority(self, level: NotificationLevel) -> MessagePriority:
        """Get message priority based on notification level."""
        return {
            NotificationLevel.DEBUG: MessagePriority.LOW,
            NotificationLevel.INFO: MessagePriority.NORMAL,
            NotificationLevel.WARNING: MessagePriority.HIGH,
            NotificationLevel.ERROR: MessagePriority.HIGH,
            NotificationLevel.CRITICAL: MessagePriority.HIGH,
            NotificationLevel.INFO_SUCCESS: MessagePriority.NORMAL,
            NotificationLevel.INFO_FAILURE: MessagePriority.HIGH,
        }.get(level, MessagePriority.NORMAL)

    async def notify_progress(
        self,
        percent: float,
        remaining_data: str,
        elapsed_time: str,
        etc: str,
        description: Optional[str] = None
    ) -> bool:
        """Send progress update notification."""
        try:
            message = self._format_message(
                description or "",
                MessageType.PROGRESS,
                NotificationLevel.INFO,
                percent=percent,
                remaining=remaining_data,
                elapsed=elapsed_time,
                etc=etc
            )
            return await self.send_notification(message["text"], message_type=MessageType.PROGRESS)
        except TelegramError as err:
            logger.error("Failed to send progress notification", error=err)
            return False

    async def notify_completion(
        self,
        stats: Optional[Dict[str, Union[str, int, float]]] = None
    ) -> bool:
        """Send completion notification."""
        try:
            message = self._format_message(
                "Operation Complete",
                MessageType.COMPLETION,
                NotificationLevel.INFO,
                stats=stats
            )
            return await self.send_notification(message["text"], message_type=MessageType.COMPLETION)
        except TelegramError as err:
            logger.error("Failed to send completion notification", error=err)
            return False

    async def notify_error(
        self,
        error_message: str,
        error_code: Optional[int] = None,
        error_details: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Send error notification."""
        try:
            message = self._format_message(
                error_message,
                MessageType.ERROR,
                NotificationLevel.ERROR,
                error_code=error_code,
                error_details=error_details
            )
            return await self.send_notification(message["text"], message_type=MessageType.ERROR)
        except TelegramError as err:
            logger.error("Failed to send error notification", error=err)
            return False

    async def send_notification(
        self,
        message: str,
        level: NotificationLevel = NotificationLevel.INFO,
        priority: MessagePriority = MessagePriority.NORMAL,
        message_type: MessageType = MessageType.CUSTOM,
        **kwargs: Any
    ) -> bool:
        """Send a notification message via Telegram Bot API.

        Primary method for sending notifications through Telegram. Supports
        various message types and priority levels with automatic rate limiting
        and error handling.

        Args:
            message (str): Content of the notification message
            level (NotificationLevel): Severity level of the notification
                (default: INFO)
            priority (MessagePriority): Message delivery priority affecting
                rate limiting (default: NORMAL)
            message_type (MessageType): Type of message to send, affects
                formatting (default: CUSTOM)
            **kwargs: Additional message-specific arguments:
                - parse_mode: Override default parse mode
                - disable_web_preview: Disable link previews
                - reply_to_message_id: Message to reply to
                - buttons: List of inline keyboard buttons
                - photo_url: URL for photo messages
                - video_url: URL for video messages
                - document_url: URL for document messages

        Returns:
            bool: True if message was sent successfully

        Raises:
            TelegramError: If message sending fails
            ValueError: If message type is invalid or required args missing

        Example:
            >>> # Send a simple text message
            >>> await provider.send_notification("Hello!")
            True

            >>> # Send a high priority HTML message
            >>> await provider.send_notification(
            ...     "<b>Alert!</b>",
            ...     level=NotificationLevel.ERROR,
            ...     priority=MessagePriority.HIGH,
            ...     parse_mode="HTML"
            ... )
            True

            >>> # Send a message with inline buttons
            >>> await provider.send_notification(
            ...     "Choose an option:",
            ...     message_type=MessageType.INTERACTIVE,
            ...     buttons=[
            ...         {"text": "Yes", "callback_data": "yes"},
            ...         {"text": "No", "callback_data": "no"}
            ...     ]
            ... )
            True
        """
        async with self._message_lock:
            try:
                # Set message priority for rate limiting
                self._message_priority = priority

                # Create message data based on type
                message_data = self._format_message(
                    message, message_type, level, **kwargs
                )

                # Send API request with retries
                response = await self._send_api_request(
                    "sendMessage",
                    message_data,
                    retries=self._priority_retry_attempts.get(priority)
                )

                # Store message ID for editing
                if "message_id" in response:
                    self._last_message_id = response["message_id"]

                return True

            except Exception as err:
                error = self._handle_request_error(err, "sendMessage")
                await self._update_error_state(error)
                raise error from err

    def _handle_request_error(
        self,
        err: Exception,
        method: str
    ) -> TelegramError:
        """Handle request errors and create appropriate TelegramError.

        Wraps various network and API errors into a standardized TelegramError
        with additional context for debugging and error handling.

        Args:
            err (Exception): Original exception that occurred
            method (str): API method name that triggered the error

        Returns:
            TelegramError: Wrapped error with additional context

        Example:
            >>> try:
            ...     await session.post(url)
            ... except Exception as e:
            ...     error = provider._handle_request_error(e, "sendMessage")
            ...     logger.error(f"Request failed: {error}")
        """
        if isinstance(err, aiohttp.ClientError):
            return TelegramError(
                f"Client error: {err}",
                context={"endpoint": method, "error": str(err)}
            )
        elif isinstance(err, asyncio.TimeoutError):
            return TelegramError(
                f"Timeout error: {err}",
                context={"endpoint": method, "error": str(err)}
            )
        else:
            return TelegramError(
                f"Unknown error: {err}",
                context={"endpoint": method, "error": str(err)}
            )

    async def _update_error_state(self, error: TelegramError) -> None:
        """Update provider state after an error occurs."""
        async with self._state_lock:
            if isinstance(error, TelegramError):
                self._consecutive_errors += 1
            else:
                self._consecutive_errors = 0

            self._last_error_time = datetime.now()
            self._state.last_error = error

            if self._consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                self._state.disabled = True

    def validate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate provider configuration.

        Args:
            config (Dict[str, Any]): Provider configuration dictionary.

        Returns:
            Dict[str, Any]: Validated configuration dictionary.

        Raises:
            ValueError: If required configuration is missing or invalid.
        """
        # Implement configuration validation logic here
        # For now, just return the original configuration
        return config
