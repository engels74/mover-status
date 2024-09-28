# tests/test_notifiers.py
import pytest
from unittest.mock import patch, MagicMock
from notifiers.discord import DiscordNotifier
from notifiers.telegram import TelegramNotifier

@pytest.fixture
def mock_discord_config():
    """
    Fixture that provides a mock configuration for Discord notifier testing.
    
    This configuration mimics the structure of the actual Discord config,
    but with placeholder values for testing purposes.
    """
    return {
        'webhook_url': 'https://discord.com/api/webhooks/xxx/yyy',
        'name_override': 'Test Bot',
        'messages': {
            'moving': {
                'discord': 'Moving: {percent}% complete, {remaining_data} remaining, ETC: {etc}'
            },
            'completion': 'Move completed!'
        }
    }

@pytest.fixture
def mock_telegram_config():
    """
    Fixture that provides a mock configuration for Telegram notifier testing.
    
    This configuration mimics the structure of the actual Telegram config,
    but with placeholder values for testing purposes.
    """
    return {
        'bot_token': '123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11',
        'chat_id': '123456789',
        'messages': {
            'moving': {
                'telegram': 'Moving: {percent}% complete, {remaining_data} remaining, ETC: {etc}'
            },
            'completion': 'Move completed!'
        }
    }

@pytest.mark.asyncio
async def test_discord_send_notification(mock_discord_config):
    """
    Test the send_notification method of DiscordNotifier.
    
    This test ensures that the method correctly formats the notification message
    and sends it to the Discord webhook.
    """
    with patch('aiohttp.ClientSession.post') as mock_post:
        mock_response = MagicMock()
        mock_response.status = 204
        mock_post.return_value.__aenter__.return_value = mock_response

        notifier = DiscordNotifier(mock_discord_config)
        result = await notifier.send_notification(50, '500 MB', '10 minutes')

        assert result is True
        mock_post.assert_called_once()
        _, kwargs = mock_post.call_args
        assert kwargs['json']['embeds'][0]['description'] == 'Moving: 50% complete, 500 MB remaining, ETC: 10 minutes'

@pytest.mark.asyncio
async def test_discord_send_completion_notification(mock_discord_config):
    """
    Test the send_completion_notification method of DiscordNotifier.
    
    This test ensures that the method correctly sends the completion message
    to the Discord webhook.
    """
    with patch('aiohttp.ClientSession.post') as mock_post:
        mock_response = MagicMock()
        mock_response.status = 204
        mock_post.return_value.__aenter__.return_value = mock_response

        notifier = DiscordNotifier(mock_discord_config)
        result = await notifier.send_completion_notification()

        assert result is True
        mock_post.assert_called_once()
        _, kwargs = mock_post.call_args
        assert kwargs['json']['embeds'][0]['description'] == 'Move completed!'

@pytest.mark.asyncio
async def test_telegram_send_notification(mock_telegram_config):
    """
    Test the send_notification method of TelegramNotifier.
    
    This test ensures that the method correctly formats the notification message
    and sends it to the Telegram API.
    """
    with patch('aiohttp.ClientSession.post') as mock_post:
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json.return_value = {'ok': True}
        mock_post.return_value.__aenter__.return_value = mock_response

        notifier = TelegramNotifier(mock_telegram_config)
        result = await notifier.send_notification(50, '500 MB', '10 minutes')

        assert result is True
        mock_post.assert_called_once()
        _, kwargs = mock_post.call_args
        assert kwargs['json']['text'] == 'Moving: 50% complete, 500 MB remaining, ETC: 10 minutes'

@pytest.mark.asyncio
async def test_telegram_send_completion_notification(mock_telegram_config):
    """
    Test the send_completion_notification method of TelegramNotifier.
    
    This test ensures that the method correctly sends the completion message
    to the Telegram API.
    """
    with patch('aiohttp.ClientSession.post') as mock_post:
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json.return_value = {'ok': True}
        mock_post.return_value.__aenter__.return_value = mock_response

        notifier = TelegramNotifier(mock_telegram_config)
        result = await notifier.send_completion_notification()

        assert result is True
        mock_post.assert_called_once()
        _, kwargs = mock_post.call_args
        assert kwargs['json']['text'] == 'Move completed!'
