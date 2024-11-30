# tests/conftest.py

"""
Shared test fixtures and configuration for MoverStatus tests.
Provides mock configurations, factories, and utilities for testing.

Example:
    def test_monitor(mock_settings, mock_process):
        monitor = MoverMonitor(mock_settings)
        assert monitor.state == MonitorState.IDLE
"""


import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import (
    Any,
    AsyncGenerator,
    Callable,
    Dict,
    Generator,
    List,
)


import aiohttp
import pytest
import structlog
from _pytest.logging import LogCaptureFixture
from aioresponses import aioresponses
from pydantic import BaseModel
from pytest_mock import MockerFixture, MockFixture


from config.constants import ProcessState
from config.settings import Settings
from core.calculator import TransferStats
from core.monitor import MonitorState
from core.process import ProcessStats
from notifications.base import NotificationProvider
from notifications.discord.config import DiscordConfig
from notifications.telegram.config import TelegramConfig
from utils.version import Version

# Test data directory
TEST_DATA_DIR = Path(__file__).parent / "data"

# Fixtures: Basic test utilities
@pytest.fixture
def temp_dir(tmp_path: Path) -> Path:
    """Provide a temporary directory for test files.

    Args:
        tmp_path: pytest-provided temporary path

    Returns:
        Path: Temporary directory path
    """
    return tmp_path

@pytest.fixture
def load_test_data() -> Callable[[str], Dict[str, Any]]:
    """Create function to load test data files.

    Returns:
        Callable[[str], Dict[str, Any]]: Function to load test data
    """
    def _load_data(filename: str) -> Dict[str, Any]:
        file_path = TEST_DATA_DIR / filename
        if not file_path.exists():
            raise FileNotFoundError(f"Test data file not found: {filename}")
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return _load_data

# Fixtures: Mock application components
@pytest.fixture
def mock_settings() -> Settings:
    """Create mock application settings.

    Returns:
        Settings: Mock settings instance with test configuration
    """
    return Settings(
        cache_path="/mnt/cache",
        notification_increment=25,
        debug_mode=True,
        discord=DiscordConfig(
            enabled=True,
            webhook_url="https://discord.com/api/webhooks/test"
        ),
        telegram=TelegramConfig(
            enabled=True,
            bot_token="123456:ABC-DEF",
            chat_id="-1001234567890"
        )
    )

@pytest.fixture
def mock_monitor_state() -> Dict[str, MonitorState]:
    """Create mock monitor state mapping.

    Returns:
        Dict[str, MonitorState]: Mapping of state names to MonitorState values
    """
    return {
        "idle": MonitorState.IDLE,
        "starting": MonitorState.STARTING,
        "monitoring": MonitorState.MONITORING,
        "error": MonitorState.ERROR,
        "stopped": MonitorState.STOPPED
    }

@pytest.fixture
def mock_process_stats() -> ProcessStats:
    """Create mock process statistics.

    Returns:
        ProcessStats: Mock process statistics with realistic test values
    """
    now = datetime.now()
    return ProcessStats(
        script_pid=12345,
        related_pids=[12346, 12347],
        total_cpu_percent=5.0,
        total_memory_percent=2.0,
        io_read_bytes=1024 * 1024,  # 1 MB
        io_write_bytes=2048 * 1024,  # 2 MB
        start_time=now,
        command_line="/usr/local/sbin/mover",
        nice_level=10,
        io_class="best-effort"
    )

@pytest.fixture
def mock_transfer_stats() -> TransferStats:
    """Create mock transfer statistics.

    Returns:
        TransferStats: Mock transfer statistics with realistic test values
    """
    now = datetime.now()
    return TransferStats(
        initial_size=10 * 1024 * 1024 * 1024,  # 10 GB
        current_size=5 * 1024 * 1024 * 1024,   # 5 GB
        bytes_moved=5 * 1024 * 1024 * 1024,    # 5 GB
        transfer_rate=100 * 1024 * 1024,       # 100 MB/s
        percent_complete=50.0,
        start_time=now,
        estimated_completion=now + timedelta(hours=1)
    )

