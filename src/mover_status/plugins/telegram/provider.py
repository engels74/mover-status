"""Telegram notification provider."""

from __future__ import annotations

import asyncio
import logging
import re
from typing import TYPE_CHECKING, override, cast
from collections.abc import Mapping


from mover_status.notifications.base import NotificationProvider
from mover_status.plugins.telegram.bot import TelegramBotClient
from mover_status.plugins.telegram.bot.client import ChatInfo
from mover_status.plugins.telegram.formatting import HTMLFormatter, MarkdownFormatter, MarkdownV2Formatter, MessageFormatter
from mover_status.plugins.telegram.rate_limiting import AdvancedRateLimiter, RateLimitConfig

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
        
        # Rate limiting configuration (optional)
        rate_limiting_config = config.get("rate_limiting", {})
        rate_limiter: AdvancedRateLimiter | None = None
        if isinstance(rate_limiting_config, dict) and rate_limiting_config.get("enabled", False):
            rate_limit_config = RateLimitConfig(
                global_limit=int(rate_limiting_config.get("global_limit", 30)),
                global_burst_limit=int(rate_limiting_config.get("global_burst_limit", 100)),
                chat_limit=int(rate_limiting_config.get("chat_limit", 20)),
                chat_burst_limit=int(rate_limiting_config.get("chat_burst_limit", 50)),
                group_limit=int(rate_limiting_config.get("group_limit", 20)),
                group_burst_limit=int(rate_limiting_config.get("group_burst_limit", 50)),
                hourly_quota=int(rate_limiting_config.get("hourly_quota", 1000)),
                hourly_quota_enabled=bool(rate_limiting_config.get("hourly_quota_enabled", True))
            )
            rate_limiter = AdvancedRateLimiter(rate_limit_config)
        
        # Initialize bot client
        self.bot_client: TelegramBotClient = TelegramBotClient(
            bot_token=self.bot_token,
            timeout=self.timeout,
            max_retries=self.max_retries,
            retry_delay=self.retry_delay,
            rate_limiter=rate_limiter
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
    
    async def get_comprehensive_status(self) -> dict[str, object]:
        """Get comprehensive status including authentication, permissions, and rate limiting.
        
        Returns:
            Comprehensive status dictionary
        """
        status: dict[str, object] = {
            "provider_name": self.get_provider_name(),
            "configuration": {
                "chat_count": len(self.chat_ids),
                "parse_mode": self.parse_mode,
                "timeout": self.timeout,
                "max_retries": self.max_retries,
                "retry_delay": self.retry_delay,
                "rate_limiting_enabled": self.bot_client.rate_limiter is not None
            }
        }
        
        # Test authentication
        auth_status = await self.bot_client.test_bot_authentication()
        status["authentication"] = auth_status
        
        # Get chat statistics
        chat_stats = await self.get_chat_statistics()
        status["chat_statistics"] = chat_stats
        
        # Get rate limiting statistics if available
        rate_stats = self.bot_client.get_rate_limiting_statistics()
        if rate_stats:
            status["rate_limiting"] = rate_stats
        
        # Validate chat permissions
        try:
            permissions = await self.validate_all_chats()
            status["chat_permissions"] = {
                "total_chats": len(permissions),
                "accessible_chats": sum(1 for accessible in permissions.values() if accessible),
                "blocked_chats": sum(1 for accessible in permissions.values() if not accessible),
                "details": permissions
            }
        except Exception as e:
            logger.warning(f"Failed to validate chat permissions: {e}")
            status["chat_permissions"] = {"error": str(e)}
        
        return status
    
    async def send_notification_with_fallback_and_monitoring(
        self,
        message: Message,
        fallback_enabled: bool = True
    ) -> dict[str, object]:
        """Send notification with comprehensive monitoring and fallback handling.
        
        Args:
            message: The notification message to send
            fallback_enabled: Whether to use fallback strategies on failures
            
        Returns:
            Detailed result dictionary with success status and metrics
        """
        start_time = asyncio.get_event_loop().time()
        
        # Initial attempt
        result = await self.send_notification_by_priority(message, prioritize_users=True)
        
        success_count = sum(1 for success in result.values() if success)
        total_chats = len(result)
        
        response: dict[str, object] = {
            "success": success_count == total_chats,
            "partial_success": success_count > 0,
            "metrics": {
                "successful_chats": success_count,
                "total_chats": total_chats,
                "success_rate": success_count / total_chats if total_chats > 0 else 0,
                "execution_time": asyncio.get_event_loop().time() - start_time
            },
            "details": result
        }
        
        # If fallback is enabled and we had failures, try alternative strategies
        if fallback_enabled and success_count < total_chats:
            failed_chats = [chat_id for chat_id, success in result.items() if not success]
            
            if failed_chats:
                logger.info(f"Attempting fallback for {len(failed_chats)} failed chats")
                
                # Try with different settings (e.g., without web preview)
                fallback_result = await self._attempt_fallback_delivery(message, failed_chats)
                
                # Update metrics
                additional_success = sum(1 for success in fallback_result.values() if success)
                metrics = cast(dict[str, object], response["metrics"])
                metrics["fallback_successful"] = additional_success
                metrics["final_successful_chats"] = success_count + additional_success
                response["fallback_details"] = fallback_result
                
                if additional_success > 0:
                    response["partial_success"] = True
                    response["success"] = (success_count + additional_success) == total_chats
        
        metrics = cast(dict[str, object], response["metrics"])
        metrics["final_execution_time"] = asyncio.get_event_loop().time() - start_time
        
        return response
    
    async def _attempt_fallback_delivery(
        self,
        message: Message,
        failed_chat_ids: list[str]
    ) -> dict[str, bool]:
        """Attempt fallback delivery strategies for failed chats.
        
        Args:
            message: The notification message to send
            failed_chat_ids: List of chat IDs that failed initial delivery
            
        Returns:
            Dictionary mapping chat IDs to success status
        """
        # Format message with plain text as fallback
        fallback_text = f"{message.title}\n\n{message.content}"
        
        fallback_results: dict[str, bool] = {}
        
        for chat_id in failed_chat_ids:
            try:
                # Try with plain text and no formatting
                success = await self.bot_client.send_message(
                    chat_id=chat_id,
                    text=fallback_text,
                    parse_mode="",  # No parsing
                    disable_web_page_preview=True
                )
                fallback_results[chat_id] = success
                
                if success:
                    logger.info(f"Fallback delivery successful for chat {chat_id}")
                else:
                    logger.warning(f"Fallback delivery failed for chat {chat_id}")
                    
            except Exception as e:
                logger.error(f"Fallback delivery exception for chat {chat_id}: {e}")
                fallback_results[chat_id] = False
        
        return fallback_results

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