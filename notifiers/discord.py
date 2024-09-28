# notifiers/discord.py
import aiohttp
from typing import Dict, Any
from .base import BaseNotifier
from ..mover.utils import get_color_from_percent

class DiscordNotifier(BaseNotifier):
    """
    Discord notifier implementation.
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.webhook_url = config['webhook_url']
        self.name_override = config.get('name_override', 'Mover Bot')
        self.moving_message_template = config['messages']['moving']['discord']
        self.completion_message = config['messages']['completion']

    @classmethod
    def from_config(cls, config: Dict[str, Any]) -> 'DiscordNotifier':
        return cls(config)

    async def send_notification(self, percent: int, remaining_data: str, etc: str) -> bool:
        message = self.moving_message_template.format(
            percent=percent,
            remaining_data=remaining_data,
            etc=etc
        )
        color = get_color_from_percent(percent)
        return await self._send_discord_message(message, color)

    async def send_completion_notification(self) -> bool:
        return await self._send_discord_message(self.completion_message, get_color_from_percent(100))

    async def send_error_notification(self, error_message: str) -> bool:
        return await self._send_discord_message(f"Error: {error_message}", 16711680)  # Red color

    async def _send_discord_message(self, message: str, color: int) -> bool:
        payload = {
            "username": self.name_override,
            "embeds": [{
                "description": message,
                "color": color
            }]
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(self.webhook_url, json=payload) as response:
                if response.status == 204:
                    return True
                else:
                    # Log the error here
                    return False

    async def _send_discord_message_with_fields(self, title: str, fields: list, color: int) -> bool:
        payload = {
            "username": self.name_override,
            "embeds": [{
                "title": title,
                "color": color,
                "fields": fields
            }]
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(self.webhook_url, json=payload) as response:
                if response.status == 204:
                    return True
                else:
                    # Log the error here
                    return False
