"""Event bus implementation for monitoring orchestrator."""

from __future__ import annotations

import re
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from queue import PriorityQueue
from typing import Callable, override, cast
import logging

logger = logging.getLogger(__name__)


class EventPriority(Enum):
    """Event priority levels."""
    
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


class EventBusError(Exception):
    """Base exception for event bus errors."""
    pass


class EventHandlerError(EventBusError):
    """Exception raised when event handler fails."""
    
    def __init__(self, message: str, original_error: Exception | None = None) -> None:
        """Initialize handler error.
        
        Args:
            message: Error message
            original_error: The original exception that caused this error
        """
        super().__init__(message)
        self.original_error: Exception | None = original_error


class EventSubscriptionError(EventBusError):
    """Exception raised when event subscription fails."""
    
    def __init__(self, message: str, topic: str | None = None) -> None:
        """Initialize subscription error.
        
        Args:
            message: Error message
            topic: Topic name related to the error
        """
        super().__init__(message)
        self.topic: str | None = topic


class EventTopic:
    """Represents an event topic with pattern matching support."""
    
    def __init__(self, name: str) -> None:
        """Initialize event topic.
        
        Args:
            name: Topic name
        """
        self.name: str = name
    
    def is_valid(self) -> bool:
        """Check if topic name is valid.
        
        Returns:
            True if topic name is valid
        """
        if not self.name:
            return False
        
        # Allow alphanumeric characters, dots, underscores, and hyphens
        pattern = r'^[a-zA-Z0-9._-]+$'
        return bool(re.match(pattern, self.name))
    
    def matches(self, pattern: str) -> bool:
        """Check if topic matches a pattern.

        Args:
            pattern: Pattern to match against (supports * wildcard)

        Returns:
            True if topic matches pattern
        """
        # Convert wildcard pattern to regex
        # First escape dots, then replace wildcards
        regex_pattern = pattern.replace('.', r'\.').replace('*', '.*')
        regex_pattern = f'^{regex_pattern}$'

        return bool(re.match(regex_pattern, self.name))
    
    @override
    def __eq__(self, other: object) -> bool:
        """Check equality with another EventTopic."""
        if not isinstance(other, EventTopic):
            return False
        return self.name == other.name
    
    @override
    def __hash__(self) -> int:
        """Get hash of the topic."""
        return hash(self.name)
    
    @override
    def __repr__(self) -> str:
        """Get string representation of the topic."""
        return f"EventTopic('{self.name}')"


@dataclass
class Event:
    """Represents an event in the event bus."""
    
    topic: EventTopic
    data: dict[str, object]
    priority: EventPriority
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)
    
    def serialize(self) -> dict[str, object]:
        """Serialize event to dictionary.
        
        Returns:
            Serialized event data
        """
        return {
            'event_id': self.event_id,
            'topic': self.topic.name,
            'data': self.data,
            'priority': self.priority.value,
            'timestamp': self.timestamp
        }
    
    @classmethod
    def deserialize(cls, data: dict[str, object]) -> Event:
        """Deserialize event from dictionary.
        
        Args:
            data: Serialized event data
            
        Returns:
            Event instance
        """
        return cls(
            event_id=str(data['event_id']),
            topic=EventTopic(str(data['topic'])),
            data=cast(dict[str, object], data['data']) if isinstance(data['data'], dict) else {},
            priority=EventPriority(int(data['priority'])) if isinstance(data['priority'], int) else EventPriority.NORMAL,
            timestamp=float(data['timestamp']) if isinstance(data['timestamp'], (int, float)) else time.time()
        )
    
    @override
    def __eq__(self, other: object) -> bool:
        """Check equality with another Event."""
        if not isinstance(other, Event):
            return False
        return self.event_id == other.event_id


