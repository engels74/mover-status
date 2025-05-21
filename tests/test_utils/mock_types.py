"""
Type definitions for unittest.mock objects.

This module provides type definitions for unittest.mock objects to improve type checking.
"""

# pyright: reportAny=false
# pyright: reportExplicitAny=false
# pyright: reportUninitializedInstanceVariable=false

from typing import Any, Protocol, TypeVar, Callable, TypeAlias
from argparse import Namespace

T = TypeVar('T')
K = TypeVar('K', bound=str)
V = TypeVar('V')


# Define a type alias for call_args that can be unpacked
CallArgs: TypeAlias = tuple[tuple[object, ...], dict[str, object]]


class MockMethod(Protocol):
    """Protocol for mock methods."""
    def __call__(self, *args: Any, **kwargs: Any) -> None: ...
    def assert_called_once(self) -> None: ...
    def assert_called_with(self, *args: Any, **kwargs: Any) -> None: ...
    def assert_called_once_with(self, *args: Any, **kwargs: Any) -> None: ...
    def assert_any_call(self, *args: Any, **kwargs: Any) -> None: ...
    def assert_not_called(self) -> None: ...
    call_args: CallArgs
    call_count: int
    side_effect: Any


class MockConfig(Protocol):
    """Protocol for mocked Config objects."""
    get_nested_value: Callable[[str], Any]


class MockConfigManager(Protocol):
    """Protocol for mocked ConfigManager objects."""
    load: Callable[[], Any]
    config: MockConfig


class MockLoggerConfig(Protocol):
    """Protocol for mocked LoggerConfig objects."""
    console_enabled: bool
    level: Any
    format: Any


class MockNotificationManager(Protocol):
    """Protocol for mocked NotificationManager."""
    def register_provider(self, provider: Any) -> None: ...
    def send_notification(self, message: str, **kwargs: Any) -> bool: ...


class MockMonitorSession(Protocol):
    """Protocol for mocked MonitorSession."""
    def run_monitoring_loop(self, notification_manager: Any) -> None: ...


class MockLogger(Protocol):
    """Protocol for mocked logger."""
    def info(self, msg: str, *args: Any, **kwargs: Any) -> None: ...
    def error(self, msg: str, *args: Any, **kwargs: Any) -> None: ...
    def warning(self, msg: str, *args: Any, **kwargs: Any) -> None: ...
    def debug(self, msg: str, *args: Any, **kwargs: Any) -> None: ...


class MockProvider(Protocol):
    """Protocol for mocked notification providers."""
    enabled: bool
    def validate_config(self) -> list[str]: ...


class ArgsNamespace(Namespace):
    """Type definition for argparse.Namespace with our specific arguments."""
    config: str | None
    version: bool
    help: bool
    dry_run: bool
    debug: bool
