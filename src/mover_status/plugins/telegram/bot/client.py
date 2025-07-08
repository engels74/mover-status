"""Telegram Bot API client for sending notifications."""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import timedelta
from typing import TYPE_CHECKING, override
from enum import Enum

from telegram import Bot
from telegram.error import TelegramError, NetworkError, RetryAfter, TimedOut, Forbidden, BadRequest
from telegram.constants import ParseMode

if TYPE_CHECKING:
    from collections.abc import Sequence
    from mover_status.plugins.telegram.rate_limiting import AdvancedRateLimiter

logger = logging.getLogger(__name__)


class ChatType(Enum):
    """Telegram chat types."""
    USER = "user"
    GROUP = "group"
    SUPERGROUP = "supergroup"
    CHANNEL = "channel"


class ChatInfo:
    """Information about a Telegram chat."""

    def __init__(self, chat_id: str, chat_type: ChatType, title: str | None = None) -> None:
        """Initialize chat info.

        Args:
            chat_id: Telegram chat ID
            chat_type: Type of the chat
            title: Chat title (for groups/channels)
        """
        self.chat_id: str = chat_id
        self.chat_type: ChatType = chat_type
        self.title: str | None = title

    @override
    def __repr__(self) -> str:
        """String representation of chat info."""
        if self.title:
            return f"ChatInfo(id={self.chat_id}, type={self.chat_type.value}, title='{self.title}')"
        return f"ChatInfo(id={self.chat_id}, type={self.chat_type.value})"


