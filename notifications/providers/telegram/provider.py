# notifications/providers/telegram/provider.py

"""
Telegram bot notification provider implementation.
Handles sending notifications via Telegram Bot API with proper rate limiting and error handling.

Example:
    >>> from notifications.providers.telegram import TelegramProvider, TelegramConfig
    >>> config = TelegramConfig(
    ...     bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
    ...     chat_id="-1001234567890"
    ... )
    >>> provider = TelegramProvider(config.to_provider_config())
    >>> async with provider:
    ...     await provider.notify_progress(75.5, "1.2 GB", "2 hours", "15:30")
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, Dict, Final, Optional, Set, Union
from urllib.parse import urljoin

import aiohttp
from structlog import get_logger

from config.constants import MessagePriority, MessageType, NotificationLevel
from notifications.base import (
    NotificationError,
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
from notifications.providers.telegram.types import (
    SendMessageRequest,
    TelegramApiError,
)

logger = get_logger(__name__)

# Constants
MAX_CONSECUTIVE_ERRORS: Final[int] = 3
BACKOFF_BASE: Final[float] = 2.0

class TelegramError(NotificationError):
    """Raised when Telegram API request fails."""

    def __init__(
        self,
        message: str,
        code: Optional[int] = None,
        retry_after: Optional[int] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        """Initialize error with optional status code and retry delay.

        Args:
            message: Error description
            code: Optional HTTP status code
            retry_after: Optional retry delay in seconds
            context: Optional error context
        """
        super().__init__(message, code)
        self.retry_after = retry_after
        self.context = context or {}

class TelegramProvider(NotificationProvider):
    """Telegram bot notification provider implementation."""

    def __init__(self, config: Dict[str, Any]) -> None:
        """Initialize the Telegram notification provider.

        Args:
            config: Provider configuration dictionary.
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

        Args:
            method: API method name

        Returns:
            str: Complete API URL
        """
        return urljoin(f"{self.api_base_url}/bot{self.bot_token}/", method)

    async def __aenter__(self) -> "TelegramProvider":
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.disconnect()

    async def connect(self) -> None:
        """Initialize aiohttp session for API requests."""
        async with self._session_lock:
            if not self.session or self.session.closed:
                self.session = aiohttp.ClientSession(
                    timeout=aiohttp.ClientTimeout(total=30)
                )

    async def disconnect(self) -> None:
        """Close aiohttp session."""
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

        Args:
            response: API response
            data: Response data dictionary

        Returns:
            Optional[int]: Retry delay in seconds if rate limited
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

    async def _handle_api_response(
        self,
        response: aiohttp.ClientResponse,
        response_data: Dict[str, Any],
        method: str
    ) -> Dict[str, Any]:
        """Handle API response and update state accordingly.

        Args:
            response: API response object
            response_data: Parsed response data
            method: API method name

        Returns:
            Dict[str, Any]: Processed response data

        Raises:
            TelegramError: If API response indicates an error
        """
        # Handle successful response
        if response.status == 200 and response_data.get("ok"):
            # Reset error counter on success
            self._consecutive_errors = 0
            self._state.last_success = datetime.now()
            logger.debug(
                "Telegram API request successful",
                method=method,
                message_id=response_data.get("result", {}).get("message_id")
            )
            return response_data

        # Handle API errors
        error_msg = response_data.get("description", "Unknown error")
        raise TelegramError(
            f"Telegram API error: {error_msg}",
            code=response.status,
            context={
                "endpoint": method,
                "response": response_data
            }
        )

    def _handle_request_error(
        self,
        err: Exception,
        method: str
    ) -> TelegramError:
        """Handle request errors and create appropriate TelegramError.

        Args:
            err: Original exception
            method: API method name

        Returns:
            TelegramError: Wrapped error with context
        """
        if isinstance(err, asyncio.TimeoutError):
            error = TelegramError(
                "Request timed out",
                code=408,
                context={"endpoint": method}
            )
        elif isinstance(err, aiohttp.ClientError):
            error = TelegramError(
                f"Request failed: {err}",
                context={"endpoint": method}
            )
        else:
            error = TelegramError(
                "Maximum retries exceeded",
                context={"endpoint": method}
            )
        error.__cause__ = err
        return error

    async def _update_error_state(self, error: TelegramError) -> None:
        """Update provider state after an error.

        Args:
            error: The error that occurred
        """
        async with self._state_lock:
            self._consecutive_errors += 1
            self._last_error_time = datetime.now()
            self._state.last_error = error
            
            # Reset error count after successful operation
            if not isinstance(error, TelegramError):
                self._consecutive_errors = 0

    def _calculate_priority_delay(self, base_delay: float) -> float:
        """Calculate delay based on message priority.

        Args:
            base_delay: Base delay in seconds

        Returns:
            float: Priority-adjusted delay
        """
        priority_multiplier = 1.0
        if self._message_priority == MessagePriority.HIGH:
            priority_multiplier = 0.5  # Shorter delay for high priority
        elif self._message_priority == MessagePriority.LOW:
            priority_multiplier = 2.0  # Longer delay for low priority
        return base_delay * priority_multiplier

    async def _send_api_request(
        self,
        method: str,
        data: SendMessageRequest,
        retries: Optional[int] = None
    ) -> Dict[str, Any]:
        """Send request to Telegram API with retries.

        Args:
            method: API method name
            data: Request payload
            retries: Optional retry attempts override

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
            self._update_error_state(last_error or TelegramError(
                "Maximum retries exceeded",
                context={"endpoint": method}
            ))
            raise self._state.last_error

    async def send_notification(
        self,
        message: str,
        level: NotificationLevel = NotificationLevel.INFO,
        priority: MessagePriority = MessagePriority.NORMAL,
        message_type: MessageType = MessageType.CUSTOM,
        **kwargs
    ) -> bool:
        """Send notification via Telegram Bot API.

        Args:
            message: Message to send
            level: Notification priority level
            priority: Message priority level
            message_type: Type of message
            **kwargs: Additional message-specific arguments

        Returns:
            bool: True if notification was sent successfully

        Raises:
            TelegramError: If API request fails
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
                raise error

    def _create_typed_message(
        self,
        message: str,
        message_type: MessageType,
        level: NotificationLevel,
        **kwargs
    ) -> Dict[str, Any]:
        """Create appropriate message based on type.

        Args:
            message: Message content
            message_type: Type of message
            level: Notification level
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

    def _get_level_priority(self, level: NotificationLevel) -> MessagePriority:
        """Get message priority based on notification level.

        Args:
            level: Notification level

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
            percent: Progress percentage
            remaining: Remaining data amount
            elapsed: Elapsed time
            etc: Estimated time of completion
            description: Optional description

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
            stats: Optional transfer statistics to include

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
            error_message: Error description
            include_debug: Whether to include debug information
            debug_info: Optional debug information

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
            message_id: Optional message ID to edit
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
            message_id: Optional message ID to delete

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
            config: Provider configuration dictionary.

        Returns:
            Dict[str, Any]: Validated configuration dictionary.

        Raises:
            ValueError: If required configuration is missing or invalid.
        """
        # Implement configuration validation logic here
        # For now, just return the original configuration
        return config