@dataclass
class QueuedEvent:
    """Represents an event in the processing queue."""
    
    event: Event
    retry_count: int = 0
    queued_at: float = field(default_factory=time.time)
    
    def increment_retry(self) -> None:
        """Increment retry count."""
        self.retry_count += 1
    
    def __lt__(self, other: QueuedEvent) -> bool:
        """Compare queued events for priority ordering."""
        if self.event.priority.value != other.event.priority.value:
            # Higher priority value means higher priority (reverse order)
            return self.event.priority.value > other.event.priority.value
        
        # If same priority, earlier timestamp wins
        return self.queued_at < other.queued_at


@dataclass
class FailedEvent:
    """Represents a failed event in the dead letter queue."""
    
    event: Event
    error: Exception
    failed_at: float = field(default_factory=time.time)
    retry_count: int = 0


class DeadLetterQueue:
    """Dead letter queue for failed events."""
    
    def __init__(self, max_size: int = 1000) -> None:
        """Initialize dead letter queue.
        
        Args:
            max_size: Maximum number of failed events to store
        """
        self.max_size: int = max_size
        self._failed_events: deque[FailedEvent] = deque(maxlen=max_size)
        self._lock: threading.RLock = threading.RLock()
    
    def add_failed_event(self, event: Event, error: Exception) -> None:
        """Add a failed event to the dead letter queue.
        
        Args:
            event: The event that failed
            error: The error that occurred
        """
        with self._lock:
            failed_event = FailedEvent(event=event, error=error)
            self._failed_events.append(failed_event)
            
            logger.error(
                f"Event {event.event_id} failed and added to dead letter queue: {error}",
                extra={
                    'event_id': event.event_id,
                    'topic': event.topic.name,
                    'error': str(error)
                }
            )
    
    def get_failed_events(self) -> list[FailedEvent]:
        """Get all failed events.
        
        Returns:
            List of failed events
        """
        with self._lock:
            return list(self._failed_events)
    
    def clear(self) -> None:
        """Clear all failed events."""
        with self._lock:
            self._failed_events.clear()
    
    def retry_event(self, event_id: str) -> bool:
        """Retry a failed event.
        
        Args:
            event_id: ID of the event to retry
            
        Returns:
            True if event was found and removed from queue
        """
        with self._lock:
            for i, failed_event in enumerate(self._failed_events):
                if failed_event.event.event_id == event_id:
                    del self._failed_events[i]
                    return True
            return False


class EventFilter:
    """Event filter for selective event processing."""
    
    def __init__(self, filter_func: Callable[[Event], bool]) -> None:
        """Initialize event filter.
        
        Args:
            filter_func: Function that returns True if event should be processed
        """
        self.filter_func: Callable[[Event], bool] = filter_func
    
    def allows_event(self, event: Event) -> bool:
        """Check if event is allowed by filter.
        
        Args:
            event: Event to check
            
        Returns:
            True if event is allowed
        """
        try:
            return self.filter_func(event)
        except Exception as e:
            logger.warning(
                f"Event filter failed for event {event.event_id}: {e}",
                extra={'event_id': event.event_id, 'error': str(e)}
            )
            return False


class EventHandler:
    """Wrapper for event handler functions."""
    
    def __init__(self, handler_func: Callable[[Event], None]) -> None:
        """Initialize event handler.
        
        Args:
            handler_func: Function to handle events
        """
        self.handler_func: Callable[[Event], None] = handler_func
    
    def __call__(self, event: Event) -> None:
        """Handle an event.
        
        Args:
            event: Event to handle
            
        Raises:
            EventHandlerError: If handler function fails
        """
        try:
            self.handler_func(event)
        except Exception as e:
            raise EventHandlerError(
                f"Handler failed for event {event.event_id}: {e}",
                original_error=e
            ) from e


