"""Discord notification provider."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, override
from collections.abc import Mapping

from mover_status.notifications.base import NotificationProvider
from mover_status.plugins.discord.webhook.client import DiscordWebhookClient, DiscordEmbed
from mover_status.plugins.discord.webhook.error_handling import DiscordApiError, DiscordErrorType

if TYPE_CHECKING:
    from mover_status.notifications.models.message import Message

logger = logging.getLogger(__name__)


class DiscordProvider(NotificationProvider):
    """Discord notification provider using webhooks."""
    
    def __init__(self, config: Mapping[str, object]) -> None:
        """Initialize Discord provider.
        
        Args:
            config: Provider configuration
        """
        super().__init__(config)
        self.validate_config()
        
        webhook_url = str(config["webhook_url"])
        username = config.get("username")
        avatar_url = config.get("avatar_url")
        
        timeout_val = config.get("timeout", 30.0)
        max_retries_val = config.get("max_retries", 3)
        retry_delay_val = config.get("retry_delay", 1.0)
        
        self.webhook_client: DiscordWebhookClient = DiscordWebhookClient(
            webhook_url=webhook_url,
            username=str(username) if username is not None else None,
            avatar_url=str(avatar_url) if avatar_url is not None else None,
            timeout=float(timeout_val) if isinstance(timeout_val, (int, float, str)) else 30.0,
            max_retries=int(max_retries_val) if isinstance(max_retries_val, (int, float, str)) else 3,
            retry_delay=float(retry_delay_val) if isinstance(retry_delay_val, (int, float, str)) else 1.0,
        )
    
    @override
    def validate_config(self) -> None:
        """Validate Discord provider configuration."""
        if not self.config.get("webhook_url"):
            raise ValueError("webhook_url is required for Discord provider")
        
        webhook_url = str(self.config["webhook_url"])
        if not webhook_url.startswith(("http://", "https://")):
            raise ValueError("webhook_url must be a valid HTTP/HTTPS URL")
        
        if "discord.com" not in webhook_url and "discordapp.com" not in webhook_url:
            raise ValueError("webhook_url must be a Discord webhook URL")
        
        # Validate optional numeric configs
        timeout_val = self.config.get("timeout")
        if timeout_val is not None:
            # Only validate types that suggest configuration errors (like dicts)
            # Other invalid types will fall back to defaults in initialization
            if isinstance(timeout_val, dict):
                raise ValueError("timeout must be a number")
            if isinstance(timeout_val, (int, float, str)):
                try:
                    timeout = float(timeout_val)
                    if timeout <= 0:
                        raise ValueError("timeout must be positive")
                except (ValueError, TypeError) as e:
                    raise ValueError(f"Invalid timeout value: {e}")

        max_retries_val = self.config.get("max_retries")
        if max_retries_val is not None:
            # Only validate types that suggest configuration errors (like dicts)
            if isinstance(max_retries_val, dict):
                raise ValueError("max_retries must be a number")
            if isinstance(max_retries_val, (int, float, str)):
                try:
                    max_retries = int(max_retries_val)
                    if max_retries < 0:
                        raise ValueError("max_retries must be non-negative")
                except (ValueError, TypeError) as e:
                    raise ValueError(f"Invalid max_retries value: {e}")

        retry_delay_val = self.config.get("retry_delay")
        if retry_delay_val is not None:
            # Only validate types that suggest configuration errors (like dicts)
            if isinstance(retry_delay_val, dict):
                raise ValueError("retry_delay must be a number")
            if isinstance(retry_delay_val, (int, float, str)):
                try:
                    retry_delay = float(retry_delay_val)
                    if retry_delay < 0:
                        raise ValueError("retry_delay must be non-negative")
                except (ValueError, TypeError) as e:
                    raise ValueError(f"Invalid retry_delay value: {e}")
    
    @override
    def get_provider_name(self) -> str:
        """Get the provider name."""
        return "discord"
    
    @override
    async def send_notification(self, message: Message) -> bool:
        """Send notification via Discord webhook.
        
        Args:
            message: The notification message to send
            
        Returns:
            True if notification was sent successfully, False otherwise
        """
        try:
            embed = self._create_embed(message)
            
            success = await self.webhook_client.send_message(
                embeds=[embed],
            )
            
            if success:
                logger.info(f"Discord notification sent successfully: {message.title}")
            else:
                logger.error(f"Failed to send Discord notification: {message.title}")
            
            return success
            
        except DiscordApiError as e:
            # Handle Discord-specific errors appropriately
            if e.error_type in (DiscordErrorType.INVALID_WEBHOOK, DiscordErrorType.MISSING_PERMISSIONS):
                logger.error(f"Discord configuration error for '{message.title}': {e}")
                return False
            elif e.error_type in (DiscordErrorType.RATE_LIMITED, DiscordErrorType.SERVER_ERROR):
                logger.warning(f"Discord service error for '{message.title}': {e}")
                return False
            else:
                logger.error(f"Discord API error for '{message.title}': {e}")
                return False
            
        except Exception as e:
            logger.error(f"Unexpected error sending Discord notification for '{message.title}': {e}")
            return False
    
    def _create_embed(self, message: Message) -> DiscordEmbed:
        """Create Discord embed from message.
        
        Args:
            message: The notification message
            
        Returns:
            Discord embed object
        """
        # Map priority to color
        color_map = {
            "low": 0x00FF00,      # Green
            "normal": 0x0099FF,   # Blue
            "high": 0xFF9900,     # Orange
            "urgent": 0xFF0000,   # Red
        }
        
        embed = DiscordEmbed(
            title=message.title,
            description=message.content,
            color=color_map.get(message.priority, 0x0099FF),  # Default to blue
            timestamp=None,  # Could add current timestamp if needed
        )
        
        # Add tags as fields if present
        if message.tags:
            embed.fields.append({
                "name": "Tags",
                "value": ", ".join(message.tags),
                "inline": True,
            })
        
        # Add priority field
        embed.fields.append({
            "name": "Priority",
            "value": message.priority.title(),
            "inline": True,
        })
        
        # Add metadata fields if present
        for key, value in message.metadata.items():
            # Limit field count to avoid Discord limits
            if len(embed.fields) >= 20:  # Leave room for other fields
                break
            
            embed.fields.append({
                "name": key.replace("_", " ").title(),
                "value": str(value),
                "inline": True,
            })
        
        return embed