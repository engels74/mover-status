# notifications/providers/telegram/provider.py

"""Telegram bot notification provider implementation.

This module implements a Telegram Bot API-based notification provider with support
for various message types, rate limiting, and error handling. It provides a robust
interface for sending notifications through Telegram bots.

Features:
    - Message Types: text, progress updates, errors, warnings
    - Rate Limiting: Priority-based rate limits
    - Error Handling: Automatic retries with exponential backoff
    - Thread Safety: Async-safe operations with proper locking
    - Message Threading: Support for Telegram message threads
    - Content Protection: Optional message forwarding protection

Configuration:
    Required:
        - bot_token: Telegram bot API token
        - chat_id: Target chat/channel ID

    Optional:
        - thread_id: Message thread ID for forum topics
        - parse_mode: Message parsing mode (HTML/Markdown)
        - disable_notifications: Mute notifications
        - protect_content: Prevent message forwarding
        - timeout: Request timeout in seconds
        - rate_limit: Maximum requests per period
        - retry_attempts: Maximum retry attempts
        - retry_delay: Initial retry delay in seconds

Example:
    >>> from notifications.providers.telegram import TelegramProvider, TelegramConfig
    >>>
    >>> # Configure the provider
    >>> config = TelegramConfig(
    ...     bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
    ...     chat_id="-1001234567890",
    ...     thread_id=12345  # Optional forum topic
    ... )
    >>>
    >>> # Use with async context manager
    >>> async with TelegramProvider(config) as provider:
    ...     # Send various notifications
    ...     await provider.notify("System startup complete")
    ...     await provider.notify_progress(75.5, "1.2 GB", "2h", "15:30")
    ...     await provider.notify_error("Connection failed", error_code=404)

Note:
    This provider implements Telegram's rate limits and backoff requirements.
    For details, see: https://core.telegram.org/bots/api#making-requests
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, Dict, Final, List, Optional, Set, TypedDict, Union
from urllib.parse import urljoin

import aiohttp
from structlog import get_logger

from config.constants import MessagePriority, MessageType, NotificationLevel
from notifications.base import NotificationError, NotificationState
from notifications.providers.base import BaseNotificationProvider
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
from notifications.providers.telegram.types import (
    SendMessageRequest,
    TelegramApiError,
)
from shared.providers.telegram import (
    ALLOWED_DOMAINS,
    TelegramDomains,
    validate_url,
)

logger = get_logger(__name__)

# Constants
MAX_CONSECUTIVE_ERRORS: Final[int] = 3
BACKOFF_BASE: Final[float] = 2.0
DEFAULT_TIMEOUT: Final[float] = 10.0  # seconds

class TelegramError(NotificationError):
    """Raised when Telegram API request fails.

    This error class extends NotificationError to include Telegram-specific
    error information such as retry delays and error context.

    Args:
        message (str): Error description
        code (Optional[int]): HTTP status code
        retry_after (Optional[int]): Retry delay in seconds
        context (Optional[Dict[str, Any]]): Additional error context

    Example:
        >>> try:
        ...     await provider.send_message(...)
        ... except TelegramError as e:
        ...     if e.retry_after:
        ...         await asyncio.sleep(e.retry_after)
        ...     print(f"Error {e.code}: {e.message}")
    """

    def __init__(
        self,
        message: str,
        code: Optional[int] = None,
        retry_after: Optional[int] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        """Initialize error with optional status code and retry delay.

        Args:
            message (str): Error description
            code (Optional[int], optional): HTTP status code. Defaults to None
            retry_after (Optional[int], optional): Retry delay in seconds.
                Defaults to None
            context (Optional[Dict[str, Any]], optional): Additional error
                context. Defaults to None
        """
        super().__init__(message, code)
        self.retry_after = retry_after
        self.context = context or {}


class TelegramConfig(TypedDict, total=False):
    """Telegram provider configuration type.

    Configuration options for the Telegram notification provider.
    The 'total=False' flag indicates all fields are optional in TypedDict.

    Attributes:
        bot_token (str): Telegram bot API token
        chat_id (Union[int, str]): Target chat/channel ID
        thread_id (Optional[int]): Message thread ID for forum topics
    """
    bot_token: str
    chat_id: Union[int, str]
    thread_id: Optional[int]


class InlineKeyboardButton(TypedDict, total=False):
    """Telegram inline keyboard button type.

    Configuration for Telegram inline keyboard buttons.
    The 'total=False' flag indicates all fields are optional in TypedDict.

    Attributes:
        text (str): Button text
        url (Optional[str]): URL to open when button is pressed
        callback_data (Optional[str]): Data to send when button is pressed
    """
    text: str
    url: Optional[str]
    callback_data: Optional[str]


class TelegramProvider(BaseNotificationProvider):
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

    ALLOWED_DOMAINS: Final[TelegramDomains] = ALLOWED_DOMAINS

    def __init__(self, config: Dict[str, Any]) -> None:
        """Initialize the Telegram notification provider.

        Sets up the provider with the specified configuration, initializing
        priority-based rate limits, retry settings, and connection management.

        Args:
            config (Dict[str, Any]): Provider configuration containing:
                - bot_token: Telegram bot API token
                - chat_id: Target chat/channel ID
                - thread_id: Optional message thread ID
                - parse_mode: Message parsing mode (HTML/Markdown)
                - disable_notifications: Mute notifications
                - protect_content: Prevent message forwarding
                - timeout: Request timeout in seconds
                - rate_limit: Maximum requests per period
                - retry_attempts: Maximum retry attempts
                - retry_delay: Initial retry delay in seconds

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
        self._config = self.validate_config(config)

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
        self.chat_id: Union[int, str] = self._config["chat_id"]
        self.parse_mode: str = self._config["parse_mode"]
        self.disable_notifications: bool = self._config["disable_notifications"]
        self.protect_content: bool = self._config["protect_content"]
        self.message_thread_id: Optional[int] = self._config["message_thread_id"]
        self.api_base_url: str = self._config["api_base_url"]
        self.max_message_length: int = self._config["max_message_length"]

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

        # Session management
        self.session: Optional[aiohttp.ClientSession] = None
        self._last_message_id: Optional[int] = None
        self._message_priority: MessagePriority = MessagePriority.NORMAL
        self._state = NotificationState()
        self._consecutive_errors: int = 0
        self._last_error_time: Optional[datetime] = None
        self._tags: Set[str] = set(self._config.get("tags", []))

        # Thread safety
        self._session_lock = asyncio.Lock()
        self._state_lock = asyncio.Lock()
        self._message_lock = asyncio.Lock()

    def _build_api_url(self, method: str) -> str:
        """Build Telegram API URL for given method.

        Constructs a complete Telegram Bot API URL by combining the base URL,
        bot token, and method name.

        Args:
            method (str): API method name (e.g., "sendMessage", "editMessage")

        Returns:
            str: Complete API URL for the specified method

        Example:
            >>> provider._build_api_url("sendMessage")
            'https://api.telegram.org/bot123456:ABC-DEF/sendMessage'
        """
        return urljoin(f"{self.api_base_url}/bot{self.bot_token}/", method)

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
            if not self.session or self.session.closed:
                self.session = aiohttp.ClientSession(
                    timeout=aiohttp.ClientTimeout(total=self._timeout)
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
            if self.session and not self.session.closed:
                await self.session.close()
                self.session = None

    async def _handle_rate_limit(
        self,
        response: aiohttp.ClientResponse,
        data: Dict[str, Any]
    ) -> Optional[int]:
        """Handle Telegram rate limit response.

        Processes Telegram's rate limit response and extracts retry timing
        information. Updates the provider's rate limit state accordingly.

        Args:
            response (aiohttp.ClientResponse): API response to process
            data (Dict[str, Any]): Response data dictionary

        Returns:
            Optional[int]: Retry delay in seconds if rate limited, None otherwise

        Example:
            >>> async with session.post(url, json=data) as response:
            ...     retry_after = await provider._handle_rate_limit(response, data)
            ...     if retry_after:
            ...         await asyncio.sleep(retry_after)
        """
        if response.status == TelegramApiError.RATE_LIMIT:
            retry_after = int(data.get("parameters", {}).get("retry_after", 5))
            self._state.rate_limited = True
            self._state.rate_limit_until = datetime.now().timestamp() + retry_after
            logger.warning(
                "Telegram rate limit hit",
                retry_after=retry_after,
                endpoint=str(response.url),
                rate_limited_until=self._state.rate_limit_until
            )
            return retry_after
        return None

    async def _send_api_request(
        self,
        method: str,
        data: SendMessageRequest,
        retries: Optional[int] = None
    ) -> Dict[str, Any]:
        """Send request to Telegram API with retries.

        Args:
            method (str): API method name
            data (SendMessageRequest): Request payload
            retries (Optional[int]): Optional retry attempts override

        Returns:
            Dict[str, Any]: API response data

        Raises:
            TelegramError: If request fails after retries
        """
        if not self.session:
            await self.connect()

        if self._state.disabled:
            raise TelegramError(
                "Provider is disabled due to excessive errors",
                context={"last_error": str(self._state.last_error)}
            )

        url = self._build_api_url(method)
        max_retries = retries if retries is not None else self._priority_retry_attempts[self._message_priority]
        last_error = None

        for attempt in range(max_retries + 1):
            try:
                async with self.session.post(url, json=data) as response:
                    response_data = await response.json()

                    # Handle rate limiting
                    if retry_after := await self._handle_rate_limit(response, response_data):
                        if attempt < max_retries:
                            base_delay = retry_after * (BACKOFF_BASE ** attempt)
                            delay = self._calculate_priority_delay(base_delay)
                            await asyncio.sleep(delay)
                            continue
                        raise TelegramError(
                            "Rate limit exceeded",
                            code=TelegramApiError.RATE_LIMIT,
                            retry_after=retry_after,
                            context={"endpoint": method}
                        )

                    return await self._handle_api_response(response, response_data, method)

            except (asyncio.TimeoutError, aiohttp.ClientError) as err:
                last_error = self._handle_request_error(err, method)

            if attempt < max_retries:
                base_delay = self._retry_delay * (BACKOFF_BASE ** attempt)
                delay = self._calculate_priority_delay(base_delay)
                await asyncio.sleep(delay)
                continue

            # Update error state and raise
            last_error = TelegramError(
                "Maximum retries exceeded",
                context={"endpoint": method}
            )
            await self._update_error_state(last_error)
            raise last_error

    async def _handle_api_response(
        self,
        response: aiohttp.ClientResponse,
        response_data: Dict[str, Any],
        method: str
    ) -> Dict[str, Any]:
        """Handle API response and update provider state.

        Processes the API response, updates internal state tracking, and handles
        both successful and error responses appropriately.

        Args:
            response (aiohttp.ClientResponse): Raw API response object
            response_data (Dict[str, Any]): Parsed response data
            method (str): API method name that generated this response

        Returns:
            Dict[str, Any]: Processed response data on success

        Raises:
            TelegramError: If API response indicates an error or validation fails

        Example:
            >>> async with session.post(url, json=data) as response:
            ...     data = await response.json()
            ...     result = await provider._handle_api_response(
            ...         response, data, "sendMessage"
            ...     )
            ...     message_id = result["result"]["message_id"]
        """
        if response.status != 200:
            raise TelegramError(
                f"API request failed with status {response.status}",
                code=response.status,
                context={"endpoint": method, "response": response_data}
            )

        if "error_code" in response_data:
            raise TelegramError(
                f"API request failed with error code {response_data['error_code']}",
                code=response_data["error_code"],
                context={"endpoint": method, "response": response_data}
            )

        return response_data

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
        """Update provider state after an error occurs.

        Updates internal error tracking state including consecutive error count,
        last error time, and error details. This information is used for
        backoff and retry logic.

        Args:
            error (TelegramError): The error that occurred

        Thread Safety:
            This method is protected by _state_lock for thread safety

        Note:
            - Consecutive error count is incremented for TelegramErrors
            - Non-TelegramErrors reset the consecutive error count
            - Last error time and details are always updated
        """
        async with self._state_lock:
            if isinstance(error, TelegramError):
                self._consecutive_errors += 1
            else:
                self._consecutive_errors = 0

            self._last_error_time = datetime.now()
            self._state.last_error = error

            if self._consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                self._state.disabled = True

    def _calculate_priority_delay(self, base_delay: float) -> float:
        """Calculate delay based on message priority level.

        Adjusts the base delay time according to the current message priority:
        - High priority: 50% of base delay
        - Normal priority: Base delay unchanged
        - Low priority: 200% of base delay

        Args:
            base_delay (float): Base delay time in seconds

        Returns:
            float: Priority-adjusted delay time in seconds

        Example:
            >>> delay = provider._calculate_priority_delay(5.0)
            >>> # Returns 2.5 for high priority
            >>> # Returns 5.0 for normal priority
            >>> # Returns 10.0 for low priority
        """
        if self._message_priority == MessagePriority.HIGH:
            return base_delay * 0.5
        elif self._message_priority == MessagePriority.LOW:
            return base_delay * 2.0
        else:
            return base_delay

    async def send_notification(
        self,
        message: str,
        level: NotificationLevel = NotificationLevel.INFO,
        priority: MessagePriority = MessagePriority.NORMAL,
        message_type: MessageType = MessageType.TEXT,
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
                formatting (default: TEXT)
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
            ...     message_type=MessageType.INLINE_KEYBOARD,
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
                message_data = await self._create_typed_message(
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

    def _create_typed_message(
        self,
        message: str,
        message_type: MessageType,
        level: NotificationLevel,
        **kwargs
    ) -> Dict[str, Any]:
        """Create appropriate message based on type.

        Args:
            message (str): Message content
            message_type (MessageType): Type of message
            level (NotificationLevel): Notification level
            **kwargs: Additional message-specific arguments

        Returns:
            Dict[str, Any]: Formatted message data for Telegram API
        """
        if message_type == MessageType.PROGRESS:
            formatted_message = create_progress_message(
                percent=kwargs.get("percent", 0),
                remaining=kwargs.get("remaining", "Unknown"),
                elapsed=kwargs.get("elapsed", "Unknown"),
                etc=kwargs.get("etc", "Unknown"),
                description=message
            )
            return {"text": formatted_message}

        elif message_type == MessageType.COMPLETION:
            formatted_message = create_completion_message(
                description=message,
                stats=kwargs.get("stats")
            )
            return {"text": formatted_message}

        elif message_type == MessageType.ERROR:
            formatted_message = create_error_message(
                error_message=message,
                error_code=kwargs.get("error_code"),
                error_details=kwargs.get("error_details")
            )
            return {"text": formatted_message}

        elif message_type == MessageType.WARNING:
            formatted_message = create_warning_message(
                warning_message=message,
                warning_details=kwargs.get("warning_details"),
                suggestion=kwargs.get("suggestion")
            )
            return {"text": formatted_message}

        elif message_type == MessageType.SYSTEM:
            formatted_message = create_system_message(
                status=message,
                metrics=kwargs.get("metrics"),
                issues=kwargs.get("issues")
            )
            return {"text": formatted_message}

        elif message_type == MessageType.BATCH:
            formatted_message = create_batch_message(
                operation=kwargs.get("operation", "Operation"),
                items=kwargs.get("items", []),
                summary=message
            )
            return {"text": formatted_message}

        elif message_type == MessageType.INTERACTIVE:
            formatted_message, keyboard = create_interactive_message(
                title=kwargs.get("title", "Interactive Message"),
                description=message,
                actions=kwargs.get("actions", []),
                expires_in=kwargs.get("expires_in")
            )
            keyboard = self.prepare_inline_keyboard(keyboard)
            return {
                "text": formatted_message,
                "reply_markup": keyboard if keyboard else None
            }

        elif message_type == MessageType.DEBUG:
            formatted_message = create_debug_message(
                message=message,
                context=kwargs.get("context"),
                stack_trace=kwargs.get("stack_trace")
            )
            return {"text": formatted_message}

        # Default to custom message type
        return {
            "text": message,
            "parse_mode": self.parse_mode,
            "disable_notification": level == NotificationLevel.DEBUG
        }

    def prepare_inline_keyboard(self, buttons: List[InlineKeyboardButton]) -> Dict[str, List[List[Dict[str, str]]]]:
        """Prepare inline keyboard markup.

        Args:
            buttons (List[InlineKeyboardButton]): List of button configurations

        Returns:
            Dict: Prepared inline keyboard markup

        Raises:
            ValueError: If button URL is invalid
        """
        keyboard = []
        row = []

        for button in buttons:
            if "url" in button and not self.validate_button_url(button["url"]):
                raise ValueError(f"Invalid button URL domain: {button['url']}")
            row.append(button)
            if len(row) == 2:  # Max 2 buttons per row
                keyboard.append(row)
                row = []

        if row:  # Add remaining buttons
            keyboard.append(row)

        return {"inline_keyboard": keyboard}

    def validate_button_url(self, url: Optional[str]) -> bool:
        """Validate button URL domain.

        Args:
            url (Optional[str]): URL to validate

        Returns:
            bool: True if URL is valid or None
        """
        if not url:
            return True
        try:
            return validate_url(url, ALLOWED_DOMAINS)
        except Exception:
            return False

    def _get_level_priority(self, level: NotificationLevel) -> MessagePriority:
        """Get message priority based on notification level.

        Args:
            level (NotificationLevel): Notification level

        Returns:
            MessagePriority: Corresponding priority level
        """
        return {
            NotificationLevel.DEBUG: MessagePriority.LOW,
            NotificationLevel.INFO: MessagePriority.NORMAL,
            NotificationLevel.WARNING: MessagePriority.NORMAL,
            NotificationLevel.ERROR: MessagePriority.HIGH,
            NotificationLevel.CRITICAL: MessagePriority.HIGH,
            NotificationLevel.INFO_SUCCESS: MessagePriority.NORMAL,
            NotificationLevel.INFO_FAILURE: MessagePriority.NORMAL,
            NotificationLevel.INFO_PROGRESS: MessagePriority.NORMAL,
            NotificationLevel.INFO_COMPLETE: MessagePriority.NORMAL,
            NotificationLevel.INFO_BATCH: MessagePriority.NORMAL,
            NotificationLevel.INFO_INTERACTIVE: MessagePriority.NORMAL,
        }.get(level, MessagePriority.NORMAL)

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
            TelegramError: If notification fails
        """
        try:
            message_data = create_progress_message(
                percent=percent,
                remaining=remaining,
                elapsed=elapsed,
                etc=etc,
                parse_mode=self.parse_mode,
                description=description,
            )
            if self._last_message_id:
                try:
                    return await self.edit_message(
                        message_id=self._last_message_id,
                        text=message_data["text"]
                    )
                except TelegramError as err:
                    if err.code != 400:  # Only retry with new message if not a bad request
                        raise
            return await self.send_notification(message_data["text"], message_type=MessageType.PROGRESS)
        except Exception as err:
            raise TelegramError(
                f"Failed to send progress update: {err}",
                context={
                    "percent": percent,
                    "remaining": remaining,
                    "elapsed": elapsed,
                    "etc": etc
                }
            ) from err

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
            TelegramError: If notification fails
        """
        try:
            message_data = create_completion_message(
                parse_mode=self.parse_mode,
                include_stats=bool(stats),
                stats=stats
            )
            self._message_priority = MessagePriority.HIGH
            return await self.send_notification(message_data["text"], message_type=MessageType.COMPLETION)
        except Exception as err:
            raise TelegramError(
                f"Failed to send completion notification: {err}",
                context={"stats": stats}
            ) from err
        finally:
            self._message_priority = MessagePriority.NORMAL

    async def notify_error(
        self,
        error_message: str,
        include_debug: bool = False,
        debug_info: Optional[Dict[str, str]] = None
    ) -> bool:
        """Send error notification.

        Args:
            error_message (str): Error description
            include_debug (bool): Whether to include debug information
            debug_info (Optional[Dict[str, str]]): Optional debug information

        Returns:
            bool: True if notification was sent successfully

        Raises:
            TelegramError: If notification fails
        """
        try:
            message_data = create_error_message(
                error_message,
                parse_mode=self.parse_mode,
                include_debug=include_debug,
                debug_info=debug_info,
                priority=MessagePriority.HIGH
            )
            self._message_priority = MessagePriority.HIGH
            return await self.send_notification(message_data["text"], message_type=MessageType.ERROR)
        except Exception as err:
            raise TelegramError(
                f"Failed to send error notification: {err}",
                context={
                    "error_message": error_message,
                    "debug_info": debug_info
                }
            ) from err
        finally:
            self._message_priority = MessagePriority.NORMAL

    async def edit_message(
        self,
        message_id: Optional[int] = None,
        **message_data: Any
    ) -> bool:
        """Edit previous message.

        Args:
            message_id (Optional[int]): Optional message ID to edit
            **message_data: New message data

        Returns:
            bool: True if message was edited successfully

        Raises:
            TelegramError: If editing fails
        """
        if not message_id and not self._last_message_id:
            raise TelegramError(
                "No message ID available for editing",
                context={"last_message_id": self._last_message_id}
            )

        edit_data = {
            "chat_id": self.chat_id,
            "message_id": message_id or self._last_message_id,
            **message_data
        }

        try:
            await self._send_api_request("editMessageText", edit_data)
            return True
        except TelegramError as err:
            if err.code == 400 and "message is not modified" in str(err):
                # Not an error if content hasn't changed
                return True
            raise TelegramError(
                f"Failed to edit message: {err}",
                code=err.code,
                context={
                    "message_id": message_id or self._last_message_id,
                    "chat_id": self.chat_id
                }
            ) from err

    async def delete_message(
        self,
        message_id: Optional[int] = None
    ) -> bool:
        """Delete a message.

        Args:
            message_id (Optional[int]): Optional message ID to delete

        Returns:
            bool: True if message was deleted successfully

        Raises:
            TelegramError: If deletion fails
        """
        if not message_id and not self._last_message_id:
            raise TelegramError(
                "No message ID available for deletion",
                context={"last_message_id": self._last_message_id}
            )

        delete_data = {
            "chat_id": self.chat_id,
            "message_id": message_id or self._last_message_id
        }

        try:
            await self._send_api_request("deleteMessage", delete_data)
            return True
        except TelegramError as err:
            if err.code == 400 and "message to delete not found" in str(err):
                # Not an error if message is already deleted
                return True
            raise TelegramError(
                f"Failed to delete message: {err}",
                code=err.code,
                context={
                    "message_id": message_id or self._last_message_id,
                    "chat_id": self.chat_id
                }
            ) from err

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

    def _create_message(
        self,
        message: str,
        message_type: MessageType = MessageType.TEXT,
        level: NotificationLevel = NotificationLevel.INFO,
        **kwargs: Any
    ) -> SendMessageRequest:
        """Create a formatted message request based on type and level.

        Constructs a SendMessageRequest object with appropriate formatting
        and parameters based on the message type and notification level.

        Args:
            message (str): Raw message content to format
            message_type (MessageType): Type of message to create
                - TEXT: Plain text message
                - HTML: Message with HTML formatting
                - MARKDOWN: Message with Markdown formatting
                - INLINE_KEYBOARD: Message with inline buttons
                - PHOTO: Message with photo attachment
                - VIDEO: Message with video attachment
                - DOCUMENT: Message with document attachment
            level (NotificationLevel): Notification severity level
                - DEBUG: Technical details (🔧)
                - INFO: General information (ℹ️)
                - WARNING: Important notices (⚠️)
                - ERROR: Critical issues (❌)
            **kwargs: Additional message-specific arguments:
                - parse_mode: Override default parse mode
                - disable_web_preview: Disable link previews
                - reply_to_message_id: Message to reply to
                - buttons: List of inline keyboard buttons
                - photo_url: URL for photo messages
                - video_url: URL for video messages
                - document_url: URL for document messages

        Returns:
            SendMessageRequest: Formatted message request ready to send

        Raises:
            ValueError: If message type is invalid or required args missing

        Example:
            >>> # Create a simple text message
            >>> request = provider._create_message("Hello!")
            >>> assert request.text == "ℹ️ Hello!"

            >>> # Create an HTML message with buttons
            >>> request = provider._create_message(
            ...     "<b>Choose:</b>",
            ...     message_type=MessageType.INLINE_KEYBOARD,
            ...     buttons=[{"text": "OK", "callback_data": "ok"}]
            ... )
            >>> assert request.parse_mode == "HTML"
            >>> assert "reply_markup" in request.dict()
        """
        pass

    def _prepare_inline_keyboard(
        self,
        buttons: List[InlineKeyboardButton]
    ) -> Dict[str, List[List[Dict[str, str]]]]:
        """Prepare inline keyboard markup for message.

        Formats a list of button configurations into the structure required
        by Telegram's Bot API for inline keyboards.

        Args:
            buttons (List[InlineKeyboardButton]): List of button configs:
                - text: Button label text
                - url: Optional URL to open
                - callback_data: Optional callback data
                - switch_inline_query: Optional inline query
                - switch_inline_query_current_chat: Optional current chat query

        Returns:
            Dict[str, List[List[Dict[str, str]]]]: Telegram keyboard markup

        Raises:
            ValueError: If button config is invalid or URLs are malformed

        Example:
            >>> markup = provider._prepare_inline_keyboard([
            ...     {"text": "Visit", "url": "https://example.com"},
            ...     {"text": "OK", "callback_data": "confirm"}
            ... ])
            >>> assert "inline_keyboard" in markup
            >>> assert len(markup["inline_keyboard"]) == 1
        """
        pass

    def _validate_button_url(self, url: Optional[str]) -> bool:
        """Validate button URL domain for security.

        Checks if the provided URL is either None or points to an allowed
        domain to prevent malicious URLs in buttons.

        Args:
            url (Optional[str]): URL to validate or None

        Returns:
            bool: True if URL is valid or None

        Example:
            >>> assert provider._validate_button_url(None)
            >>> assert provider._validate_button_url("https://telegram.org")
            >>> assert not provider._validate_button_url("javascript:alert(1)")
        """
        pass
