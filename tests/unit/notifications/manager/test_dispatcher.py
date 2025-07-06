"""Tests for the async dispatch infrastructure."""

from __future__ import annotations

import asyncio
import pytest
from typing import TYPE_CHECKING, override
from collections.abc import Mapping

from mover_status.notifications.manager.dispatcher import (
    AsyncDispatcher,
    DispatchStatus,
    MessageQueue,
    WorkerPool,
    DeliveryTracker,
    QueuedMessage,
    BatchProcessor,
)
from mover_status.notifications.base.provider import NotificationProvider
from mover_status.notifications.models.message import Message

if TYPE_CHECKING:
    pass


class MockProvider(NotificationProvider):
    """Mock provider for testing."""
    
    def __init__(self, config: Mapping[str, object], name: str = "mock") -> None:
        super().__init__(config)
        self.name: str = name
        self.send_calls: list[Message] = []
        self.should_fail: bool = False
        self.delay: float = 0.0
        
    @override
    async def send_notification(self, message: Message) -> bool:
        """Mock send notification."""
        if self.delay > 0:
            await asyncio.sleep(self.delay)
        self.send_calls.append(message)
        if self.should_fail:
            raise Exception(f"Mock failure from {self.name}")
        return True
        
    @override
    def validate_config(self) -> None:
        """Mock validate config."""
        pass
        
    @override
    def get_provider_name(self) -> str:
        """Mock get provider name."""
        return self.name


class TestMessageQueue:
    """Test cases for MessageQueue."""
    
    @pytest.mark.asyncio
    async def test_queue_basic_operations(self) -> None:
        """Test basic queue operations."""
        queue = MessageQueue(max_size=10)
        message = Message(title="Test", content="Test content")
        queued_msg = QueuedMessage(message=message, priority=1, providers=["test"])
        
        # Test enqueue
        await queue.enqueue(queued_msg)
        assert queue.size() == 1
        assert not queue.is_empty()
        
        # Test dequeue
        result = await queue.dequeue()
        assert result == queued_msg
        assert queue.size() == 0
        assert queue.is_empty()
    
    @pytest.mark.asyncio
    async def test_queue_priority_ordering(self) -> None:
        """Test that messages are dequeued by priority."""
        queue = MessageQueue(max_size=10)
        
        # Add messages with different priorities
        low_msg = QueuedMessage(
            message=Message(title="Low", content="Low priority"),
            priority=1,
            providers=["test"]
        )
        high_msg = QueuedMessage(
            message=Message(title="High", content="High priority"),
            priority=3,
            providers=["test"]
        )
        medium_msg = QueuedMessage(
            message=Message(title="Medium", content="Medium priority"),
            priority=2,
            providers=["test"]
        )
        
        # Enqueue in random order
        await queue.enqueue(low_msg)
        await queue.enqueue(high_msg)
        await queue.enqueue(medium_msg)
        
        # Should dequeue in priority order (highest first)
        assert (await queue.dequeue()) == high_msg
        assert (await queue.dequeue()) == medium_msg
        assert (await queue.dequeue()) == low_msg
    
    @pytest.mark.asyncio
    async def test_queue_max_size_limit(self) -> None:
        """Test queue size limits."""
        queue = MessageQueue(max_size=2)
        message = Message(title="Test", content="Test content")
        
        # Fill queue to capacity
        await queue.enqueue(QueuedMessage(message=message, priority=1, providers=["test"]))
        await queue.enqueue(QueuedMessage(message=message, priority=1, providers=["test"]))
        
        # Should be at capacity
        assert queue.size() == 2
        assert queue.is_full()
        
        # Adding another should block (we'll test with timeout)
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(
                queue.enqueue(QueuedMessage(message=message, priority=1, providers=["test"])),
                timeout=0.1
            )


class TestWorkerPool:
    """Test cases for WorkerPool."""
    
    @pytest.mark.asyncio
    async def test_worker_pool_basic_operations(self) -> None:
        """Test basic worker pool operations."""
        pool = WorkerPool(max_workers=2)
        
        # Test initial state
        assert pool.active_workers == 0
        assert pool.max_workers == 2
        
        # Test starting workers
        await pool.start()
        assert pool.active_workers == 2
        
        # Test stopping workers
        await pool.stop()
        assert pool.active_workers == 0
    
    @pytest.mark.asyncio
    async def test_worker_pool_task_processing(self) -> None:
        """Test that worker pool processes tasks."""
        pool = WorkerPool(max_workers=1)
        results: list[int] = []

        async def test_task(value: int) -> int:
            results.append(value)
            return value * 2
        
        await pool.start()
        
        # Submit tasks
        future1 = await pool.submit_task(test_task, 1)
        future2 = await pool.submit_task(test_task, 2)
        
        # Wait for completion
        result1 = await future1
        result2 = await future2
        
        assert result1 == 2
        assert result2 == 4
        assert sorted(results) == [1, 2]
        
        await pool.stop()


