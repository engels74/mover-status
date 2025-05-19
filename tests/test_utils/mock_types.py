"""
Type definitions for unittest.mock objects.

This module provides type definitions for unittest.mock objects to improve type checking.
"""

from typing import Protocol, TypeVar

T = TypeVar('T')


class CallArgs(tuple[tuple[str, ...], dict[str, str | int]]):
    """Type definition for unittest.mock call_args."""
    pass


class MockMethod(Protocol):
    """Protocol for mock methods."""
    def __call__(self, msg: str) -> None: ...
    def assert_called_once(self) -> None: ...
    def assert_called_with(self, msg: str) -> None: ...
    def assert_any_call(self, msg: str) -> None: ...
    def assert_not_called(self) -> None: ...
    call_args: CallArgs
