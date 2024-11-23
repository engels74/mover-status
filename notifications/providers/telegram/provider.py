# notifications/providers/telegram/provider.py

"""
Telegram bot notification provider implementation.
Handles sending notifications via Telegram Bot API with proper rate limiting and error handling.

Example:
    >>> from notifications.telegram.provider import TelegramProvider
    >>> provider = TelegramProvider({
    ...     "bot_token": "YOUR_BOT_TOKEN",
    ...     "chat_id": "YOUR_CHAT_ID",
    ...     "parse_mode": "HTML"
    ... })
    >>> async with provider:
    ...     await provider.notify_progress(75.5, "1.2 GB", "2 hours", "15:30")
"""

import asyncio
from typing import Any, Dict, Optional, Union
from urllib.parse import urljoin

import aiohttp
from structlog import get_logger

from notifications.base import NotificationError, NotificationProvider
from notifications.providers.telegram.templates import (
    create_completion_message,
    create_error_message,
    create_progress_message,
)
from notifications.providers.telegram.types import (
    RATE_LIMIT,
    ChatType,
    MessageLimit,
    MessagePriority,
    ParseMode,
    SendMessageRequest,
)
from shared.types.telegram import validate_message_length

logger = get_logger(__name__)


class TelegramError(NotificationError):
    """Raised when Telegram API request fails."""

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


