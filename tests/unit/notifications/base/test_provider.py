"""Test cases for the abstract notification provider base class."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, override, TypeVar, ParamSpec, Callable
from collections.abc import Mapping, Awaitable
from functools import wraps

import pytest

from mover_status.notifications.base.provider import (
    NotificationProvider,
    with_retry,
)
from mover_status.notifications.models.message import Message


P = ParamSpec("P")
T = TypeVar("T")

def generic_retry(max_attempts: int = 3, backoff_factor: float = 0.1) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T | None]]]:
    """Generic retry decorator for testing."""
    def decorator(func: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T | None]]:
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T | None:
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except Exception:
                    if attempt == max_attempts - 1:
                        raise
                    wait_time = backoff_factor ** attempt
                    await asyncio.sleep(wait_time)
            return None
        return wrapper
    return decorator

if TYPE_CHECKING:
    pass


class MockProvider(NotificationProvider):
    """Mock implementation of NotificationProvider for testing."""
    
    def __init__(self, config: Mapping[str, object]) -> None:
        super().__init__(config)
        self.send_call_count: int = 0
        self.should_fail: bool = False
        self.failure_count: int = 0
        
    @override
    async def send_notification(self, message: Message) -> bool:
        """Mock implementation that can be configured to fail."""
        self.send_call_count += 1
        if self.should_fail and self.failure_count < 2:
            self.failure_count += 1
            raise Exception("Mock failure")
        return True
    
    @override
    def validate_config(self) -> None:
        """Mock validation that checks for required fields."""
        if 'required_field' not in self.config:
            raise ValueError("Missing required_field in config")
    
    @override
    def get_provider_name(self) -> str:
        """Return the mock provider name."""
        return "mock_provider"


class TestNotificationProvider:
    """Test cases for the NotificationProvider abstract base class."""
    
    def test_provider_interface(self) -> None:
        """Test that the abstract provider interface is properly defined."""
        config = {"enabled": True, "required_field": "test"}
        provider = MockProvider(config)
        
        assert provider.config == config
        assert provider.enabled is True
        assert provider.get_provider_name() == "mock_provider"
    
    def test_provider_disabled_by_default(self) -> None:
        """Test that provider can be disabled via config."""
        config = {"enabled": False, "required_field": "test"}
        provider = MockProvider(config)
        
        assert provider.enabled is False
    
    def test_provider_enabled_by_default(self) -> None:
        """Test that provider is enabled by default if not specified."""
        config = {"required_field": "test"}
        provider = MockProvider(config)
        
        assert provider.enabled is True
    
    def test_validate_config_success(self) -> None:
        """Test successful configuration validation."""
        config = {"required_field": "test"}
        provider = MockProvider(config)
        
        # Should not raise an exception
        provider.validate_config()
    
    def test_validate_config_failure(self) -> None:
        """Test configuration validation failure."""
        config = {"missing_field": "test"}
        provider = MockProvider(config)
        
        with pytest.raises(ValueError, match="Missing required_field in config"):
            provider.validate_config()
    
    @pytest.mark.asyncio
    async def test_send_notification_success(self) -> None:
        """Test successful notification sending."""
        config = {"required_field": "test"}
        provider = MockProvider(config)
        message = Message(
            title="Test Title",
            content="Test Content",
            priority="normal"
        )
        
        result = await provider.send_notification(message)
        
        assert result is True
        assert provider.send_call_count == 1
    
    @pytest.mark.asyncio
    async def test_send_notification_failure(self) -> None:
        """Test notification sending failure."""
        config = {"required_field": "test"}
        provider = MockProvider(config)
        provider.should_fail = True
        provider.failure_count = 0  # Reset failure count
        
        message = Message(
            title="Test Title",
            content="Test Content",
            priority="normal"
        )
        
        with pytest.raises(Exception, match="Mock failure"):
            _ = await provider.send_notification(message)


class TestRetryDecorator:
    """Test cases for the retry decorator."""
    
    @pytest.mark.asyncio
    async def test_retry_decorator_success_first_try(self) -> None:
        """Test retry decorator with successful first attempt."""
        call_count = 0
        
        @generic_retry(max_attempts=3, backoff_factor=0.1)
        async def test_function() -> str:
            nonlocal call_count
            call_count += 1
            return "success"
        
        result = await test_function()
        
        assert result == "success"
        assert call_count == 1
    
    @pytest.mark.asyncio
    async def test_retry_decorator_success_after_failures(self) -> None:
        """Test retry decorator with success after initial failures."""
        call_count = 0
        
        @generic_retry(max_attempts=3, backoff_factor=0.1)
        async def test_function() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Temporary failure")
            return "success"
        
        result = await test_function()
        
        assert result == "success"
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_retry_decorator_all_attempts_fail(self) -> None:
        """Test retry decorator when all attempts fail."""
        call_count = 0
        
        @generic_retry(max_attempts=3, backoff_factor=0.1)
        async def test_function() -> str:
            nonlocal call_count
            call_count += 1
            raise Exception("Persistent failure")
        
        with pytest.raises(Exception, match="Persistent failure"):
            _ = await test_function()
        
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_retry_decorator_backoff_timing(self) -> None:
        """Test that retry decorator implements exponential backoff."""
        call_count = 0
        start_time = asyncio.get_event_loop().time()
        
        @generic_retry(max_attempts=3, backoff_factor=0.1)
        async def test_function() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Temporary failure")
            return "success"
        
        result = await test_function()
        end_time = asyncio.get_event_loop().time()
        
        assert result == "success"
        assert call_count == 3
        # Should have waited at least 0.1 + 0.2 = 0.3 seconds
        assert end_time - start_time >= 0.3
    
    @pytest.mark.asyncio
    async def test_retry_decorator_preserves_function_metadata(self) -> None:
        """Test that retry decorator preserves function metadata."""
        @with_retry(max_attempts=3)
        async def test_function() -> bool:
            """Test docstring."""
            return True
        
        assert test_function.__name__ == "test_function"
        assert test_function.__doc__ == "Test docstring."
        _ = await test_function()  # Ensure it actually works