class TelegramBotClient:
    """Telegram Bot API client for sending messages."""
    
    def __init__(
        self,
        bot_token: str,
        timeout: float = 30.0,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        rate_limiter: AdvancedRateLimiter | None = None
    ) -> None:
        """Initialize Telegram bot client.
        
        Args:
            bot_token: Telegram bot token
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
            retry_delay: Base delay between retries in seconds
            rate_limiter: Optional advanced rate limiter
        """
        self.bot_token: str = bot_token
        self.timeout: float = timeout
        self.max_retries: int = max_retries
        self.retry_delay: float = retry_delay
        self.rate_limiter: AdvancedRateLimiter | None = rate_limiter
        
        # Validate bot token format
        if not self._is_valid_bot_token(bot_token):
            raise ValueError(f"Invalid bot token format: {bot_token}")
        
        # Initialize bot client
        self.bot: Bot = Bot(token=bot_token)
    
    async def send_message(
        self,
        chat_id: str,
        text: str,
        parse_mode: str = ParseMode.HTML,
        disable_web_page_preview: bool = True
    ) -> bool:
        """Send a message to a specific chat.
        
        Args:
            chat_id: Telegram chat ID
            text: Message text to send
            parse_mode: Parse mode for message formatting
            disable_web_page_preview: Whether to disable link previews
            
        Returns:
            True if message was sent successfully, False otherwise
        """
        if not self._is_valid_chat_id(chat_id):
            logger.error(f"Invalid chat ID format: {chat_id}")
            return False
        
        # Apply rate limiting if available
        if self.rate_limiter:
            wait_time = await self.rate_limiter.acquire(chat_id)
            if wait_time > 0:
                logger.debug(f"Rate limiting: waiting {wait_time:.2f}s for chat {chat_id}")
                await asyncio.sleep(wait_time)
        
        for attempt in range(self.max_retries + 1):
            try:
                _ = await self.bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    parse_mode=parse_mode,
                    disable_web_page_preview=disable_web_page_preview,
                    read_timeout=self.timeout,
                    write_timeout=self.timeout,
                    connect_timeout=self.timeout,
                )
                
                logger.debug(f"Message sent successfully to chat {chat_id}")
                return True
                
            except RetryAfter as e:
                # Handle rate limiting with Telegram's suggested delay
                retry_after = e.retry_after
                if isinstance(retry_after, timedelta):
                    wait_time = retry_after.total_seconds()
                else:
                    wait_time = float(retry_after)
                logger.warning(f"Rate limited by Telegram API, waiting {wait_time} seconds before retry")
                await asyncio.sleep(wait_time)
                continue
                
            except TimedOut as e:
                logger.warning(f"Request timed out for chat {chat_id} (attempt {attempt + 1}): {e}")
                if attempt < self.max_retries:
                    wait_time = self.retry_delay * (2.0 ** attempt)
                    await asyncio.sleep(wait_time)
                    continue
                    
            except Forbidden as e:
                logger.error(f"Bot blocked or no permissions for chat {chat_id}: {e}")
                return False
                
            except BadRequest as e:
                logger.error(f"Invalid request for chat {chat_id}: {e}")
                return False
                
            except NetworkError as e:
                logger.warning(f"Network error for chat {chat_id} (attempt {attempt + 1}): {e}")
                if attempt < self.max_retries:
                    wait_time = self.retry_delay * (2.0 ** attempt)
                    await asyncio.sleep(wait_time)
                    continue
                
            except TelegramError as e:
                logger.error(f"Telegram API error for chat {chat_id}: {e}")
                return False
                
            except Exception as e:
                logger.error(f"Unexpected error sending message to chat {chat_id}: {e}")
                return False
        
        logger.error(f"Failed to send message to chat {chat_id} after {self.max_retries + 1} attempts")
        return False
    
    async def send_message_to_multiple_chats(
        self,
        chat_ids: Sequence[str],
        text: str,
        parse_mode: str = ParseMode.HTML,
        disable_web_page_preview: bool = True
    ) -> bool:
        """Send a message to multiple chats concurrently.
        
        Args:
            chat_ids: List of Telegram chat IDs
            text: Message text to send
            parse_mode: Parse mode for message formatting
            disable_web_page_preview: Whether to disable link previews
            
        Returns:
            True if message was sent successfully to all chats, False otherwise
        """
        if not chat_ids:
            logger.warning("No chat IDs provided")
            return False
        
        # Send messages concurrently
        tasks = [
            self.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode=parse_mode,
                disable_web_page_preview=disable_web_page_preview
            )
            for chat_id in chat_ids
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Check results
        successful_sends = 0
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Exception sending to chat {chat_ids[i]}: {result}")
            elif result is True:
                successful_sends += 1
            else:
                logger.warning(f"Failed to send message to chat {chat_ids[i]}")
        
        success_rate = successful_sends / len(chat_ids)
        logger.info(f"Message sent to {successful_sends}/{len(chat_ids)} chats ({success_rate:.1%})")
        
        # Return True only if all messages were sent successfully
        return successful_sends == len(chat_ids)
    
    async def get_me(self) -> dict[str, object] | None:
        """Get bot information for validation.
        
        Returns:
            Bot information dict or None if failed
        """
        try:
            bot_info = await self.bot.get_me()
            return {
                "id": bot_info.id,
                "username": bot_info.username,
                "first_name": bot_info.first_name,
                "is_bot": bot_info.is_bot
            }
        except TelegramError as e:
            logger.error(f"Failed to get bot info: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error getting bot info: {e}")
            return None

    def classify_chat_type(self, chat_id: str) -> ChatType:
        """Classify chat type based on chat ID format.

        Args:
            chat_id: Telegram chat ID

        Returns:
            ChatType enum value
        """
        if not chat_id.startswith("-"):
            return ChatType.USER
        elif chat_id.startswith("-100"):
            # Both supergroups and channels use -100 prefix
            # We'll default to supergroup, but this can be refined with API calls
            return ChatType.SUPERGROUP
        else:
            # Legacy group format (rare)
            return ChatType.GROUP

    def categorize_chats(self, chat_ids: Sequence[str]) -> dict[ChatType, list[str]]:
        """Categorize chat IDs by their type.

        Args:
            chat_ids: List of chat IDs to categorize

        Returns:
            Dictionary mapping chat types to lists of chat IDs
        """
        categorized: dict[ChatType, list[str]] = {
            ChatType.USER: [],
            ChatType.GROUP: [],
            ChatType.SUPERGROUP: [],
            ChatType.CHANNEL: []
        }

        for chat_id in chat_ids:
            chat_type = self.classify_chat_type(chat_id)
            categorized[chat_type].append(chat_id)

        return categorized

    async def send_message_by_chat_type(
        self,
        chat_ids: Sequence[str],
        text: str,
        parse_mode: str = ParseMode.HTML,
        disable_web_page_preview: bool = True,
        prioritize_users: bool = True
    ) -> dict[str, bool]:
        """Send messages with chat type prioritization.

        Args:
            chat_ids: List of chat IDs
            text: Message text
            parse_mode: Parse mode for formatting
            disable_web_page_preview: Whether to disable link previews
            prioritize_users: Whether to send to users first

        Returns:
            Dictionary mapping chat IDs to success status
        """
        if not chat_ids:
            logger.warning("No chat IDs provided")
            return {}

        categorized = self.categorize_chats(chat_ids)
        results: dict[str, bool] = {}

        # Define sending order based on priority
        if prioritize_users:
            send_order = [ChatType.USER, ChatType.SUPERGROUP, ChatType.GROUP, ChatType.CHANNEL]
        else:
            send_order = [ChatType.CHANNEL, ChatType.SUPERGROUP, ChatType.GROUP, ChatType.USER]

        for chat_type in send_order:
            type_chat_ids = categorized[chat_type]
            if not type_chat_ids:
                continue

            logger.info(f"Sending to {len(type_chat_ids)} {chat_type.value} chats")

            # Send to all chats of this type concurrently
            tasks = [
                self.send_message(
                    chat_id=chat_id,
                    text=text,
                    parse_mode=parse_mode,
                    disable_web_page_preview=disable_web_page_preview
                )
                for chat_id in type_chat_ids
            ]

            type_results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results for this chat type
            for i, result in enumerate(type_results):
                chat_id = type_chat_ids[i]
                if isinstance(result, Exception):
                    logger.error(f"Exception sending to {chat_type.value} chat {chat_id}: {result}")
                    results[chat_id] = False
                else:
                    results[chat_id] = bool(result)

        return results

    async def validate_chat_permissions(self, chat_ids: Sequence[str]) -> dict[str, bool]:
        """Validate bot permissions for each chat.

        Args:
            chat_ids: List of chat IDs to validate

        Returns:
            Dictionary mapping chat IDs to permission status
        """
        if not chat_ids:
            return {}

        results: dict[str, bool] = {}

        # Test permissions by attempting to get chat info
        for chat_id in chat_ids:
            try:
                chat = await self.bot.get_chat(chat_id)
                # If we can get chat info, we have basic permissions
                results[chat_id] = True
                logger.debug(f"Validated permissions for chat {chat_id} ({chat.type})")
            except TelegramError as e:
                logger.warning(f"Permission validation failed for chat {chat_id}: {e}")
                results[chat_id] = False
            except Exception as e:
                logger.error(f"Unexpected error validating chat {chat_id}: {e}")
                results[chat_id] = False

        return results

    async def get_chat_info(self, chat_ids: Sequence[str]) -> dict[str, ChatInfo | None]:
        """Get detailed information about chats.

        Args:
            chat_ids: List of chat IDs

        Returns:
            Dictionary mapping chat IDs to ChatInfo objects or None if failed
        """
        if not chat_ids:
            return {}

        results: dict[str, ChatInfo | None] = {}

        for chat_id in chat_ids:
            try:
                chat = await self.bot.get_chat(chat_id)

                # Map Telegram chat type to our ChatType enum
                if chat.type == "private":
                    chat_type = ChatType.USER
                elif chat.type == "group":
                    chat_type = ChatType.GROUP
                elif chat.type == "supergroup":
                    chat_type = ChatType.SUPERGROUP
                elif chat.type == "channel":
                    chat_type = ChatType.CHANNEL
                else:
                    # Default fallback
                    chat_type = self.classify_chat_type(chat_id)

                results[chat_id] = ChatInfo(
                    chat_id=chat_id,
                    chat_type=chat_type,
                    title=chat.title
                )

            except TelegramError as e:
                logger.warning(f"Failed to get info for chat {chat_id}: {e}")
                results[chat_id] = None
            except Exception as e:
                logger.error(f"Unexpected error getting info for chat {chat_id}: {e}")
                results[chat_id] = None

        return results

    async def send_message_with_fallback(
        self,
        primary_chat_ids: Sequence[str],
        fallback_chat_ids: Sequence[str],
        text: str,
        parse_mode: str = ParseMode.HTML,
        disable_web_page_preview: bool = True
    ) -> bool:
        """Send message with fallback chats if primary chats fail.

        Args:
            primary_chat_ids: Primary chat IDs to try first
            fallback_chat_ids: Fallback chat IDs if primary fails
            text: Message text
            parse_mode: Parse mode for formatting
            disable_web_page_preview: Whether to disable link previews

        Returns:
            True if message was sent to at least one chat, False otherwise
        """
        # Try primary chats first
        if primary_chat_ids:
            primary_success = await self.send_message_to_multiple_chats(
                chat_ids=primary_chat_ids,
                text=text,
                parse_mode=parse_mode,
                disable_web_page_preview=disable_web_page_preview
            )

            if primary_success:
                logger.info(f"Message sent successfully to {len(primary_chat_ids)} primary chats")
                return True
            else:
                logger.warning("Primary chats failed, trying fallback chats")

        # Try fallback chats if primary failed or was empty
        if fallback_chat_ids:
            fallback_success = await self.send_message_to_multiple_chats(
                chat_ids=fallback_chat_ids,
                text=text,
                parse_mode=parse_mode,
                disable_web_page_preview=disable_web_page_preview
            )

            if fallback_success:
                logger.info(f"Message sent successfully to {len(fallback_chat_ids)} fallback chats")
                return True
            else:
                logger.error("Both primary and fallback chats failed")

        return False

    def _is_valid_bot_token(self, token: str) -> bool:
        """Validate bot token format.
        
        Args:
            token: Bot token to validate
            
        Returns:
            True if token format is valid, False otherwise
        """
        # Telegram bot token format: number:alphanumeric_string
        pattern = r"^\d+:[A-Za-z0-9_-]+$"
        return bool(re.match(pattern, token))
    
    def _is_valid_chat_id(self, chat_id: str) -> bool:
        """Validate chat ID format.
        
        Args:
            chat_id: Chat ID to validate
            
        Returns:
            True if chat ID format is valid, False otherwise
        """
        # Chat ID can be:
        # - Positive integer for users (e.g., "123456789")
        # - Negative integer for groups/channels (e.g., "-100123456789")
        pattern = r"^-?\d+$"
        return bool(re.match(pattern, chat_id))
    
    def get_rate_limiting_statistics(self) -> dict[str, int | float | dict[str, int]] | None:
        """Get rate limiting statistics if rate limiter is enabled.
        
        Returns:
            Rate limiting statistics or None if not enabled
        """
        if self.rate_limiter:
            return self.rate_limiter.get_statistics()
        return None
    
    async def test_bot_authentication(self) -> dict[str, object]:
        """Test bot authentication and return detailed status.
        
        Returns:
            Dictionary with authentication status and bot information
        """
        try:
            bot_info = await self.bot.get_me()
            return {
                "authenticated": True,
                "bot_info": {
                    "id": bot_info.id,
                    "username": bot_info.username,
                    "first_name": bot_info.first_name,
                    "is_bot": bot_info.is_bot,
                    "can_join_groups": bot_info.can_join_groups,
                    "can_read_all_group_messages": bot_info.can_read_all_group_messages,
                    "supports_inline_queries": bot_info.supports_inline_queries
                },
                "error": None
            }
        except Forbidden as e:
            logger.error(f"Bot authentication forbidden: {e}")
            return {
                "authenticated": False,
                "bot_info": None,
                "error": {"type": "forbidden", "message": str(e)}
            }
        except BadRequest as e:
            logger.error(f"Bad request during authentication: {e}")
            return {
                "authenticated": False,
                "bot_info": None,
                "error": {"type": "bad_request", "message": str(e)}
            }
        except TelegramError as e:
            logger.error(f"Telegram error during authentication: {e}")
            return {
                "authenticated": False,
                "bot_info": None,
                "error": {"type": "telegram_error", "message": str(e)}
            }
        except Exception as e:
            logger.error(f"Unexpected error during authentication: {e}")
            return {
                "authenticated": False,
                "bot_info": None,
                "error": {"type": "unexpected", "message": str(e)}
            }