class TelegramProvider(NotificationProvider):
    """Telegram bot notification provider implementation."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize Telegram provider.

        Args:
            config: Provider configuration containing bot token and chat ID

        Raises:
            ValueError: If required configuration is missing or invalid
        """
        # Initialize rate limiting from config or defaults
        rate_limit_config = config.get("rate_limit", {})
        super().__init__(
            rate_limit=rate_limit_config.get("limit", RATE_LIMIT["rate_limit"]),
            rate_period=rate_limit_config.get("period", RATE_LIMIT["rate_period"]),
            retry_attempts=rate_limit_config.get("retry_attempts", RATE_LIMIT["max_retries"]),
            retry_delay=rate_limit_config.get("retry_delay", RATE_LIMIT["retry_delay"]),
        )

        # Required configuration
        self.bot_token = self._validate_config_str(config, "bot_token", "Bot token")
        self.chat_id = self._validate_chat_id(config.get("chat_id"))

        # Optional configuration
        self.parse_mode = ParseMode(config.get("parse_mode", ParseMode.HTML))
        self.disable_notifications = bool(config.get("disable_notifications", False))
        self.protect_content = bool(config.get("protect_content", False))
        self.message_thread_id = config.get("message_thread_id")
        self.chat_type = ChatType(config["chat_type"]) if "chat_type" in config else None
        self.api_base_url = self._validate_api_url(
            config.get("api_base_url", "https://api.telegram.org")
        )
        self.max_message_length = min(
            int(config.get("max_message_length", MessageLimit.MESSAGE_TEXT)),
            MessageLimit.MESSAGE_TEXT
        )

        # Session management
        self.session: Optional[aiohttp.ClientSession] = None
        self._last_message_id: Optional[int] = None
        self._message_priority = MessagePriority(
            config.get("message_priority", MessagePriority.NORMAL)
        )

    def _validate_config_str(
        self,
        config: Dict[str, Any],
        key: str,
        display_name: str
    ) -> str:
        """Validate required string configuration value.

        Args:
            config: Configuration dictionary
            key: Configuration key
            display_name: Human-readable name for error messages

        Returns:
            str: Validated configuration value

        Raises:
            ValueError: If value is missing or invalid
        """
        value = config.get(key)
        if not value or not isinstance(value, str):
            raise ValueError(f"{display_name} must be a non-empty string")
        return value.strip()

    def _validate_chat_id(self, chat_id: Optional[Union[int, str]]) -> str:
        """Validate Telegram chat ID.

        Args:
            chat_id: Chat ID to validate

        Returns:
            str: Validated chat ID

        Raises:
            ValueError: If chat ID is invalid
        """
        if not chat_id:
            raise ValueError("Chat ID is required")

        chat_id_str = str(chat_id)

        # Channel username format: @channel_name
        if chat_id_str.startswith("@"):
            if len(chat_id_str) < 2 or not chat_id_str[1:].replace("_", "").isalnum():
                raise ValueError("Invalid channel username format")
            return chat_id_str

        # Group/supergroup format: -100{9,10 digits}
        if chat_id_str.startswith("-100"):
            remaining = chat_id_str[4:]
            if not remaining.isdigit() or len(remaining) not in (9, 10):
                raise ValueError("Invalid group/supergroup ID format")
            return chat_id_str

        # Private chat or basic group format
        if chat_id_str.replace("-", "").isdigit():
            return chat_id_str

        raise ValueError(
            "Invalid chat ID format. Must be a channel username starting with '@', "
            "a group ID starting with '-100', or a numeric chat ID"
        )

    def _validate_api_url(self, url: str) -> str:
        """Validate and normalize Telegram API URL.

        Args:
            url: API URL to validate

        Returns:
            str: Normalized API URL

        Raises:
            ValueError: If URL is invalid
        """
        if not url:
            raise ValueError("API URL is required")

        url = url.rstrip("/")
        if not url.startswith(("http://", "https://")):
            raise ValueError("API URL must start with http:// or https://")

        if "api.telegram.org" not in url:
            raise ValueError("API URL must be from api.telegram.org domain")

        return url

    async def __aenter__(self) -> "TelegramProvider":
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.disconnect()

    async def connect(self) -> None:
        """Initialize aiohttp session for API requests."""
        if not self.session or self.session.closed:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30)
            )

    async def disconnect(self) -> None:
        """Close aiohttp session."""
        if self.session and not self.session.closed:
            await self.session.close()
            self.session = None

    def _build_api_url(self, method: str) -> str:
        """Build Telegram API URL for given method.

        Args:
            method: API method name

        Returns:
            str: Complete API URL
        """
        return urljoin(f"{self.api_base_url}/bot{self.bot_token}/", method)

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
        if response.status == 429:  # Rate limited
            retry_after = int(data.get("parameters", {}).get("retry_after", 5))
            logger.warning(
                "Telegram rate limit hit",
                retry_after=retry_after,
                endpoint=str(response.url)
            )
            return retry_after
        return None

    async def _send_api_request(
        self,
        method: str,
        data: SendMessageRequest,
        retries: int = 3
    ) -> Dict[str, Any]:
        """Send request to Telegram API with retries.

        Args:
            method: API method name
            data: Request payload
            retries: Number of retry attempts

        Returns:
            Dict[str, Any]: API response data

        Raises:
            TelegramError: If request fails after retries
        """
        if not self.session:
            await self.connect()

        url = self._build_api_url(method)
        last_error = None

        for attempt in range(retries + 1):
            try:
                async with self.session.post(url, json=data) as response:
                    response_data = await response.json()

                    # Handle rate limiting
                    if retry_after := await self._handle_rate_limit(response, response_data):
                        if attempt < retries:
                            await asyncio.sleep(retry_after)
                            continue
                        raise TelegramError(
                            "Rate limit exceeded",
                            code=429,
                            retry_after=retry_after
                        )

                    # Handle successful response
                    if response.status == 200 and response_data.get("ok"):
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
                        code=response.status
                    )

            except asyncio.TimeoutError as err:
                last_error = TelegramError("Telegram API request timed out")
                last_error.__cause__ = err
            except aiohttp.ClientError as err:
                last_error = TelegramError(f"Telegram API request failed: {err}")
                last_error.__cause__ = err

            if attempt < retries:
                await asyncio.sleep(self._retry_delay * (attempt + 1))
                continue

        raise last_error or TelegramError("Maximum retries exceeded")

    def _prepare_message_request(
        self,
        text: str,
        message_thread_id: Optional[int] = None
    ) -> SendMessageRequest:
        """Prepare message request data.

        Args:
            text: Message text
            message_thread_id: Optional thread ID

        Returns:
            SendMessageRequest: Prepared request data

        Raises:
            ValueError: If message is too long
        """
        # Validate message length
        validate_message_length(text, self.max_message_length)

        # Prepare base request
        request: SendMessageRequest = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": self.parse_mode,
            "disable_notification": (
                self.disable_notifications or
                self._message_priority == MessagePriority.SILENT
            ),
            "protect_content": self.protect_content
        }

        # Add thread ID if provided or configured
        thread_id = message_thread_id or self.message_thread_id
        if thread_id:
            request["message_thread_id"] = thread_id

        return request

    async def send_notification(self, message: str) -> bool:
        """Send notification via Telegram Bot API.

        Args:
            message: Message to send

        Returns:
            bool: True if notification was sent successfully

        Raises:
            TelegramError: If API request fails
        """
        try:
            request = self._prepare_message_request(message)
            response = await self._send_api_request("sendMessage", request)
            self._last_message_id = response.get("result", {}).get("message_id")
            return True
        except TelegramError:
            raise
        except Exception as err:
            raise TelegramError(f"Failed to send notification: {err}") from err

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
            message_data = create_progress_message(
                percent=percent,
                remaining=remaining,
                elapsed=elapsed,
                etc=etc,
                parse_mode=self.parse_mode,
                description=description,
            )
            return await self.send_notification(message_data["text"])
        except TelegramError:
            raise
        except Exception as err:
            raise TelegramError(f"Failed to send progress update: {err}") from err

    async def notify_completion(self) -> bool:
        """Send completion notification.

        Returns:
            bool: True if notification was sent successfully
        """
        try:
            message_data = create_completion_message(parse_mode=self.parse_mode)
            return await self.send_notification(message_data["text"])
        except TelegramError:
            raise
        except Exception as err:
            raise TelegramError(f"Failed to send completion notification: {err}") from err

    async def notify_error(self, error_message: str) -> bool:
        """Send error notification.

        Args:
            error_message: Error description

        Returns:
            bool: True if notification was sent successfully
        """
        try:
            message_data = create_error_message(
                error_message,
                parse_mode=self.parse_mode
            )
            return await self.send_notification(message_data["text"])
        except TelegramError:
            raise
        except Exception as err:
            raise TelegramError(f"Failed to send error notification: {err}") from err

    async def edit_message(
        self,
        message_id: Optional[int] = None,
        **message_data
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
            raise TelegramError("No message ID available for editing")

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
                # Message content hasn't changed, not an error
                return True
            raise

    async def delete_message(
        self,
        message_id: Optional[int] = None
    ) -> bool:
        """Delete a message.

        Args:
            message_id: Optional message ID to delete. Uses last sent message ID if not provided.

        Returns:
            bool: True if message was deleted successfully

        Raises:
            TelegramError: If deletion fails
        """
        if not message_id and not self._last_message_id:
            raise TelegramError("No message ID available for deletion")

        delete_data = {
            "chat_id": self.chat_id,
            "message_id": message_id or self._last_message_id
        }

        try:
            await self._send_api_request("deleteMessage", delete_data)
            return True
        except TelegramError as err:
            if err.code == 400 and "message to delete not found" in str(err):
                # Message already deleted or not found
                return True
            raise
