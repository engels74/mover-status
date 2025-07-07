"""Test suite for event bus implementation."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from unittest.mock import Mock

import pytest

from mover_status.core.monitor.event_bus import (
    Event,
    EventBus,
    EventFilter,
    EventHandler,
    EventPriority,
    EventPublisher,
    EventSubscriber,
    EventTopic,
    QueuedEvent,
    DeadLetterQueue,
    EventBusError,
    EventHandlerError,
    EventSubscriptionError,
)


@dataclass
class TestEvent:
    """Test event for testing purposes."""
    name: str
    data: dict[str, object] = field(default_factory=dict)


class TestEventBus:
    """Test cases for EventBus class."""
    
    def test_event_bus_initialization(self) -> None:
        """Test EventBus initialization."""
        bus = EventBus()
        assert bus is not None
        assert bus.is_running is False
        assert len(bus.subscribers) == 0
        assert len(bus.publishers) == 0
    
    def test_event_bus_start_stop(self) -> None:
        """Test EventBus start and stop functionality."""
        bus = EventBus()
        
        # Start the bus
        bus.start()
        assert bus.is_running is True
        
        # Stop the bus
        bus.stop()
        assert bus.is_running is False
    
    def test_event_bus_double_start_stop(self) -> None:
        """Test EventBus double start/stop safety."""
        bus = EventBus()
        
        # Double start should not raise error
        bus.start()
        bus.start()
        assert bus.is_running is True
        
        # Double stop should not raise error
        bus.stop()
        bus.stop()
        assert bus.is_running is False
    
    def test_subscriber_registration(self) -> None:
        """Test subscriber registration and unregistration."""
        bus = EventBus()
        handler = Mock()
        subscriber = EventSubscriber("test_topic", handler)
        
        # Register subscriber
        bus.register_subscriber(subscriber)
        assert len(bus.subscribers) == 1
        assert subscriber in bus.subscribers
        
        # Unregister subscriber
        bus.unregister_subscriber(subscriber)
        assert len(bus.subscribers) == 0
        assert subscriber not in bus.subscribers
    
    def test_publisher_registration(self) -> None:
        """Test publisher registration and unregistration."""
        bus = EventBus()
        publisher = EventPublisher("test_topic")
        
        # Register publisher
        bus.register_publisher(publisher)
        assert len(bus.publishers) == 1
        assert publisher in bus.publishers
        
        # Unregister publisher
        bus.unregister_publisher(publisher)
        assert len(bus.publishers) == 0
        assert publisher not in bus.publishers
    
    def test_event_publishing_and_subscription(self) -> None:
        """Test basic event publishing and subscription."""
        bus = EventBus()
        bus.start()
        
        received_events = []
        
        def handler(event: Event) -> None:
            received_events.append(event)
        
        # Subscribe to events
        subscriber = EventSubscriber("test_topic", handler)
        bus.register_subscriber(subscriber)
        
        # Publish event
        publisher = EventPublisher("test_topic")
        bus.register_publisher(publisher)
        
        test_event = Event(
            topic=EventTopic("test_topic"),
            data={"message": "Hello World"},
            priority=EventPriority.NORMAL
        )
        
        publisher.publish(test_event)
        
        # Wait for event processing
        time.sleep(0.1)
        
        assert len(received_events) == 1
        assert received_events[0].topic.name == "test_topic"
        assert received_events[0].data["message"] == "Hello World"
        
        bus.stop()
    
    def test_event_filtering(self) -> None:
        """Test event filtering functionality."""
        bus = EventBus()
        bus.start()
        
        received_events = []
        
        def handler(event: Event) -> None:
            received_events.append(event)
        
        # Create filter that only allows events with specific data
        def filter_func(event: Event) -> bool:
            return bool(event.data.get("level") == "important")
        
        event_filter = EventFilter(filter_func)
        subscriber = EventSubscriber("test_topic", handler, event_filter)
        bus.register_subscriber(subscriber)
        
        publisher = EventPublisher("test_topic")
        bus.register_publisher(publisher)
        
        # Publish events - one should be filtered out
        event1 = Event(
            topic=EventTopic("test_topic"),
            data={"level": "important", "message": "Important message"},
            priority=EventPriority.NORMAL
        )
        event2 = Event(
            topic=EventTopic("test_topic"),
            data={"level": "debug", "message": "Debug message"},
            priority=EventPriority.NORMAL
        )
        
        publisher.publish(event1)
        publisher.publish(event2)
        
        # Wait for event processing
        time.sleep(0.1)
        
        assert len(received_events) == 1
        assert received_events[0].data["level"] == "important"
        
        bus.stop()
    
    def test_event_prioritization(self) -> None:
        """Test event prioritization."""
        bus = EventBus()
        bus.start()
        
        received_events = []
        
        def handler(event: Event) -> None:
            received_events.append(event)
        
        subscriber = EventSubscriber("test_topic", handler)
        bus.register_subscriber(subscriber)
        
        publisher = EventPublisher("test_topic")
        bus.register_publisher(publisher)
        
        # Publish events with different priorities
        low_event = Event(
            topic=EventTopic("test_topic"),
            data={"priority": "low"},
            priority=EventPriority.LOW
        )
        high_event = Event(
            topic=EventTopic("test_topic"),
            data={"priority": "high"},
            priority=EventPriority.HIGH
        )
        normal_event = Event(
            topic=EventTopic("test_topic"),
            data={"priority": "normal"},
            priority=EventPriority.NORMAL
        )
        
        # Publish in reverse priority order
        publisher.publish(low_event)
        publisher.publish(high_event)
        publisher.publish(normal_event)
        
        # Wait for event processing
        time.sleep(0.1)
        
        assert len(received_events) == 3
        # High priority should be processed first
        assert received_events[0].data["priority"] == "high"
        assert received_events[1].data["priority"] == "normal"
        assert received_events[2].data["priority"] == "low"
        
        bus.stop()
    
    def test_multiple_subscribers_same_topic(self) -> None:
        """Test multiple subscribers for the same topic."""
        bus = EventBus()
        bus.start()
        
        received_events1 = []
        received_events2 = []
        
        def handler1(event: Event) -> None:
            received_events1.append(event)
        
        def handler2(event: Event) -> None:
            received_events2.append(event)
        
        subscriber1 = EventSubscriber("test_topic", handler1)
        subscriber2 = EventSubscriber("test_topic", handler2)
        
        bus.register_subscriber(subscriber1)
        bus.register_subscriber(subscriber2)
        
        publisher = EventPublisher("test_topic")
        bus.register_publisher(publisher)
        
        test_event = Event(
            topic=EventTopic("test_topic"),
            data={"message": "Broadcast message"},
            priority=EventPriority.NORMAL
        )
        
        publisher.publish(test_event)
        
        # Wait for event processing
        time.sleep(0.1)
        
        assert len(received_events1) == 1
        assert len(received_events2) == 1
        assert received_events1[0].data["message"] == "Broadcast message"
        assert received_events2[0].data["message"] == "Broadcast message"
        
        bus.stop()
    
    def test_error_handling_in_subscriber(self) -> None:
        """Test error handling when subscriber throws exception."""
        bus = EventBus()
        bus.start()
        
        received_events = []
        
        def failing_handler(event: Event) -> None:
            raise ValueError("Handler error")
        
        def good_handler(event: Event) -> None:
            received_events.append(event)
        
        failing_subscriber = EventSubscriber("test_topic", failing_handler)
        good_subscriber = EventSubscriber("test_topic", good_handler)
        
        bus.register_subscriber(failing_subscriber)
        bus.register_subscriber(good_subscriber)
        
        publisher = EventPublisher("test_topic")
        bus.register_publisher(publisher)
        
        test_event = Event(
            topic=EventTopic("test_topic"),
            data={"message": "Test message"},
            priority=EventPriority.NORMAL
        )
        
        publisher.publish(test_event)
        
        # Wait for event processing
        time.sleep(0.1)
        
        # Good subscriber should still receive the event
        assert len(received_events) == 1
        assert received_events[0].data["message"] == "Test message"
        
        # Failed event should be in dead letter queue
        assert len(bus.dead_letter_queue.get_failed_events()) > 0
        
        bus.stop()
    
    def test_thread_safety(self) -> None:
        """Test thread safety of event bus."""
        bus = EventBus()
        bus.start()
        
        received_events = []
        lock = threading.Lock()
        
        def handler(event: Event) -> None:
            with lock:
                received_events.append(event)
        
        subscriber = EventSubscriber("test_topic", handler)
        bus.register_subscriber(subscriber)
        
        publisher = EventPublisher("test_topic")
        bus.register_publisher(publisher)
        
        # Publish events from multiple threads
        def publish_events(count: int) -> None:
            for i in range(count):
                event = Event(
                    topic=EventTopic("test_topic"),
                    data={"thread_id": threading.current_thread().ident, "index": i},
                    priority=EventPriority.NORMAL
                )
                publisher.publish(event)
        
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=publish_events, args=(10,))
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Wait for all events to be processed
        time.sleep(0.5)
        
        assert len(received_events) == 50  # 5 threads * 10 events each
        
        bus.stop()
    
    def test_topic_pattern_matching(self) -> None:
        """Test topic pattern matching for subscriptions."""
        bus = EventBus()
        bus.start()
        
        received_events = []
        
        def handler(event: Event) -> None:
            received_events.append(event)
        
        # Subscribe to wildcard topic
        subscriber = EventSubscriber("system.*", handler)
        bus.register_subscriber(subscriber)
        
        publisher1 = EventPublisher("system.startup")
        publisher2 = EventPublisher("system.shutdown")
        publisher3 = EventPublisher("user.login")
        
        bus.register_publisher(publisher1)
        bus.register_publisher(publisher2)
        bus.register_publisher(publisher3)
        
        # Publish events
        event1 = Event(
            topic=EventTopic("system.startup"),
            data={"action": "startup"},
            priority=EventPriority.NORMAL
        )
        event2 = Event(
            topic=EventTopic("system.shutdown"),
            data={"action": "shutdown"},
            priority=EventPriority.NORMAL
        )
        event3 = Event(
            topic=EventTopic("user.login"),
            data={"action": "login"},
            priority=EventPriority.NORMAL
        )
        
        publisher1.publish(event1)
        publisher2.publish(event2)
        publisher3.publish(event3)
        
        # Wait for event processing
        time.sleep(0.1)
        
        # Only system.* events should be received
        assert len(received_events) == 2
        actions = [event.data["action"] for event in received_events]
        assert "startup" in actions
        assert "shutdown" in actions
        assert "login" not in actions
        
        bus.stop()


class TestEvent:
    """Test cases for Event class."""
    
    def test_event_creation(self) -> None:
        """Test Event creation and properties."""
        topic = EventTopic("test_topic")
        data: dict[str, object] = {"key": "value"}
        
        event = Event(
            topic=topic,
            data=data,
            priority=EventPriority.HIGH
        )
        
        assert event.topic == topic
        assert event.data == data
        assert event.priority == EventPriority.HIGH
        assert event.timestamp is not None
        assert event.event_id is not None
    
    def test_event_serialization(self) -> None:
        """Test Event serialization and deserialization."""
        topic = EventTopic("test_topic")
        data: dict[str, object] = {"key": "value", "number": 42}
        
        event = Event(
            topic=topic,
            data=data,
            priority=EventPriority.NORMAL
        )
        
        # Serialize
        serialized = event.serialize()
        assert isinstance(serialized, dict)
        assert serialized["topic"] == "test_topic"
        assert serialized["data"] == data
        assert serialized["priority"] == EventPriority.NORMAL.value
        
        # Deserialize
        deserialized = Event.deserialize(serialized)
        assert deserialized.topic.name == event.topic.name
        assert deserialized.data == event.data
        assert deserialized.priority == event.priority


class TestEventTopic:
    """Test cases for EventTopic class."""
    
    def test_topic_creation(self) -> None:
        """Test EventTopic creation and validation."""
        topic = EventTopic("valid.topic.name")
        assert topic.name == "valid.topic.name"
        assert topic.is_valid() is True
    
    def test_topic_validation(self) -> None:
        """Test EventTopic validation rules."""
        # Valid topics
        assert EventTopic("simple").is_valid() is True
        assert EventTopic("with.dots").is_valid() is True
        assert EventTopic("with_underscores").is_valid() is True
        assert EventTopic("with-hyphens").is_valid() is True
        assert EventTopic("with123numbers").is_valid() is True
        
        # Invalid topics
        assert EventTopic("").is_valid() is False
        assert EventTopic("with spaces").is_valid() is False
        assert EventTopic("with@symbols").is_valid() is False
        assert EventTopic("with/slashes").is_valid() is False
    
    def test_topic_pattern_matching(self) -> None:
        """Test EventTopic pattern matching."""
        topic = EventTopic("system.monitor.cpu")
        
        # Exact match
        assert topic.matches("system.monitor.cpu") is True
        
        # Wildcard match
        assert topic.matches("system.*") is True
        assert topic.matches("system.monitor.*") is True
        assert topic.matches("*.cpu") is True
        assert topic.matches("*") is True
        
        # No match
        assert topic.matches("user.*") is False
        assert topic.matches("system.memory.*") is False
        assert topic.matches("*.memory") is False


class TestEventPriority:
    """Test cases for EventPriority enum."""
    
    def test_priority_values(self) -> None:
        """Test EventPriority enum values."""
        assert EventPriority.LOW.value == 0
        assert EventPriority.NORMAL.value == 1
        assert EventPriority.HIGH.value == 2
        assert EventPriority.CRITICAL.value == 3
    
    def test_priority_ordering(self) -> None:
        """Test EventPriority ordering."""
        priorities = [EventPriority.HIGH, EventPriority.LOW, EventPriority.CRITICAL, EventPriority.NORMAL]
        sorted_priorities = sorted(priorities, key=lambda p: p.value, reverse=True)
        
        expected_order = [EventPriority.CRITICAL, EventPriority.HIGH, EventPriority.NORMAL, EventPriority.LOW]
        assert sorted_priorities == expected_order


class TestEventSubscriber:
    """Test cases for EventSubscriber class."""
    
    def test_subscriber_creation(self) -> None:
        """Test EventSubscriber creation."""
        handler = Mock()
        subscriber = EventSubscriber("test_topic", handler)
        
        assert subscriber.topic == "test_topic"
        assert subscriber.handler == handler
        assert subscriber.event_filter is None
    
    def test_subscriber_with_filter(self) -> None:
        """Test EventSubscriber with filter."""
        handler = Mock()
        filter_func = Mock(return_value=True)
        event_filter = EventFilter(filter_func)
        
        subscriber = EventSubscriber("test_topic", handler, event_filter)
        
        assert subscriber.event_filter == event_filter
    
    def test_subscriber_can_handle_event(self) -> None:
        """Test EventSubscriber can_handle_event method."""
        handler = Mock()
        subscriber = EventSubscriber("test_topic", handler)
        
        # Matching topic
        event = Event(
            topic=EventTopic("test_topic"),
            data={},
            priority=EventPriority.NORMAL
        )
        assert subscriber.can_handle_event(event) is True
        
        # Non-matching topic
        event = Event(
            topic=EventTopic("other_topic"),
            data={},
            priority=EventPriority.NORMAL
        )
        assert subscriber.can_handle_event(event) is False
    
    def test_subscriber_handle_event(self) -> None:
        """Test EventSubscriber handle_event method."""
        handler = Mock()
        subscriber = EventSubscriber("test_topic", handler)
        
        event = Event(
            topic=EventTopic("test_topic"),
            data={"key": "value"},
            priority=EventPriority.NORMAL
        )
        
        subscriber.handle_event(event)
        handler.assert_called_once_with(event)


class TestEventPublisher:
    """Test cases for EventPublisher class."""
    
    def test_publisher_creation(self) -> None:
        """Test EventPublisher creation."""
        publisher = EventPublisher("test_topic")
        assert publisher.topic == "test_topic"
        assert publisher.event_bus is None
    
    def test_publisher_publish_without_bus(self) -> None:
        """Test EventPublisher publish without event bus."""
        publisher = EventPublisher("test_topic")
        event = Event(
            topic=EventTopic("test_topic"),
            data={},
            priority=EventPriority.NORMAL
        )
        
        # Should not raise exception
        publisher.publish(event)
    
    def test_publisher_publish_with_bus(self) -> None:
        """Test EventPublisher publish with event bus."""
        bus = EventBus()
        publisher = EventPublisher("test_topic")
        publisher.set_event_bus(bus)
        
        event = Event(
            topic=EventTopic("test_topic"),
            data={"key": "value"},
            priority=EventPriority.NORMAL
        )
        
        with Mock() as mock_bus:
            publisher.event_bus = mock_bus
            publisher.publish(event)
            mock_bus.publish_event.assert_called_once_with(event)


class TestDeadLetterQueue:
    """Test cases for DeadLetterQueue class."""
    
    def test_dead_letter_queue_creation(self) -> None:
        """Test DeadLetterQueue creation."""
        dlq = DeadLetterQueue(max_size=100)
        assert dlq.max_size == 100
        assert len(dlq.get_failed_events()) == 0
    
    def test_dead_letter_queue_add_failed_event(self) -> None:
        """Test adding failed events to dead letter queue."""
        dlq = DeadLetterQueue(max_size=2)
        
        event1 = Event(
            topic=EventTopic("test_topic"),
            data={"id": 1},
            priority=EventPriority.NORMAL
        )
        event2 = Event(
            topic=EventTopic("test_topic"),
            data={"id": 2},
            priority=EventPriority.NORMAL
        )
        
        error1 = Exception("Error 1")
        error2 = Exception("Error 2")
        
        dlq.add_failed_event(event1, error1)
        dlq.add_failed_event(event2, error2)
        
        failed_events = dlq.get_failed_events()
        assert len(failed_events) == 2
        assert failed_events[0].event == event1
        assert failed_events[1].event == event2
    
    def test_dead_letter_queue_max_size(self) -> None:
        """Test dead letter queue maximum size enforcement."""
        dlq = DeadLetterQueue(max_size=2)
        
        # Add 3 events (should only keep 2)
        for i in range(3):
            event = Event(
                topic=EventTopic("test_topic"),
                data={"id": i},
                priority=EventPriority.NORMAL
            )
            error = Exception(f"Error {i}")
            dlq.add_failed_event(event, error)
        
        failed_events = dlq.get_failed_events()
        assert len(failed_events) == 2
        # Should keep the most recent events
        assert failed_events[0].event.data["id"] == 1
        assert failed_events[1].event.data["id"] == 2
    
    def test_dead_letter_queue_clear(self) -> None:
        """Test clearing dead letter queue."""
        dlq = DeadLetterQueue(max_size=100)
        
        event = Event(
            topic=EventTopic("test_topic"),
            data={},
            priority=EventPriority.NORMAL
        )
        error = Exception("Error")
        
        dlq.add_failed_event(event, error)
        assert len(dlq.get_failed_events()) == 1
        
        dlq.clear()
        assert len(dlq.get_failed_events()) == 0


class TestEventHandler:
    """Test cases for EventHandler class."""
    
    def test_event_handler_creation(self) -> None:
        """Test EventHandler creation."""
        def handler_func(event: Event) -> None:
            pass
        
        handler = EventHandler(handler_func)
        assert handler.handler_func == handler_func
    
    def test_event_handler_call(self) -> None:
        """Test EventHandler call method."""
        called_events = []
        
        def handler_func(event: Event) -> None:
            called_events.append(event)
        
        handler = EventHandler(handler_func)
        
        event = Event(
            topic=EventTopic("test_topic"),
            data={"key": "value"},
            priority=EventPriority.NORMAL
        )
        
        handler(event)
        
        assert len(called_events) == 1
        assert called_events[0] == event
    
    def test_event_handler_error_handling(self) -> None:
        """Test EventHandler error handling."""
        def failing_handler(event: Event) -> None:
            raise ValueError("Handler failed")
        
        handler = EventHandler(failing_handler)
        
        event = Event(
            topic=EventTopic("test_topic"),
            data={},
            priority=EventPriority.NORMAL
        )
        
        with pytest.raises(EventHandlerError):
            handler(event)


class TestEventFilter:
    """Test cases for EventFilter class."""
    
    def test_event_filter_creation(self) -> None:
        """Test EventFilter creation."""
        def filter_func(event: Event) -> bool:
            return True
        
        event_filter = EventFilter(filter_func)
        assert event_filter.filter_func == filter_func
    
    def test_event_filter_allows_event(self) -> None:
        """Test EventFilter allows_event method."""
        def filter_func(event: Event) -> bool:
            allowed = event.data.get("allowed", False)
            return bool(allowed)
        
        event_filter = EventFilter(filter_func)
        
        # Event that should be allowed
        allowed_event = Event(
            topic=EventTopic("test_topic"),
            data={"allowed": True},
            priority=EventPriority.NORMAL
        )
        assert event_filter.allows_event(allowed_event) is True
        
        # Event that should be filtered out
        filtered_event = Event(
            topic=EventTopic("test_topic"),
            data={"allowed": False},
            priority=EventPriority.NORMAL
        )
        assert event_filter.allows_event(filtered_event) is False
    
    def test_event_filter_error_handling(self) -> None:
        """Test EventFilter error handling."""
        def failing_filter(event: Event) -> bool:
            raise ValueError("Filter failed")
        
        event_filter = EventFilter(failing_filter)
        
        event = Event(
            topic=EventTopic("test_topic"),
            data={},
            priority=EventPriority.NORMAL
        )
        
        # Should return False on filter error
        assert event_filter.allows_event(event) is False


class TestQueuedEvent:
    """Test cases for QueuedEvent class."""
    
    def test_queued_event_creation(self) -> None:
        """Test QueuedEvent creation."""
        event = Event(
            topic=EventTopic("test_topic"),
            data={"key": "value"},
            priority=EventPriority.HIGH
        )
        
        queued_event = QueuedEvent(event)
        assert queued_event.event == event
        assert queued_event.retry_count == 0
        assert queued_event.queued_at is not None
    
    def test_queued_event_ordering(self) -> None:
        """Test QueuedEvent ordering by priority."""
        low_event = Event(
            topic=EventTopic("test_topic"),
            data={"priority": "low"},
            priority=EventPriority.LOW
        )
        high_event = Event(
            topic=EventTopic("test_topic"),
            data={"priority": "high"},
            priority=EventPriority.HIGH
        )
        
        queued_low = QueuedEvent(low_event)
        queued_high = QueuedEvent(high_event)
        
        # High priority should be "less than" low priority for sorting
        assert queued_high < queued_low
    
    def test_queued_event_increment_retry(self) -> None:
        """Test QueuedEvent increment_retry method."""
        event = Event(
            topic=EventTopic("test_topic"),
            data={},
            priority=EventPriority.NORMAL
        )
        
        queued_event = QueuedEvent(event)
        assert queued_event.retry_count == 0
        
        queued_event.increment_retry()
        assert queued_event.retry_count == 1
        
        queued_event.increment_retry()
        assert queued_event.retry_count == 2


class TestEventBusExceptions:
    """Test cases for event bus exceptions."""
    
    def test_event_bus_error(self) -> None:
        """Test EventBusError exception."""
        error = EventBusError("Test error")
        assert str(error) == "Test error"
        assert isinstance(error, Exception)
    
    def test_event_handler_error(self) -> None:
        """Test EventHandlerError exception."""
        original_error = ValueError("Original error")
        error = EventHandlerError("Handler failed", original_error)
        
        assert str(error) == "Handler failed"
        assert error.original_error == original_error
        assert isinstance(error, EventBusError)
    
    def test_event_subscription_error(self) -> None:
        """Test EventSubscriptionError exception."""
        error = EventSubscriptionError("Subscription failed", "test_topic")
        
        assert str(error) == "Subscription failed"
        assert error.topic == "test_topic"
        assert isinstance(error, EventBusError)