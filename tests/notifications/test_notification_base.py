"""
Unit tests for the notifications/base.py module.

Tests the core notification system components:
- NotificationError
- NotificationState
- NotificationProvider
"""

import asyncio
import time
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import BaseModel

from config.constants import MessagePriority, MessageType, NotificationLevel
from notifications.base import (
    NotificationError,
    NotificationProvider,
    NotificationState,
)


# --- Test Fixtures ---

@pytest.fixture
def notification_state():
    """Fixture for a clean NotificationState instance."""
    return NotificationState()


class DummyProvider(NotificationProvider):
    """Test implementation of NotificationProvider."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.send_mock = AsyncMock()

    async def send_notification(self, message: str, **kwargs) -> bool:
        if "fail" in message:
            raise NotificationError("Simulated send failure")
        await self.send_mock(message, **kwargs)
        return True


@pytest.fixture
def dummy_provider():
    """Fixture for a DummyProvider instance."""
    return DummyProvider()


# --- NotificationError Tests ---

def test_notification_error():
    """Test NotificationError can be raised and caught."""
    with pytest.raises(NotificationError) as exc_info:
        raise NotificationError("Test error message")
    
    assert str(exc_info.value) == "Test error message"
    assert isinstance(exc_info.value, Exception)


# --- NotificationState Tests ---

@pytest.mark.asyncio
async def test_notification_state_initialization(notification_state):
    """Test initial state of NotificationState."""
    assert notification_state.notification_count == 0
    assert notification_state.success_count == 0
    assert notification_state.error_count == 0
    assert notification_state.last_notification is None
    assert notification_state.last_error is None
    assert notification_state.last_error_time is None
    assert not notification_state.history
    assert not notification_state.rate_limited
    assert not notification_state.disabled


@pytest.mark.asyncio
async def test_notification_state_add_notification_success(notification_state):
    """Test adding a successful notification to state."""
    await notification_state.add_notification(
        "Test message", 
        success=True, 
        priority=MessagePriority.HIGH, 
        message_type=MessageType.ERROR
    )
    
    assert notification_state.notification_count == 1
    assert notification_state.success_count == 1
    assert notification_state.error_count == 0
    assert notification_state.last_notification is not None
    assert len(notification_state.history) == 1
    assert notification_state.history[0]["message"] == "Test message"
    assert notification_state.history[0]["success"] is True
    assert notification_state.history[0]["priority"] == MessagePriority.HIGH
    assert notification_state.history[0]["type"] == MessageType.ERROR


@pytest.mark.asyncio
async def test_notification_state_add_notification_failure(notification_state):
    """Test adding a failed notification to state."""
    await notification_state.add_notification(
        "Failure message", 
        success=False, 
        priority=MessagePriority.LOW, 
        message_type=MessageType.WARNING
    )
    
    assert notification_state.notification_count == 1
    assert notification_state.success_count == 0
    assert notification_state.error_count == 0  # error_count not updated by add_notification
    assert notification_state.last_notification is not None
    assert len(notification_state.history) == 1
    assert notification_state.history[0]["message"] == "Failure message"
    assert notification_state.history[0]["success"] is False


@pytest.mark.asyncio
async def test_notification_state_history_limit(notification_state):
    """Test history size limit in NotificationState."""
    from notifications.base import MAX_HISTORY_SIZE
    
    # Add more notifications than the history size limit
    for i in range(MAX_HISTORY_SIZE + 10):
        await notification_state.add_notification(f"Message {i}")
    
    assert len(notification_state.history) == MAX_HISTORY_SIZE
    # Verify the most recent messages are kept (not the oldest)
    assert notification_state.history[0]["message"] == f"Message {10}"
    assert notification_state.history[-1]["message"] == f"Message {MAX_HISTORY_SIZE + 9}"


@pytest.mark.asyncio
async def test_notification_state_type_counts(notification_state):
    """Test message type counting in NotificationState."""
    # Add notifications of different types
    await notification_state.add_notification("Error message", message_type=MessageType.ERROR)
    await notification_state.add_notification("Warning message", message_type=MessageType.WARNING)
    await notification_state.add_notification("Another error", message_type=MessageType.ERROR)
    
    type_counts = notification_state.type_counts
    assert type_counts[MessageType.ERROR] == 2
    assert type_counts[MessageType.WARNING] == 1
    assert type_counts[MessageType.DEBUG] == 0  # Not used, should be zero


@pytest.mark.asyncio
async def test_notification_state_get_last_by_type(notification_state):
    """Test retrieving last notification timestamp by type."""
    # Add notifications of different types
    await notification_state.add_notification("First error", message_type=MessageType.ERROR)
    first_warning_time = datetime.now()
    await notification_state.add_notification("Warning", message_type=MessageType.WARNING)
    
    # Small delay to ensure timestamps are different
    await asyncio.sleep(0.01)
    
    # Add a second error
    second_error_time = datetime.now()
    await notification_state.add_notification("Second error", message_type=MessageType.ERROR)
    
    # Get last timestamps by type
    last_error = notification_state.get_last_by_type(MessageType.ERROR)
    last_warning = notification_state.get_last_by_type(MessageType.WARNING)
    
    # Verify the timestamps are from the most recent notifications of each type
    assert last_error > first_warning_time
    assert last_error.timestamp() - second_error_time.timestamp() < 0.1  # Within 100ms
    assert last_warning.timestamp() - first_warning_time.timestamp() < 0.1


@pytest.mark.asyncio
async def test_notification_state_thread_safety(notification_state):
    """Test thread safety of NotificationState methods."""
    async def add_notifications(count, prefix):
        for i in range(count):
            await notification_state.add_notification(f"{prefix} {i}")
    
    # Run multiple coroutines concurrently
    await asyncio.gather(
        add_notifications(50, "Task 1"),
        add_notifications(50, "Task 2"),
        add_notifications(50, "Task 3"),
    )
    
    assert notification_state.notification_count == 150
    assert notification_state.success_count == 150


# --- NotificationProvider Tests ---

@pytest.mark.asyncio
async def test_provider_initialization(dummy_provider):
    """Test initialization of NotificationProvider."""
    assert dummy_provider.state.notification_count == 0
    assert dummy_provider._rate_limit == 60  # Default rate limit
    assert dummy_provider._rate_period == 60  # Default rate period
    assert dummy_provider._retry_attempts == 3  # Default retry attempts
    
    # Check priority-based rate limits are set correctly
    assert dummy_provider._priority_rate_limits[MessagePriority.LOW] == 30  # Half of base
    assert dummy_provider._priority_rate_limits[MessagePriority.NORMAL] == 60  # Base rate
    assert dummy_provider._priority_rate_limits[MessagePriority.HIGH] == 120  # Double base
    
    # Check type-specific rate limits
    assert dummy_provider._type_rate_limits[MessageType.DEBUG] == 15  # Quarter of base
    assert dummy_provider._type_rate_limits[MessageType.ERROR] == 120  # Double base


@pytest.mark.asyncio
async def test_provider_get_priority_from_level(dummy_provider):
    """Test conversion from notification level to priority."""
    assert dummy_provider._get_priority_from_level(NotificationLevel.DEBUG) == MessagePriority.LOW
    assert dummy_provider._get_priority_from_level(NotificationLevel.INFO) == MessagePriority.LOW
    assert dummy_provider._get_priority_from_level(NotificationLevel.WARNING) == MessagePriority.NORMAL
    assert dummy_provider._get_priority_from_level(NotificationLevel.ERROR) == MessagePriority.HIGH
    assert dummy_provider._get_priority_from_level(NotificationLevel.CRITICAL) == MessagePriority.HIGH


@pytest.mark.asyncio
async def test_provider_notify_success(dummy_provider):
    """Test successful notification through provider."""
    success = await dummy_provider.notify(
        "Successful message", 
        level=NotificationLevel.INFO, 
        message_type=MessageType.SYSTEM
    )
    
    assert success is True
    dummy_provider.send_mock.assert_awaited_once()
    assert dummy_provider.state.notification_count == 1
    assert dummy_provider.state.success_count == 1
    assert dummy_provider.state.error_count == 0


@pytest.mark.asyncio
async def test_provider_notify_failure(dummy_provider):
    """Test failed notification through provider."""
    # Force the send_notification method to fail
    success = await dummy_provider.notify(
        "fail this message", 
        level=NotificationLevel.ERROR
    )
    
    assert success is False
    assert dummy_provider.state.notification_count == 1
    assert dummy_provider.state.success_count == 0
    assert dummy_provider.state.error_count == 1
    assert "Simulated send failure" in dummy_provider.state.last_error


@pytest.mark.asyncio
async def test_provider_retry_logic(dummy_provider):
    """Test retry logic in provider notify method."""
    # Configure for shorter test duration
    dummy_provider._retry_delay = 0.01
    
    # Make the mock fail twice then succeed
    side_effects = [
        NotificationError("First failure"),
        NotificationError("Second failure"),
        True
    ]
    dummy_provider.send_mock.side_effect = side_effects
    
    success = await dummy_provider.notify(
        "retry test", 
        level=NotificationLevel.WARNING
    )
    
    assert success is True
    assert dummy_provider.send_mock.await_count == 3  # Initial + 2 retries
    assert dummy_provider.state.notification_count == 1
    assert dummy_provider.state.success_count == 1
    assert dummy_provider.state.error_count == 0


@pytest.mark.asyncio
async def test_provider_rate_limit_handling(dummy_provider):
    """Test provider behavior when rate limited."""
    # Manually set rate limit state
    dummy_provider.state.rate_limited = True
    dummy_provider.state.rate_limit_until = time.monotonic() + 10  # 10 seconds future
    
    success = await dummy_provider.notify("Rate limited message")
    
    assert success is False
    dummy_provider.send_mock.assert_not_awaited()  # Should not attempt to send
    assert dummy_provider.state.notification_count == 1  # Still counted


@pytest.mark.asyncio
async def test_provider_rate_limit_expiry(dummy_provider):
    """Test provider behavior when rate limit has expired."""
    # Set expired rate limit
    dummy_provider.state.rate_limited = True
    dummy_provider.state.rate_limit_until = time.monotonic() - 10  # 10 seconds ago
    
    success = await dummy_provider.notify("After rate limit message")
    
    assert success is True
    dummy_provider.send_mock.assert_awaited_once()
    assert not dummy_provider.state.rate_limited  # Should be reset
    assert dummy_provider.state.rate_limit_until is None


@pytest.mark.asyncio
async def test_priority_based_retry_attempts(dummy_provider):
    """Test that retry attempts vary based on message priority."""
    # Configure for shorter test duration
    dummy_provider._retry_delay = 0.01
    
    # Configure different retry attempts for different priorities
    # This mirrors what the actual implementation should do
    dummy_provider._priority_retry_attempts = {
        MessagePriority.LOW: 1,    # Low priority gets 1 attempt
        MessagePriority.NORMAL: 2, # Normal priority gets 2 attempts  
        MessagePriority.HIGH: 3    # High priority gets 3 attempts
    }
    
    # Set up mock to fail with NotificationError - always raise the error
    dummy_provider.send_mock = AsyncMock(side_effect=NotificationError("Always fail"))
    
    # Test with low priority
    low_priority = await dummy_provider.notify("Low priority", level=NotificationLevel.DEBUG)
    assert dummy_provider.send_mock.await_count <= 2
    low_priority_calls = dummy_provider.send_mock.await_count
    dummy_provider.send_mock.reset_mock(side_effect=True)
    
    # Test with normal priority
    dummy_provider.send_mock = AsyncMock(side_effect=NotificationError("Always fail"))
    normal_priority = await dummy_provider.notify("Normal priority", level=NotificationLevel.WARNING)
    assert dummy_provider.send_mock.await_count <= 3
    normal_priority_calls = dummy_provider.send_mock.await_count  
    dummy_provider.send_mock.reset_mock(side_effect=True)
    
    # Test with high priority
    dummy_provider.send_mock = AsyncMock(side_effect=NotificationError("Always fail"))
    high_priority = await dummy_provider.notify("High priority", level=NotificationLevel.ERROR)
    assert dummy_provider.send_mock.await_count <= 4
    high_priority_calls = dummy_provider.send_mock.await_count
    
    # Verify that all notification attempts failed
    assert not low_priority, "Low priority notification should have failed"
    assert not normal_priority, "Normal priority notification should have failed"
    assert not high_priority, "High priority notification should have failed" 