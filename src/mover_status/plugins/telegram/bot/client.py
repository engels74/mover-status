"""Telegram Bot API client for sending notifications."""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import timedelta
from typing import TYPE_CHECKING

from telegram import Bot
from telegram.error import TelegramError, NetworkError, RetryAfter, TimedOut
from telegram.constants import ParseMode

if TYPE_CHECKING:
    from collections.abc import Sequence

logger = logging.getLogger(__name__)


class TelegramBotClient:
    """Telegram Bot API client for sending messages."""
    
    def __init__(
        self,
        bot_token: str,
        timeout: float = 30.0,
        max_retries: int = 3,
        retry_delay: float = 1.0
    ) -> None:
        """Initialize Telegram bot client.
        
        Args:
            bot_token: Telegram bot token
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
            retry_delay: Base delay between retries in seconds
        """
        self.bot_token: str = bot_token
        self.timeout: float = timeout
        self.max_retries: int = max_retries
        self.retry_delay: float = retry_delay
        
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
                logger.warning(f"Rate limited, waiting {wait_time} seconds before retry")
                await asyncio.sleep(wait_time)
                continue
                
            except TimedOut as e:
                logger.warning(f"Request timed out for chat {chat_id} (attempt {attempt + 1}): {e}")
                if attempt < self.max_retries:
                    wait_time = self.retry_delay * (2.0 ** attempt)
                    await asyncio.sleep(wait_time)
                    continue
                    
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