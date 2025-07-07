"""Telegram notification provider."""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, override, cast
from collections.abc import Mapping


from mover_status.notifications.base import NotificationProvider
from mover_status.plugins.telegram.bot import TelegramBotClient
from mover_status.plugins.telegram.bot.client import ChatInfo
from mover_status.plugins.telegram.formatting import HTMLFormatter, MarkdownFormatter, MarkdownV2Formatter, MessageFormatter

if TYPE_CHECKING:
    from mover_status.notifications.models.message import Message

logger = logging.getLogger(__name__)


class TelegramProvider(NotificationProvider):
    """Telegram notification provider using Bot API."""
    
    def __init__(self, config: Mapping[str, object]) -> None:
        """Initialize Telegram provider.
        
        Args:
            config: Provider configuration
        """
        super().__init__(config)
        self.validate_config()
        
        # Extract configuration
        self.bot_token: str = str(config["bot_token"])
        chat_ids_raw: object = config["chat_ids"]
        if not isinstance(chat_ids_raw, list):
            raise ValueError("chat_ids must be a list")
        # Type narrowing: chat_ids_raw is now known to be a list
        chat_ids_list = cast(list[object], chat_ids_raw)
        self.chat_ids: list[str] = [str(chat_id) for chat_id in chat_ids_list]
        
        # Optional configuration with defaults
        parse_mode_config = config.get("parse_mode", "HTML")
        self.parse_mode: str = str(parse_mode_config)
        
        disable_preview_config = config.get("disable_web_page_preview", True)
        self.disable_web_page_preview: bool = bool(disable_preview_config)
        
        timeout_config = config.get("timeout", 30.0)
        self.timeout: float = float(timeout_config) if isinstance(timeout_config, (int, float, str)) else 30.0
        
        max_retries_config = config.get("max_retries", 3)
        self.max_retries: int = int(max_retries_config) if isinstance(max_retries_config, (int, float, str)) else 3
        
        retry_delay_config = config.get("retry_delay", 1.0)
        self.retry_delay: float = float(retry_delay_config) if isinstance(retry_delay_config, (int, float, str)) else 1.0
        
        # Initialize bot client
        self.bot_client: TelegramBotClient = TelegramBotClient(
            bot_token=self.bot_token,
            timeout=self.timeout,
            max_retries=self.max_retries,
            retry_delay=self.retry_delay
        )
        
        # Initialize formatter based on parse mode
        self.formatter: MessageFormatter
        if self.parse_mode == "HTML":
            self.formatter = HTMLFormatter()
        elif self.parse_mode == "Markdown":
            self.formatter = MarkdownFormatter()
        elif self.parse_mode == "MarkdownV2":
            self.formatter = MarkdownV2Formatter()
        else:
            # Default to HTML formatter
            self.formatter = HTMLFormatter()
    
    @override
    def validate_config(self) -> None:
        """Validate Telegram provider configuration."""
        # Check required fields
        if "bot_token" not in self.config:
            raise ValueError("bot_token is required for Telegram provider")
        
        if "chat_ids" not in self.config:
            raise ValueError("chat_ids is required for Telegram provider")
        
        # Validate bot token format
        bot_token = str(self.config["bot_token"])
        if not self._is_valid_bot_token(bot_token):
            raise ValueError(f"Invalid bot token format: {bot_token}")
        
        # Validate chat IDs
        chat_ids: object = self.config["chat_ids"]
        if not isinstance(chat_ids, list):
            raise ValueError("chat_ids must be a list")
        
        # Type narrowing: chat_ids is now known to be a list
        chat_ids_list = cast(list[object], chat_ids)
        if len(chat_ids_list) == 0:
            raise ValueError("chat_ids cannot be empty")
        for chat_id in chat_ids_list:
            chat_id_str = str(chat_id)
            if not self._is_valid_chat_id(chat_id_str):
                raise ValueError(f"Invalid chat ID format: {chat_id_str}")
        
        # Validate parse mode if provided
        if "parse_mode" in self.config:
            parse_mode = str(self.config["parse_mode"])
            valid_modes = ["HTML", "Markdown", "MarkdownV2"]
            if parse_mode not in valid_modes:
                raise ValueError(f"parse_mode must be one of {valid_modes}, got: {parse_mode}")
    
    @override
    async def send_notification(self, message: Message) -> bool:
        """Send a notification message via Telegram.
        
        Args:
            message: The notification message to send
            
        Returns:
            True if the notification was sent successfully to all chats, False otherwise
        """
        # Format message text using the appropriate formatter
        text = self.formatter.format_message(message)
        
        # Send message to all configured chats
        success = await self.bot_client.send_message_to_multiple_chats(
            chat_ids=self.chat_ids,
            text=text,
            parse_mode=self.parse_mode,
            disable_web_page_preview=self.disable_web_page_preview
        )
        
        if success:
            logger.info(f"Telegram notification sent successfully to {len(self.chat_ids)} chats")
        else:
            logger.error("Failed to send Telegram notification to one or more chats")
        
        return success
    
    @override
    def get_provider_name(self) -> str:
        """Get the name of this provider.
        
        Returns:
            The provider name
        """
        return "telegram"

    async def get_chat_statistics(self) -> dict[str, int | dict[str, int] | list[str]]:
        """Get statistics about configured chats.

        Returns:
            Dictionary with chat statistics
        """
        categorized = self.bot_client.categorize_chats(self.chat_ids)

        stats = {
            "total_chats": len(self.chat_ids),
            "chat_types": {
                chat_type.value: len(chat_ids)
                for chat_type, chat_ids in categorized.items()
                if chat_ids  # Only include types with chats
            },
            "chat_ids": list(self.chat_ids)
        }

        return stats

    async def validate_all_chats(self) -> dict[str, bool]:
        """Validate permissions for all configured chats.

        Returns:
            Dictionary mapping chat IDs to validation status
        """
        return await self.bot_client.validate_chat_permissions(self.chat_ids)

    async def get_all_chat_info(self) -> dict[str, ChatInfo | None]:
        """Get detailed information about all configured chats.

        Returns:
            Dictionary mapping chat IDs to ChatInfo objects
        """
        return await self.bot_client.get_chat_info(self.chat_ids)

    async def send_notification_by_priority(
        self,
        message: Message,
        prioritize_users: bool = True
    ) -> dict[str, bool]:
        """Send notification with chat type prioritization.

        Args:
            message: The notification message to send
            prioritize_users: Whether to prioritize user chats over groups/channels

        Returns:
            Dictionary mapping chat IDs to success status
        """
        # Format message text using the appropriate formatter
        text = self.formatter.format_message(message)

        # Send with prioritization
        results = await self.bot_client.send_message_by_chat_type(
            chat_ids=self.chat_ids,
            text=text,
            parse_mode=self.parse_mode,
            disable_web_page_preview=self.disable_web_page_preview,
            prioritize_users=prioritize_users
        )

        successful_chats = sum(1 for success in results.values() if success)
        total_chats = len(results)

        if successful_chats == total_chats:
            logger.info(f"Telegram notification sent successfully to all {total_chats} chats")
        elif successful_chats > 0:
            logger.warning(f"Telegram notification sent to {successful_chats}/{total_chats} chats")
        else:
            logger.error("Failed to send Telegram notification to any chats")

        return results

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