class TestDeliveryTracker:
    """Test cases for DeliveryTracker."""
    
    def test_delivery_tracker_basic_operations(self) -> None:
        """Test basic delivery tracking operations."""
        tracker = DeliveryTracker()
        message = Message(title="Test", content="Test content")
        
        # Test tracking new delivery
        delivery_id = tracker.track_delivery(message, ["provider1", "provider2"])
        assert delivery_id is not None
        
        # Test getting delivery status
        status = tracker.get_delivery_status(delivery_id)
        assert status is not None
        assert status.message == message
        assert status.providers == ["provider1", "provider2"]
        assert status.status == DispatchStatus.PENDING
    
    def test_delivery_tracker_status_updates(self) -> None:
        """Test delivery status updates."""
        tracker = DeliveryTracker()
        message = Message(title="Test", content="Test content")
        
        delivery_id = tracker.track_delivery(message, ["provider1"])
        
        # Test successful delivery
        tracker.update_delivery_status(delivery_id, "provider1", True, None)
        status = tracker.get_delivery_status(delivery_id)
        assert status is not None
        assert status.status == DispatchStatus.SUCCESS
        assert "provider1" in status.results
        assert status.results["provider1"].success is True
    
    def test_delivery_tracker_failed_delivery(self) -> None:
        """Test failed delivery tracking."""
        tracker = DeliveryTracker()
        message = Message(title="Test", content="Test content")
        
        delivery_id = tracker.track_delivery(message, ["provider1"])
        
        # Test failed delivery
        error = Exception("Test error")
        tracker.update_delivery_status(delivery_id, "provider1", False, error)
        status = tracker.get_delivery_status(delivery_id)
        assert status is not None
        assert status.status == DispatchStatus.FAILED
        assert "provider1" in status.results
        assert status.results["provider1"].success is False
        assert status.results["provider1"].error == error


class TestAsyncDispatcher:
    """Test cases for AsyncDispatcher."""
    
    @pytest.mark.asyncio
    async def test_dispatcher_basic_dispatch(self) -> None:
        """Test basic message dispatch."""
        dispatcher = AsyncDispatcher(max_workers=2, queue_size=10)
        provider = MockProvider({"enabled": True}, "test_provider")
        
        # Register provider
        dispatcher.register_provider("test_provider", provider)
        
        # Start dispatcher
        await dispatcher.start()
        
        # Dispatch message
        message = Message(title="Test", content="Test content")
        result = await dispatcher.dispatch_message(message, ["test_provider"])
        
        # Verify dispatch
        assert result.delivery_id is not None
        assert result.status == DispatchStatus.SUCCESS
        assert len(provider.send_calls) == 1
        assert provider.send_calls[0] == message
        
        await dispatcher.stop()
    
    @pytest.mark.asyncio
    async def test_dispatcher_multiple_providers(self) -> None:
        """Test dispatch to multiple providers."""
        dispatcher = AsyncDispatcher(max_workers=2, queue_size=10)
        provider1 = MockProvider({"enabled": True}, "provider1")
        provider2 = MockProvider({"enabled": True}, "provider2")
        
        # Register providers
        dispatcher.register_provider("provider1", provider1)
        dispatcher.register_provider("provider2", provider2)
        
        await dispatcher.start()
        
        # Dispatch to both providers
        message = Message(title="Test", content="Test content")
        result = await dispatcher.dispatch_message(message, ["provider1", "provider2"])
        
        # Verify both providers received the message
        assert result.status == DispatchStatus.SUCCESS
        assert len(provider1.send_calls) == 1
        assert len(provider2.send_calls) == 1
        
        await dispatcher.stop()
    
    @pytest.mark.asyncio
    async def test_dispatcher_failed_provider(self) -> None:
        """Test dispatch with failing provider."""
        dispatcher = AsyncDispatcher(max_workers=2, queue_size=10)
        provider = MockProvider({"enabled": True}, "failing_provider")
        provider.should_fail = True
        
        dispatcher.register_provider("failing_provider", provider)
        await dispatcher.start()
        
        message = Message(title="Test", content="Test content")
        result = await dispatcher.dispatch_message(message, ["failing_provider"])
        
        # Should still complete but with failed status
        assert result.status == DispatchStatus.FAILED
        
        await dispatcher.stop()


class TestBatchProcessor:
    """Test cases for BatchProcessor."""
    
    @pytest.mark.asyncio
    async def test_batch_processor_basic_batching(self) -> None:
        """Test basic batch processing."""
        processor = BatchProcessor(batch_size=3, batch_timeout=1.0)
        results: list[QueuedMessage] = []

        async def process_batch(messages: list[QueuedMessage]) -> None:
            results.extend(messages)
        
        processor.set_batch_handler(process_batch)
        await processor.start()
        
        # Add messages to batch
        for i in range(3):
            message = Message(title=f"Test {i}", content=f"Content {i}")
            queued_msg = QueuedMessage(message=message, priority=1, providers=["test"])
            await processor.add_to_batch(queued_msg)
        
        # Wait for batch processing
        await asyncio.sleep(0.1)
        
        # Should have processed all 3 messages
        assert len(results) == 3
        
        await processor.stop()
    
    @pytest.mark.asyncio
    async def test_batch_processor_timeout_batching(self) -> None:
        """Test batch processing with timeout."""
        processor = BatchProcessor(batch_size=10, batch_timeout=0.1)
        results: list[QueuedMessage] = []

        async def process_batch(messages: list[QueuedMessage]) -> None:
            results.extend(messages)
        
        processor.set_batch_handler(process_batch)
        await processor.start()
        
        # Add only 2 messages (less than batch size)
        for i in range(2):
            message = Message(title=f"Test {i}", content=f"Content {i}")
            queued_msg = QueuedMessage(message=message, priority=1, providers=["test"])
            await processor.add_to_batch(queued_msg)
        
        # Wait for timeout
        await asyncio.sleep(0.2)
        
        # Should have processed 2 messages due to timeout
        assert len(results) == 2
        
        await processor.stop()