class EventSubscriber:
    """Event subscriber that listens for events on specific topics."""
    
    def __init__(
        self,
        topic: str,
        handler: Callable[[Event], None],
        event_filter: EventFilter | None = None,
        max_retries: int = 3
    ) -> None:
        """Initialize event subscriber.
        
        Args:
            topic: Topic pattern to subscribe to
            handler: Function to handle events
            event_filter: Optional filter for events
            max_retries: Maximum number of retries for failed events
        """
        self.topic: str = topic
        self.handler: Callable[[Event], None] = handler
        self.event_filter: EventFilter | None = event_filter
        self.max_retries: int = max_retries
        self.subscriber_id: str = str(uuid.uuid4())
    
    def can_handle_event(self, event: Event) -> bool:
        """Check if subscriber can handle an event.
        
        Args:
            event: Event to check
            
        Returns:
            True if subscriber can handle the event
        """
        # Check topic match
        if not event.topic.matches(self.topic):
            return False
        
        # Check filter if present
        if self.event_filter and not self.event_filter.allows_event(event):
            return False
        
        return True
    
    def handle_event(self, event: Event) -> None:
        """Handle an event.
        
        Args:
            event: Event to handle
            
        Raises:
            EventHandlerError: If handler fails
        """
        try:
            self.handler(event)
            logger.debug(
                f"Event {event.event_id} handled successfully by subscriber {self.subscriber_id}",
                extra={
                    'event_id': event.event_id,
                    'subscriber_id': self.subscriber_id,
                    'topic': event.topic.name
                }
            )
        except Exception as e:
            raise EventHandlerError(
                f"Subscriber {self.subscriber_id} failed to handle event {event.event_id}: {e}",
                original_error=e
            ) from e
    
    @override
    def __eq__(self, other: object) -> bool:
        """Check equality with another EventSubscriber."""
        if not isinstance(other, EventSubscriber):
            return False
        return self.subscriber_id == other.subscriber_id
    
    @override
    def __hash__(self) -> int:
        """Get hash of the subscriber."""
        return hash(self.subscriber_id)


class EventPublisher:
    """Event publisher that sends events to the event bus."""
    
    def __init__(self, topic: str) -> None:
        """Initialize event publisher.
        
        Args:
            topic: Default topic for published events
        """
        self.topic: str = topic
        self.publisher_id: str = str(uuid.uuid4())
        self.event_bus: EventBus | None = None
    
    def set_event_bus(self, event_bus: EventBus) -> None:
        """Set the event bus for this publisher.
        
        Args:
            event_bus: Event bus instance
        """
        self.event_bus = event_bus
    
    def publish(self, event: Event) -> None:
        """Publish an event.
        
        Args:
            event: Event to publish
        """
        if self.event_bus:
            self.event_bus.publish_event(event)
        else:
            logger.warning(
                f"Publisher {self.publisher_id} attempted to publish event {event.event_id} "
                + "but no event bus is configured"
            )
    
    def create_event(
        self,
        data: dict[str, object],
        priority: EventPriority = EventPriority.NORMAL,
        topic: str | None = None
    ) -> Event:
        """Create an event with this publisher's default topic.
        
        Args:
            data: Event data
            priority: Event priority
            topic: Override topic (uses publisher's default if None)
            
        Returns:
            Created event
        """
        event_topic = EventTopic(topic or self.topic)
        return Event(
            topic=event_topic,
            data=data,
            priority=priority
        )
    
    @override
    def __eq__(self, other: object) -> bool:
        """Check equality with another EventPublisher."""
        if not isinstance(other, EventPublisher):
            return False
        return self.publisher_id == other.publisher_id
    
    @override
    def __hash__(self) -> int:
        """Get hash of the publisher."""
        return hash(self.publisher_id)


