# notifications/telegram/provider.py

"""
Telegram bot notification provider implementation.
Handles sending notifications via Telegram Bot API with proper rate limiting and error handling.

Example:
    >>> from notifications.telegram.provider import TelegramProvider
    >>> provider = TelegramProvider({
    ...     "bot_token": "YOUR_BOT_TOKEN",
    ...     "chat_id": "YOUR_CHAT_ID"
    ... })
    >>> await provider.notify_progress(75.5, "1.2 GB", "2 hours", "15:30")
"""

import asyncio
from typing import Dict, Optional, Union
from urllib.parse import urljoin

import aiohttp
from structlog import get_logger

from notifications.base import NotificationError, NotificationProvider
from notifications.telegram.templates import (
    create_completion_message,
    create_error_message,
    create_progress_message,
)
from notifications.telegram.types import (
    RATE_LIMIT,
    ParseMode,
    SendMessageRequest,
)

logger = get_logger(__name__)


class TelegramError(NotificationError):
    """Raised when Telegram API request fails."""

    def __init__(self, message: str, code: Optional[int] = None):
        """Initialize error with optional status code.

        Args:
            message: Error description
            code: Optional HTTP status code
        """
        super().__init__(message)
        self.code = code


class TelegramProvider(NotificationProvider):
    """Telegram bot notification provider implementation."""

    def __init__(self, config: Dict[str, Union[str, dict]]):
        """Initialize Telegram provider.

        Args:
            config: Provider configuration containing bot_token and chat_id

        Raises:
            ValueError: If required configuration is missing
        """
        super().__init__(
            rate_limit=RATE_LIMIT["rate_limit"],
            rate_period=RATE_LIMIT["rate_period"],
            retry_attempts=RATE_LIMIT["max_retries"],
            retry_delay=RATE_LIMIT["retry_delay"],
        )
        # Extract required configuration
        self.bot_token = self._get_config_value(config, "bot_token")
        self.chat_id = self._get_config_value(config, "chat_id")

        # Extract optional configuration
        rate_limit = config.get("rate_limit", {})
        if isinstance(rate_limit, dict):
            self._rate_limit = rate_limit.get("limit", RATE_LIMIT["rate_limit"])
            self._rate_period = rate_limit.get("period", RATE_LIMIT["rate_period"])
            self._retry_attempts = rate_limit.get("retry_attempts", RATE_LIMIT["max_retries"])
            self._retry_delay = rate_limit.get("retry_delay", RATE_LIMIT["retry_delay"])

        self.parse_mode = config.get("parse_mode", ParseMode.HTML)
        self.disable_notifications = config.get("disable_notifications", False)
        self.protect_content = config.get("protect_content", False)
        self.message_thread_id = config.get("message_thread_id")
        self.api_base_url = config.get("api_base_url", "https://api.telegram.org").rstrip("/")

        self.session: Optional[aiohttp.ClientSession] = None
        self._last_message_id: Optional[int] = None

    def _get_config_value(self, config: Dict, key: str) -> str:
        """Get required configuration value.

        Args:
            config: Configuration dictionary
            key: Configuration key

        Returns:
            str: Configuration value

        Raises:
            ValueError: If value is missing or empty
        """
        value = config.get(key)
        if not value:
            raise ValueError(f"Missing required configuration: {key}")
        return str(value)

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
            self.session = aiohttp.ClientSession()

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

    async def _send_api_request(
        self,
        method: str,
        data: SendMessageRequest,
    ) -> Dict:
        """Send request to Telegram API.

        Args:
            method: API method name
            data: Request payload

        Returns:
            Dict: API response data

        Raises:
            TelegramError: If request fails
        """
        if not self.session:
            await self.connect()

        url = self._build_api_url(method)

        try:
            async with self.session.post(url, json=data, timeout=30) as response:
                response_data = await response.json()

                if response.status == 200 and response_data.get("ok"):
                    logger.debug(
                        "Telegram API request successful",
                        method=method,
                        message_id=response_data.get("result", {}).get("message_id")
                    )
                    return response_data

                error_msg = response_data.get("description", "Unknown error")
                raise TelegramError(
                    f"Telegram API error: {error_msg}",
                    code=response.status
                )

        except asyncio.TimeoutError as err:
            raise TelegramError("Telegram API request timed out") from err
        except aiohttp.ClientError as err:
            raise TelegramError(f"Telegram API request failed: {err}") from err

    async def send_notification(self, message: str) -> bool:
        """Send notification via Telegram Bot API.

        Args:
            message: Message to send

        Returns:
            bool: True if notification was sent successfully

        Raises:
            TelegramError: If API request fails
        """
        data: SendMessageRequest = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": self.parse_mode,
            "disable_notification": self.disable_notifications,
            "protect_content": self.protect_content,
        }

        if self.message_thread_id:
            data["message_thread_id"] = self.message_thread_id

        try:
            response = await self._send_api_request("sendMessage", data)
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
        description: Optional[str] = None,
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
        message_data = create_progress_message(
            percent=percent,
            remaining=remaining,
            elapsed=elapsed,
            etc=etc,
            parse_mode=self.parse_mode,
            description=description,
        )
        return await self.send_notification(message_data["text"])

    async def notify_completion(self) -> bool:
        """Send completion notification.

        Returns:
            bool: True if notification was sent successfully
        """
        message_data = create_completion_message(parse_mode=self.parse_mode)
        return await self.send_notification(message_data["text"])

    async def notify_error(self, error_message: str) -> bool:
        """Send error notification.

        Args:
            error_message: Error description

        Returns:
            bool: True if notification was sent successfully
        """
        message_data = create_error_message(
            error_message,
            parse_mode=self.parse_mode
        )
        return await self.send_notification(message_data["text"])

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
            message_id: Optional message ID to delete

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
                # Message already deleted
                return True
            raise
