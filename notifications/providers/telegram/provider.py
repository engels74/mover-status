# notifications/providers/telegram/provider.py

"""
Telegram bot notification provider implementation.
Handles sending notifications via Telegram Bot API with proper rate limiting and error handling.

Example:
    >>> from notifications.providers.telegram import TelegramProvider
    >>> provider = TelegramProvider({
    ...     "bot_token": "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
    ...     "chat_id": "-1001234567890"
    ... })
    >>> async with provider:
    ...     await provider.notify_progress(75.5, "1.2 GB", "2 hours", "15:30")
"""

import asyncio
import re
from typing import Any, Dict, Optional, Union
from urllib.parse import urljoin, urlparse

import aiohttp
from structlog import get_logger

from notifications.base import NotificationError, NotificationProvider
from notifications.providers.telegram.schemas import BotConfigSchema
from notifications.providers.telegram.templates import (
    create_completion_message,
    create_error_message,
    create_progress_message,
)
from notifications.providers.telegram.types import (
    RATE_LIMIT,
    MessageLimit,
    MessagePriority,
    ParseMode,
    SendMessageRequest,
    validate_message_length,
)

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

    @classmethod
    def _validate_bot_token(cls, token: str) -> None:
        """Validate Telegram bot token format.

        Args:
            token: Bot token to validate

        Raises:
            ValueError: If token format is invalid
        """
        if not token:
            raise ValueError("Bot token is required")

        # Token format: <bot_id>:<token>
        parts = token.split(":")
        if len(parts) != 2:
            raise ValueError("Invalid bot token format: missing separator")

        bot_id, token_part = parts

        if not bot_id.isdigit():
            raise ValueError("Invalid bot token format: invalid bot ID")

        if not re.match(r"^[A-Za-z0-9_-]{30,}$", token_part):
            raise ValueError("Invalid bot token format: invalid token")

    @classmethod
    def _validate_chat_id(cls, chat_id: Union[int, str]) -> None:
        """Validate Telegram chat ID format.

        Args:
            chat_id: Chat ID to validate

        Raises:
            ValueError: If chat ID format is invalid
        """
        if not chat_id:
            raise ValueError("Chat ID is required")

        if isinstance(chat_id, int):
            return

        chat_id_str = str(chat_id)

        # Channel username format: @channel_name
        if chat_id_str.startswith("@"):
            if len(chat_id_str) < 2 or not chat_id_str[1:].replace("_", "").isalnum():
                raise ValueError("Invalid channel username format")
            return

        # Group/supergroup format: -100{9,10 digits}
        if chat_id_str.startswith("-100"):
            remaining = chat_id_str[4:]
            if not remaining.isdigit() or len(remaining) not in (9, 10):
                raise ValueError("Invalid group/supergroup ID format")
            return

        # Basic group or private chat ID
        if not chat_id_str.replace("-", "").isdigit():
            raise ValueError("Invalid chat ID format")

    @classmethod
    def _validate_api_url(cls, url: str) -> None:
        """Validate and normalize Telegram API URL.

        Args:
            url: API URL to validate

        Raises:
            ValueError: If URL format is invalid
        """
        if not url:
            raise ValueError("API URL is required")

        try:
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                raise ValueError("Invalid API URL format")

            if parsed.scheme not in ("http", "https"):
                raise ValueError("API URL must use HTTP(S) protocol")

            if "telegram.org" not in parsed.netloc:
                raise ValueError("API URL must be from telegram.org domain")

        except Exception as err:
            raise ValueError(f"Invalid API URL: {err}") from err

    @classmethod
    def validate_config(cls, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate Telegram provider configuration.

        Args:
            config: Configuration dictionary to validate

        Returns:
            Dict[str, Any]: Validated configuration

        Raises:
            ValueError: If configuration is invalid
        """
        try:
            # Validate required settings
            cls._validate_bot_token(str(config.get("bot_token", "")))
            cls._validate_chat_id(config.get("chat_id", ""))
            cls._validate_api_url(str(config.get("api_base_url", "https://api.telegram.org")))

            # Prepare validated configuration
            validated = {
                "bot_token": str(config["bot_token"]),
                "chat_id": str(config["chat_id"]),
                "parse_mode": config.get("parse_mode", ParseMode.HTML),
                "disable_notifications": bool(config.get("disable_notifications", False)),
                "protect_content": bool(config.get("protect_content", False)),
                "message_thread_id": config.get("message_thread_id"),
                "api_base_url": config.get("api_base_url", "https://api.telegram.org").rstrip("/"),
                "max_message_length": min(
                    int(config.get("max_message_length", MessageLimit.MESSAGE_TEXT)),
                    MessageLimit.MESSAGE_TEXT
                ),
                "chat_type": config.get("chat_type"),
                "rate_limit": config.get("rate_limit", RATE_LIMIT["rate_limit"]),
                "rate_period": config.get("rate_period", RATE_LIMIT["rate_period"]),
                "retry_attempts": config.get("retry_attempts", RATE_LIMIT["max_retries"]),
                "retry_delay": config.get("retry_delay", RATE_LIMIT["retry_delay"]),
            }

            # Validate using schema
            BotConfigSchema(**validated)
            return validated

        except ValueError:
            raise
        except Exception as err:
            raise ValueError(f"Configuration validation failed: {err}") from err

    def __init__(self, config: Dict[str, Any]):
        """Initialize Telegram provider.

        Args:
            config: Provider configuration containing bot token and chat ID

        Raises:
            ValueError: If required configuration is missing or invalid
        """
        # Initialize with validated config
        validated_config = self.validate_config(config)
        super().__init__(
            rate_limit=validated_config["rate_limit"],
            rate_period=validated_config["rate_period"],
            retry_attempts=validated_config["retry_attempts"],
            retry_delay=validated_config["retry_delay"],
        )

        self.bot_token = validated_config["bot_token"]
        self.chat_id = validated_config["chat_id"]
        self.parse_mode = validated_config["parse_mode"]
        self.disable_notifications = validated_config["disable_notifications"]
        self.protect_content = validated_config["protect_content"]
        self.message_thread_id = validated_config["message_thread_id"]
        self.api_base_url = validated_config["api_base_url"]
        self.max_message_length = validated_config["max_message_length"]
        self.chat_type = validated_config["chat_type"]

        # Session management
        self.session: Optional[aiohttp.ClientSession] = None
        self._last_message_id: Optional[int] = None
        self._message_priority = MessagePriority.NORMAL

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

        url = self._build_api_url(method)
        max_retries = retries if retries is not None else self._retry_attempts
        last_error = None

        for attempt in range(max_retries + 1):
            try:
                async with self.session.post(url, json=data) as response:
                    response_data = await response.json()

                    # Handle rate limiting
                    if retry_after := await self._handle_rate_limit(response, response_data):
                        if attempt < max_retries:
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

            if attempt < max_retries:
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
            message_data = create_completion_message(
                parse_mode=self.parse_mode,
                include_stats=bool(stats),
                stats=stats
            )
            return await self.send_notification(message_data["text"])
        except TelegramError:
            raise
        except Exception as err:
            raise TelegramError(f"Failed to send completion notification: {err}") from err

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
        """
        try:
            message_data = create_error_message(
                error_message,
                parse_mode=self.parse_mode,
                include_debug=include_debug,
                debug_info=debug_info,
                priority=MessagePriority.HIGH
            )
            return await self.send_notification(message_data["text"])
        except TelegramError:
            raise
        except Exception as err:
            raise TelegramError(f"Failed to send error notification: {err}") from err

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
                # Message already deleted or not found
                return True
            raise
