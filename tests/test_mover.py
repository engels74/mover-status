# tests/test_mover.py
import pytest
from unittest.mock import Mock, patch
from mover.monitor import MoverMonitor
from notifiers.base import BaseNotifier

@pytest.fixture
def mock_config():
    """
    Fixture that provides a mock configuration for testing.
    
    This configuration mimics the structure of the actual config,
    but with simplified values for testing purposes.
    """
    return {
        'mover': {
            'executable': 'mover',
            'cache_path': '/mnt/cache'
        },
        'exclude_paths': [],
        'notifications': {
            'increment': 25
        },
        'debug': {
            'dry_run': False
        }
    }

@pytest.fixture
def mock_notifier():
    """
    Fixture that provides a mock notifier for testing.
    
    This mock notifier adheres to the BaseNotifier interface
    and returns True for all notification methods.
    """
    notifier = Mock(spec=BaseNotifier)
    notifier.send_notification.return_value = True
    notifier.send_completion_notification.return_value = True
    return notifier

@pytest.mark.asyncio
async def test_mover_monitor_initialization(mock_config, mock_notifier):
    """
    Test the initialization of the MoverMonitor class.
    
    Ensures that the MoverMonitor is correctly initialized with
    the provided configuration and notifier.
    """
    monitor = MoverMonitor(mock_config, [mock_notifier])
    assert monitor.mover_executable == 'mover'
    assert monitor.cache_path == '/mnt/cache'
    assert monitor.notification_increment == 25
    assert not monitor.dry_run

@pytest.mark.asyncio
async def test_is_mover_running(mock_config, mock_notifier):
    """
    Test the _is_mover_running method of MoverMonitor.
    
    This test mocks the subprocess call and ensures that the method
    correctly interprets the subprocess output.
    """
    with patch('asyncio.create_subprocess_shell') as mock_subprocess:
        mock_subprocess.return_value.communicate.return_value = (b'123', b'')
        monitor = MoverMonitor(mock_config, [mock_notifier])
        result = await monitor._is_mover_running()
        assert result is True

@pytest.mark.asyncio
async def test_get_cache_size(mock_config, mock_notifier):
    """
    Test the _get_cache_size method of MoverMonitor.
    
    This test mocks the subprocess call and ensures that the method
    correctly interprets the subprocess output to get the cache size.
    """
    with patch('asyncio.create_subprocess_shell') as mock_subprocess:
        mock_subprocess.return_value.communicate.return_value = (b'1000000', b'')
        monitor = MoverMonitor(mock_config, [mock_notifier])
        size = await monitor._get_cache_size()
        assert size == 1000000

@pytest.mark.asyncio
async def test_send_notifications(mock_config, mock_notifier):
    """
    Test the _send_notifications method of MoverMonitor.
    
    This test ensures that the method correctly calls the send_notification
    method of the provided notifier with the correct arguments.
    """
    monitor = MoverMonitor(mock_config, [mock_notifier])
    await monitor._send_notifications(50, '500 MB', '10 minutes')
    mock_notifier.send_notification.assert_called_once_with(50, '500 MB', '10 minutes')

@pytest.mark.asyncio
async def test_send_completion_notifications(mock_config, mock_notifier):
    """
    Test the _send_completion_notifications method of MoverMonitor.
    
    This test ensures that the method correctly calls the send_completion_notification
    method of the provided notifier.
    """
    monitor = MoverMonitor(mock_config, [mock_notifier])
    await monitor._send_completion_notifications()
    mock_notifier.send_completion_notification.assert_called_once()