# Fixtures: Mock network components
@pytest.fixture
def mock_notification_provider() -> NotificationProvider:
    """Create mock notification provider.

    Returns:
        NotificationProvider: Mock provider instance with message tracking
    """
    class MockProvider(NotificationProvider):
        def __init__(self) -> None:
            super().__init__()
            self.sent_messages: List[str] = []

        async def send_notification(self, message: str) -> bool:
            self.sent_messages.append(message)
            return True

        def _format_message(self, message: str) -> Dict[str, Any]:
            return {"text": message}

    return MockProvider()

@pytest.fixture
async def mock_aiohttp_session() -> AsyncGenerator[aiohttp.ClientSession, None]:
    """Create mock aiohttp session.

    Yields:
        AsyncGenerator[aiohttp.ClientSession, None]: Mock session for testing
    """
    async with aiohttp.ClientSession() as session:
        yield session

@pytest.fixture
def mock_responses() -> Generator[aioresponses, None, None]:
    """Create mock aiohttp responses.

    Yields:
        Generator[aioresponses, None, None]: Mock response manager for testing
    """
    with aioresponses() as m:
        yield m

# Fixtures: Mock system components
@pytest.fixture
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create event loop for async tests.

    Yields:
        Generator[asyncio.AbstractEventLoop, None, None]: Test event loop
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()

@pytest.fixture
def mock_logger(caplog: LogCaptureFixture) -> structlog.BoundLogger:
    """Create mock structured logger.

    Args:
        caplog: pytest log capture fixture

    Returns:
        structlog.BoundLogger: Configured test logger
    """
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    return structlog.get_logger()

@pytest.fixture
def mock_process_manager(mocker: MockerFixture) -> Generator[MockFixture, None, None]:
    """Mock process manager.

    Args:
        mocker: pytest mocker fixture

    Yields:
        Generator[MockFixture, None, None]: Configured process manager mock
    """
    mock = mocker.patch("core.process.ProcessManager")
    mock.return_value.current_state = ProcessState.RUNNING
    mock.return_value.is_running = mocker.AsyncMock(return_value=True)
    yield mock

@pytest.fixture
def assert_called_with_delay() -> Callable[[MockFixture, float], None]:
    """Create assertion helper for delayed function calls.

    Returns:
        Callable[[MockFixture, float], None]: Assertion helper function
    """
    async def _assert_delay(mock_func: MockFixture, expected_delay: float) -> None:
        """Assert that a mock was called with a specific delay.

        Args:
            mock_func: Mock function to check
            expected_delay: Expected delay in seconds

        Raises:
            AssertionError: If the actual delay differs from expected by more than 0.1s
        """
        call_times = [call[0][0] for call in mock_func.await_args_list]
        actual_delay = (call_times[-1] - call_times[0]).total_seconds()
        assert abs(actual_delay - expected_delay) < 0.1, (
            f"Expected delay of {expected_delay}s, got {actual_delay}s"
        )

    return _assert_delay

# Fixtures: Mock HTTP components
class MockResponse(BaseModel):
    """Mock HTTP response model."""
    status: int = 200
    data: Dict[str, Any] = {}

    def json(self) -> Dict[str, Any]:
        """Get response data as JSON.

        Returns:
            Dict[str, Any]: Response data
        """
        return self.data

@pytest.fixture
def mock_http_response() -> MockResponse:
    """Create mock HTTP response.

    Returns:
        MockResponse: Mock response instance
    """
    return MockResponse()

@pytest.fixture
def version_response() -> Dict[str, Any]:
    """Create mock version response data.

    Returns:
        Dict[str, Any]: Version response data
    """
    return {
        "tag_name": "v0.1.0",
        "name": "Release 0.1.0",
        "body": "Test release",
        "draft": False,
        "prerelease": False
    }

@pytest.fixture
def mock_version(mocker: MockerFixture) -> Version:
    """Create mock version instance.

    Args:
        mocker: pytest mocker fixture

    Returns:
        Version: Mock version instance
    """
    version = Version(major=0, minor=1, patch=0)
    mocker.patch("utils.version.Version.from_string", return_value=version)
    return version

# Initialize test environment
TEST_DATA_DIR.mkdir(exist_ok=True)
