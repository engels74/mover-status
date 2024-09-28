# notifiers/telegram.py
import aiohttp
from typing import Dict, Any
from .base import BaseNotifier

class TelegramNotifier(BaseNotifier):
    """
    Telegram notifier implementation.
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.bot_token = config['bot_token']
        self.chat_id = config['chat_id']
        self.api_url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        self.moving_message_template = config['messages']['moving']['telegram']
        self.completion_message = config['messages']['completion']

    @classmethod
    def from_config(cls, config: Dict[str, Any]) -> 'TelegramNotifier':
        return cls(config)

    async def send_notification(self, percent: int, remaining_data: str, etc: str) -> bool:
        message = self.moving_message_template.format(
            percent=percent,
            remaining_data=remaining_data,
            etc=etc
        )
        return await self._send_telegram_message(message)

    async def send_completion_notification(self) -> bool:
        return await self._send_telegram_message(self.completion_message)

    async def send_error_notification(self, error_message: str) -> bool:
        return await self._send_telegram_message(f"Error: {error_message}")

    async def _send_telegram_message(self, message: str) -> bool:
        payload = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": "HTML",
            "disable_notification": False
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(self.api_url, json=payload) as response:
                if response.status == 200:
                    response_json = await response.json()
                    return response_json.get('ok', False)
                else:
                    # Log the error here
                    return False

    async def _send_telegram_message_with_markdown(self, message: str) -> bool:
        payload = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": "MarkdownV2",
            "disable_notification": False
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(self.api_url, json=payload) as response:
                if response.status == 200:
                    response_json = await response.json()
                    return response_json.get('ok', False)
                else:
                    # Log the error here
                    return False
