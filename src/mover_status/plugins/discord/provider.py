"""Discord notification provider."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, override
from collections.abc import Mapping

from mover_status.notifications.base import NotificationProvider, with_retry
from mover_status.plugins.discord.webhook.client import DiscordWebhookClient, DiscordEmbed

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
            username=str(username) if username else None,
            avatar_url=str(avatar_url) if avatar_url else None,
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
            try:
                if isinstance(timeout_val, (int, float, str)):
                    timeout = float(timeout_val)
                    if timeout <= 0:
                        raise ValueError("timeout must be positive")
                else:
                    raise TypeError("timeout must be a number")
            except (ValueError, TypeError) as e:
                raise ValueError(f"Invalid timeout value: {e}")
        
        max_retries_val = self.config.get("max_retries")
        if max_retries_val is not None:
            try:
                if isinstance(max_retries_val, (int, float, str)):
                    max_retries = int(max_retries_val)
                    if max_retries < 0:
                        raise ValueError("max_retries must be non-negative")
                else:
                    raise TypeError("max_retries must be a number")
            except (ValueError, TypeError) as e:
                raise ValueError(f"Invalid max_retries value: {e}")
        
        retry_delay_val = self.config.get("retry_delay")
        if retry_delay_val is not None:
            try:
                if isinstance(retry_delay_val, (int, float, str)):
                    retry_delay = float(retry_delay_val)
                    if retry_delay < 0:
                        raise ValueError("retry_delay must be non-negative")
                else:
                    raise TypeError("retry_delay must be a number")
            except (ValueError, TypeError) as e:
                raise ValueError(f"Invalid retry_delay value: {e}")
    
    @override
    def get_provider_name(self) -> str:
        """Get the provider name."""
        return "discord"
    
    @with_retry(max_attempts=3, backoff_factor=2.0)
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
            
        except Exception as e:
            logger.error(f"Error sending Discord notification: {e}")
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