class EventBus:
    """Main event bus for publish-subscribe messaging."""
    
    def __init__(self, max_queue_size: int = 10000, worker_threads: int = 4) -> None:
        """Initialize event bus.
        
        Args:
            max_queue_size: Maximum number of events in queue
            worker_threads: Number of worker threads for processing events
        """
        self.max_queue_size: int = max_queue_size
        self.worker_threads: int = worker_threads
        
        # Core components
        self.subscribers: set[EventSubscriber] = set()
        self.publishers: set[EventPublisher] = set()
        self.dead_letter_queue: DeadLetterQueue = DeadLetterQueue()
        
        # Event processing
        self._event_queue: PriorityQueue[QueuedEvent] = PriorityQueue(maxsize=max_queue_size)
        self._workers: list[threading.Thread] = []
        self._running: bool = False
        self._lock: threading.RLock = threading.RLock()
        
        # Statistics
        self._stats: dict[str, int] = {
            'events_published': 0,
            'events_processed': 0,
            'events_failed': 0,
            'subscribers_count': 0,
            'publishers_count': 0
        }
    
    @property
    def is_running(self) -> bool:
        """Check if event bus is running.
        
        Returns:
            True if event bus is running
        """
        with self._lock:
            return self._running
    
    def start(self) -> None:
        """Start the event bus."""
        with self._lock:
            if self._running:
                return
            
            self._running = True
            
            # Start worker threads
            for i in range(self.worker_threads):
                worker = threading.Thread(
                    target=self._worker_thread,
                    name=f"EventBusWorker-{i}",
                    daemon=True
                )
                worker.start()
                self._workers.append(worker)
            
            logger.info(
                f"Event bus started with {self.worker_threads} worker threads",
                extra={'worker_threads': self.worker_threads}
            )
    
    def stop(self) -> None:
        """Stop the event bus."""
        with self._lock:
            if not self._running:
                return
            
            self._running = False
            
            # Add sentinel values to wake up workers
            for _ in range(self.worker_threads):
                try:
                    # Create a sentinel event to wake up workers
                    sentinel_event = Event(
                        topic=EventTopic("__shutdown__"),
                        data={},
                        priority=EventPriority.CRITICAL
                    )
                    sentinel_queued = QueuedEvent(sentinel_event)
                    self._event_queue.put(sentinel_queued, timeout=1.0)
                except Exception:
                    pass  # Queue might be full, that's ok
            
            # Wait for workers to finish
            for worker in self._workers:
                if worker.is_alive():
                    worker.join(timeout=2.0)
            
            self._workers.clear()
            
            logger.info("Event bus stopped")
    
    def register_subscriber(self, subscriber: EventSubscriber) -> None:
        """Register an event subscriber.
        
        Args:
            subscriber: Subscriber to register
        """
        with self._lock:
            self.subscribers.add(subscriber)
            self._stats['subscribers_count'] = len(self.subscribers)
            
            logger.debug(
                f"Registered subscriber {subscriber.subscriber_id} for topic '{subscriber.topic}'",
                extra={
                    'subscriber_id': subscriber.subscriber_id,
                    'topic': subscriber.topic
                }
            )
    
    def unregister_subscriber(self, subscriber: EventSubscriber) -> None:
        """Unregister an event subscriber.
        
        Args:
            subscriber: Subscriber to unregister
        """
        with self._lock:
            self.subscribers.discard(subscriber)
            self._stats['subscribers_count'] = len(self.subscribers)
            
            logger.debug(
                f"Unregistered subscriber {subscriber.subscriber_id}",
                extra={'subscriber_id': subscriber.subscriber_id}
            )
    
    def register_publisher(self, publisher: EventPublisher) -> None:
        """Register an event publisher.
        
        Args:
            publisher: Publisher to register
        """
        with self._lock:
            self.publishers.add(publisher)
            publisher.set_event_bus(self)
            self._stats['publishers_count'] = len(self.publishers)
            
            logger.debug(
                f"Registered publisher {publisher.publisher_id} for topic '{publisher.topic}'",
                extra={
                    'publisher_id': publisher.publisher_id,
                    'topic': publisher.topic
                }
            )
    
    def unregister_publisher(self, publisher: EventPublisher) -> None:
        """Unregister an event publisher.
        
        Args:
            publisher: Publisher to unregister
        """
        with self._lock:
            self.publishers.discard(publisher)
            publisher.event_bus = None
            self._stats['publishers_count'] = len(self.publishers)
            
            logger.debug(
                f"Unregistered publisher {publisher.publisher_id}",
                extra={'publisher_id': publisher.publisher_id}
            )
    
    def publish_event(self, event: Event) -> None:
        """Publish an event to the bus.
        
        Args:
            event: Event to publish
        """
        if not self._running:
            logger.warning(
                f"Cannot publish event {event.event_id} - event bus is not running"
            )
            return
        
        try:
            queued_event = QueuedEvent(event)
            self._event_queue.put(queued_event, timeout=1.0)
            
            with self._lock:
                self._stats['events_published'] += 1
            
            logger.debug(
                f"Published event {event.event_id} to topic '{event.topic.name}'",
                extra={
                    'event_id': event.event_id,
                    'topic': event.topic.name,
                    'priority': event.priority.name
                }
            )
        except Exception as e:
            logger.error(
                f"Failed to publish event {event.event_id}: {e}",
                extra={'event_id': event.event_id, 'error': str(e)}
            )
    
    def get_stats(self) -> dict[str, int]:
        """Get event bus statistics.
        
        Returns:
            Dictionary of statistics
        """
        with self._lock:
            return self._stats.copy()
    
    def _worker_thread(self) -> None:
        """Worker thread for processing events."""
        thread_name = threading.current_thread().name
        logger.debug(f"Event bus worker thread {thread_name} started")
        
        while self._running:
            try:
                # Get event from queue
                queued_event = self._event_queue.get(timeout=1.0)
                
                # Check for shutdown sentinel
                if queued_event.event.topic.name == "__shutdown__":
                    break
                
                # Process the event
                self._process_event(queued_event)
                
            except Exception as e:
                if self._running:  # Only log if we're still supposed to be running
                    logger.error(
                        f"Error in worker thread {thread_name}: {e}",
                        extra={'thread_name': thread_name, 'error': str(e)}
                    )
        
        logger.debug(f"Event bus worker thread {thread_name} stopped")
    
    def _process_event(self, queued_event: QueuedEvent) -> None:
        """Process a single event.
        
        Args:
            queued_event: Event to process
        """
        event = queued_event.event
        
        # Find matching subscribers
        matching_subscribers: list[EventSubscriber] = []
        with self._lock:
            for subscriber in self.subscribers:
                if subscriber.can_handle_event(event):
                    matching_subscribers.append(subscriber)
        
        if not matching_subscribers:
            logger.debug(
                f"No subscribers found for event {event.event_id} on topic '{event.topic.name}'",
                extra={
                    'event_id': event.event_id,
                    'topic': event.topic.name
                }
            )
            return
        
        # Process event for each subscriber
        for subscriber in matching_subscribers:
            try:
                subscriber.handle_event(event)
                
            except EventHandlerError as e:
                logger.error(
                    f"Subscriber {subscriber.subscriber_id} failed to handle event {event.event_id}: {e}",
                    extra={
                        'event_id': event.event_id,
                        'subscriber_id': subscriber.subscriber_id,
                        'error': str(e)
                    }
                )
                
                # Add to dead letter queue
                self.dead_letter_queue.add_failed_event(event, e)
                
                with self._lock:
                    self._stats['events_failed'] += 1
            
            except Exception as e:
                logger.error(
                    f"Unexpected error in subscriber {subscriber.subscriber_id} "
                    + f"handling event {event.event_id}: {e}",
                    extra={
                        'event_id': event.event_id,
                        'subscriber_id': subscriber.subscriber_id,
                        'error': str(e)
                    }
                )
                
                # Add to dead letter queue
                self.dead_letter_queue.add_failed_event(event, e)
                
                with self._lock:
                    self._stats['events_failed'] += 1
        
        with self._lock:
            self._stats['events_processed'] += 1
    
    def __enter__(self) -> EventBus:
        """Enter context manager."""
        self.start()
        return self
    
    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        """Exit context manager."""
        self.stop()