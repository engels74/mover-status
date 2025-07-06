"""Async dispatch infrastructure for notification system."""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING
from collections.abc import Awaitable, Callable

if TYPE_CHECKING:
    from mover_status.notifications.base.provider import NotificationProvider
    from mover_status.notifications.models.message import Message


logger = logging.getLogger(__name__)


class DispatchStatus(Enum):
    """Status of message dispatch."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"


@dataclass
class ProviderResult:
    """Result of sending to a specific provider."""
    provider_name: str
    success: bool
    error: Exception | None = None
    timestamp: float = field(default_factory=time.time)


@dataclass
class DispatchResult:
    """Result of dispatching a message."""
    delivery_id: str
    status: DispatchStatus
    message: Message
    providers: list[str]
    results: dict[str, ProviderResult] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    completed_at: float | None = None

    @property
    def provider_results(self) -> list[ProviderResult]:
        """Get provider results as a list for backward compatibility."""
        return list(self.results.values())


@dataclass
class QueuedMessage:
    """Message queued for dispatch."""
    message: Message
    priority: int
    providers: list[str]
    created_at: float = field(default_factory=time.time)
    delivery_id: str = field(default_factory=lambda: str(uuid.uuid4()))


class MessageQueue:
    """Priority queue for messages."""
    
    def __init__(self, max_size: int = 1000) -> None:
        """Initialize message queue.
        
        Args:
            max_size: Maximum queue size
        """
        self._queue: asyncio.PriorityQueue[tuple[int, float, QueuedMessage]] = (
            asyncio.PriorityQueue(maxsize=max_size)
        )
        self._max_size: int = max_size
    
    async def enqueue(self, message: QueuedMessage) -> None:
        """Add message to queue.
        
        Args:
            message: Message to enqueue
        """
        # Use negative priority for max-heap behavior (higher priority first)
        priority_key = (-message.priority, message.created_at)
        await self._queue.put((priority_key[0], priority_key[1], message))
        logger.debug("Enqueued message: %s (priority: %d)", message.delivery_id, message.priority)
    
    async def dequeue(self) -> QueuedMessage:
        """Remove and return next message from queue.
        
        Returns:
            Next message to process
        """
        _, _, message = await self._queue.get()
        logger.debug("Dequeued message: %s", message.delivery_id)
        return message
    
    def size(self) -> int:
        """Get current queue size.
        
        Returns:
            Number of messages in queue
        """
        return self._queue.qsize()
    
    def is_empty(self) -> bool:
        """Check if queue is empty.
        
        Returns:
            True if queue is empty
        """
        return self._queue.empty()
    
    def is_full(self) -> bool:
        """Check if queue is full.
        
        Returns:
            True if queue is full
        """
        return self._queue.full()


class WorkerPool:
    """Pool of worker tasks for processing messages."""
    
    def __init__(self, max_workers: int = 5) -> None:
        """Initialize worker pool.

        Args:
            max_workers: Maximum number of worker tasks
        """
        self.max_workers: int = max_workers
        self.active_workers: int = 0
        self._workers: list[asyncio.Task[None]] = []
        self._task_queue: asyncio.Queue[tuple[Callable[..., Awaitable[object]], tuple[object, ...], asyncio.Future[object]]] = (
            asyncio.Queue()
        )
        self._shutdown_event: asyncio.Event = asyncio.Event()
    
    async def start(self) -> None:
        """Start worker tasks."""
        if self._workers:
            return  # Already started
        
        self._shutdown_event.clear()
        for i in range(self.max_workers):
            worker = asyncio.create_task(self._worker_loop(f"worker-{i}"))
            self._workers.append(worker)
            self.active_workers += 1
        
        logger.info("Started %d workers", self.max_workers)
    
    async def stop(self) -> None:
        """Stop all worker tasks."""
        if not self._workers:
            return  # Already stopped
        
        self._shutdown_event.set()

        # Cancel all workers
        for worker in self._workers:
            _ = worker.cancel()

        # Wait for workers to finish
        _ = await asyncio.gather(*self._workers, return_exceptions=True)
        
        self._workers.clear()
        self.active_workers = 0
        logger.info("Stopped all workers")
    
    async def submit_task(self, func: Callable[..., Awaitable[object]], *args: object) -> asyncio.Future[object]:
        """Submit a task to the worker pool.

        Args:
            func: Async function to execute
            *args: Arguments for the function

        Returns:
            Future that will contain the result
        """
        future: asyncio.Future[object] = asyncio.Future()
        await self._task_queue.put((func, args, future))
        return future
    
    async def _worker_loop(self, worker_name: str) -> None:
        """Main worker loop.
        
        Args:
            worker_name: Name of the worker for logging
        """
        logger.debug("Worker %s started", worker_name)
        
        try:
            while not self._shutdown_event.is_set():
                try:
                    # Wait for task with timeout to check shutdown event
                    func, args, future = await asyncio.wait_for(
                        self._task_queue.get(),
                        timeout=1.0
                    )
                    
                    try:
                        result = await func(*args)
                        future.set_result(result)
                    except Exception as e:
                        future.set_exception(e)
                        logger.error("Worker %s task failed: %s", worker_name, e)
                    
                except asyncio.TimeoutError:
                    continue  # Check shutdown event
                    
        except asyncio.CancelledError:
            logger.debug("Worker %s cancelled", worker_name)
        finally:
            logger.debug("Worker %s stopped", worker_name)


class DeliveryTracker:
    """Tracks delivery status of messages."""
    
    def __init__(self) -> None:
        """Initialize delivery tracker."""
        self._deliveries: dict[str, DispatchResult] = {}
    
    def track_delivery(self, message: Message, providers: list[str], delivery_id: str | None = None) -> str:
        """Start tracking a new delivery.

        Args:
            message: Message being delivered
            providers: List of providers to deliver to
            delivery_id: Optional specific delivery ID to use

        Returns:
            Delivery ID for tracking
        """
        if delivery_id is None:
            delivery_id = str(uuid.uuid4())

        result = DispatchResult(
            delivery_id=delivery_id,
            status=DispatchStatus.PENDING,
            message=message,
            providers=providers
        )
        self._deliveries[delivery_id] = result
        logger.debug("Started tracking delivery: %s", delivery_id)
        return delivery_id
    
    def update_delivery_status(
        self,
        delivery_id: str,
        provider_name: str,
        success: bool,
        error: Exception | None = None
    ) -> None:
        """Update delivery status for a provider.
        
        Args:
            delivery_id: Delivery ID
            provider_name: Name of the provider
            success: Whether delivery was successful
            error: Error if delivery failed
        """
        if delivery_id not in self._deliveries:
            logger.warning("Unknown delivery ID: %s", delivery_id)
            return
        
        result = self._deliveries[delivery_id]
        result.results[provider_name] = ProviderResult(
            provider_name=provider_name,
            success=success,
            error=error
        )
        
        # Update overall status
        self._update_overall_status(result)
        logger.debug("Updated delivery %s for provider %s: %s", delivery_id, provider_name, success)
    
    def get_delivery_status(self, delivery_id: str) -> DispatchResult | None:
        """Get delivery status.
        
        Args:
            delivery_id: Delivery ID
            
        Returns:
            Delivery result or None if not found
        """
        return self._deliveries.get(delivery_id)
    
    def _update_overall_status(self, result: DispatchResult) -> None:
        """Update overall delivery status based on provider results.
        
        Args:
            result: Dispatch result to update
        """
        if len(result.results) == 0:
            result.status = DispatchStatus.PENDING
        elif len(result.results) < len(result.providers):
            result.status = DispatchStatus.IN_PROGRESS
        else:
            # All providers have reported
            successes = sum(1 for r in result.results.values() if r.success)
            if successes == len(result.providers):
                result.status = DispatchStatus.SUCCESS
            elif successes == 0:
                result.status = DispatchStatus.FAILED
            else:
                result.status = DispatchStatus.PARTIAL
            
            result.completed_at = time.time()


class BatchProcessor:
    """Processes messages in batches for efficiency."""
    
    def __init__(self, batch_size: int = 10, batch_timeout: float = 5.0) -> None:
        """Initialize batch processor.

        Args:
            batch_size: Maximum messages per batch
            batch_timeout: Maximum time to wait for batch to fill
        """
        self.batch_size: int = batch_size
        self.batch_timeout: float = batch_timeout
        self._batch: list[QueuedMessage] = []
        self._batch_handler: Callable[[list[QueuedMessage]], Awaitable[None]] | None = None
        self._batch_task: asyncio.Task[None] | None = None
        self._shutdown_event: asyncio.Event = asyncio.Event()
        self._batch_lock: asyncio.Lock = asyncio.Lock()
    
    def set_batch_handler(self, handler: Callable[[list[QueuedMessage]], Awaitable[None]]) -> None:
        """Set the batch processing handler.
        
        Args:
            handler: Async function to process batches
        """
        self._batch_handler = handler
    
    async def start(self) -> None:
        """Start batch processing."""
        if self._batch_task:
            return  # Already started
        
        self._shutdown_event.clear()
        self._batch_task = asyncio.create_task(self._batch_loop())
        logger.info("Started batch processor")
    
    async def stop(self) -> None:
        """Stop batch processing."""
        if not self._batch_task:
            return  # Already stopped
        
        self._shutdown_event.set()
        
        # Process remaining batch
        async with self._batch_lock:
            if self._batch and self._batch_handler:
                await self._batch_handler(self._batch.copy())
                self._batch.clear()
        
        _ = self._batch_task.cancel()
        try:
            await self._batch_task
        except asyncio.CancelledError:
            pass
        
        self._batch_task = None
        logger.info("Stopped batch processor")
    
    async def add_to_batch(self, message: QueuedMessage) -> None:
        """Add message to current batch.
        
        Args:
            message: Message to add to batch
        """
        async with self._batch_lock:
            self._batch.append(message)
            
            # Process batch if it's full
            if len(self._batch) >= self.batch_size:
                await self._process_current_batch()
    
    async def _batch_loop(self) -> None:
        """Main batch processing loop."""
        try:
            while not self._shutdown_event.is_set():
                await asyncio.sleep(self.batch_timeout)
                
                async with self._batch_lock:
                    if self._batch:
                        await self._process_current_batch()
                        
        except asyncio.CancelledError:
            logger.debug("Batch processor cancelled")
    
    async def _process_current_batch(self) -> None:
        """Process the current batch of messages."""
        if not self._batch or not self._batch_handler:
            return
        
        batch_to_process = self._batch.copy()
        self._batch.clear()
        
        try:
            await self._batch_handler(batch_to_process)
            logger.debug("Processed batch of %d messages", len(batch_to_process))
        except Exception as e:
            logger.error("Batch processing failed: %s", e)


class AsyncDispatcher:
    """Main async dispatcher for notification messages."""
    
    def __init__(self, max_workers: int = 5, queue_size: int = 1000) -> None:
        """Initialize async dispatcher.
        
        Args:
            max_workers: Maximum number of worker tasks
            queue_size: Maximum queue size
        """
        self._providers: dict[str, NotificationProvider] = {}
        self._queue: MessageQueue = MessageQueue(max_size=queue_size)
        self._worker_pool: WorkerPool = WorkerPool(max_workers=max_workers)
        self._delivery_tracker: DeliveryTracker = DeliveryTracker()
        self._batch_processor: BatchProcessor = BatchProcessor()
        self._dispatch_task: asyncio.Task[None] | None = None
        self._shutdown_event: asyncio.Event = asyncio.Event()
    
    def register_provider(self, name: str, provider: NotificationProvider) -> None:
        """Register a notification provider.
        
        Args:
            name: Provider name
            provider: Provider instance
        """
        self._providers[name] = provider
        logger.info("Registered provider: %s", name)
    
    def unregister_provider(self, name: str) -> None:
        """Unregister a notification provider.
        
        Args:
            name: Provider name
        """
        if name in self._providers:
            del self._providers[name]
            logger.info("Unregistered provider: %s", name)
    
    async def start(self) -> None:
        """Start the dispatcher."""
        if self._dispatch_task:
            return  # Already started
        
        await self._worker_pool.start()
        await self._batch_processor.start()
        
        self._shutdown_event.clear()
        self._dispatch_task = asyncio.create_task(self._dispatch_loop())
        logger.info("Started async dispatcher")
    
    async def stop(self) -> None:
        """Stop the dispatcher."""
        if not self._dispatch_task:
            return  # Already stopped
        
        self._shutdown_event.set()
        
        _ = self._dispatch_task.cancel()
        try:
            await self._dispatch_task
        except asyncio.CancelledError:
            pass
        
        await self._batch_processor.stop()
        await self._worker_pool.stop()
        
        self._dispatch_task = None
        logger.info("Stopped async dispatcher")

    def is_running(self) -> bool:
        """Check if the dispatcher is currently running.

        Returns:
            True if dispatcher is running, False otherwise
        """
        return self._dispatch_task is not None
    
    async def dispatch_message(
        self,
        message: Message,
        providers: list[str],
        priority: int = 1
    ) -> DispatchResult:
        """Dispatch a message to providers.

        Args:
            message: Message to dispatch
            providers: List of provider names
            priority: Message priority (higher = more urgent)

        Returns:
            Dispatch result
        """
        # Validate providers
        invalid_providers = [p for p in providers if p not in self._providers]
        if invalid_providers:
            raise ValueError(f"Unknown providers: {invalid_providers}")

        # Generate delivery ID first
        delivery_id = str(uuid.uuid4())

        # Create queued message with the delivery_id
        queued_msg = QueuedMessage(
            message=message,
            priority=priority,
            providers=providers,
            delivery_id=delivery_id
        )

        # Start tracking with the same delivery_id
        _ = self._delivery_tracker.track_delivery(message, providers, delivery_id)

        # Enqueue for processing
        await self._queue.enqueue(queued_msg)

        # Wait for completion (with timeout)
        return await self._wait_for_completion(queued_msg.delivery_id, timeout=30.0)
    
    async def _dispatch_loop(self) -> None:
        """Main dispatch loop."""
        try:
            while not self._shutdown_event.is_set():
                try:
                    # Get next message with timeout
                    message = await asyncio.wait_for(self._queue.dequeue(), timeout=1.0)
                    
                    # Submit to worker pool
                    _ = await self._worker_pool.submit_task(self._process_message, message)
                    
                except asyncio.TimeoutError:
                    continue  # Check shutdown event
                    
        except asyncio.CancelledError:
            logger.debug("Dispatch loop cancelled")
    
    async def _process_message(self, queued_msg: QueuedMessage) -> None:
        """Process a single message.
        
        Args:
            queued_msg: Message to process
        """
        logger.debug("Processing message: %s", queued_msg.delivery_id)
        
        # Send to all providers concurrently
        tasks: list[asyncio.Task[None]] = []
        for provider_name in queued_msg.providers:
            if provider_name in self._providers:
                task = asyncio.create_task(
                    self._send_to_provider(queued_msg, provider_name)
                )
                tasks.append(task)

        # Wait for all providers to complete
        _ = await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _send_to_provider(self, queued_msg: QueuedMessage, provider_name: str) -> None:
        """Send message to a specific provider.
        
        Args:
            queued_msg: Message to send
            provider_name: Name of the provider
        """
        provider = self._providers[provider_name]
        
        try:
            success = await provider.send_notification(queued_msg.message)
            self._delivery_tracker.update_delivery_status(
                queued_msg.delivery_id,
                provider_name,
                success
            )
        except Exception as e:
            logger.error("Failed to send to %s: %s", provider_name, e)
            self._delivery_tracker.update_delivery_status(
                queued_msg.delivery_id,
                provider_name,
                False,
                e
            )
    
    async def _wait_for_completion(self, delivery_id: str, timeout: float = 30.0) -> DispatchResult:
        """Wait for message delivery to complete.
        
        Args:
            delivery_id: Delivery ID to wait for
            timeout: Maximum time to wait
            
        Returns:
            Final dispatch result
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            result = self._delivery_tracker.get_delivery_status(delivery_id)
            if result and result.status in (DispatchStatus.SUCCESS, DispatchStatus.FAILED, DispatchStatus.PARTIAL):
                return result
            
            await asyncio.sleep(0.1)
        
        # Timeout - return current status
        result = self._delivery_tracker.get_delivery_status(delivery_id)
        if result:
            return result
        
        # This shouldn't happen, but create a failed result
        from mover_status.notifications.models.message import Message
        return DispatchResult(
            delivery_id=delivery_id,
            status=DispatchStatus.FAILED,
            message=Message(title="Unknown", content="Unknown"),
            providers=[]
        )
