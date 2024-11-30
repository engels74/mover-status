# core/monitor.py

"""
Core monitoring system for tracking file transfer operations.
This module implements the main monitoring loop and event handling system for
tracking file transfers, calculating progress, and sending notifications.

Components:
- DirectoryScanner: Async directory size calculation with caching
- MonitorStats: Statistics tracking for transfers and events
- MoverMonitor: Main coordinator for monitoring and notifications

Features:
- Asynchronous directory scanning with path exclusions
- Real-time transfer progress calculation
- Event-based notification system
- Version checking and update notifications
- Resource cleanup and graceful shutdown

Example:
    >>> from core.monitor import MoverMonitor
    >>> from config.settings import Settings
    >>>
    >>> settings = Settings.from_file("config.yaml")
    >>> monitor = MoverMonitor(settings)
    >>>
    >>> async with monitor:
    ...     # Subscribe to events if needed
    ...     monitor.subscribe(Events.TransferComplete, on_complete)
    ...     # Start monitoring
    ...     await monitor.start()
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Set, Type

import aiofiles
from structlog import get_logger

from config.constants import (
    Events,
    States,
)
from config.settings import Settings
from core.calculator import TransferCalculator, TransferStats
from core.process import ProcessManager
from notifications.base import NotificationError, NotificationProvider
from notifications.factory import notification_factory
from utils.version import version_checker

logger = get_logger(__name__)

class DirectoryScanner:
    """Asynchronous directory size scanner with caching and exclusion support.

    This class provides efficient directory size calculation with the following features:
    - Asynchronous scanning using aiofiles
    - Path exclusion for skipping specific directories
    - Size caching with configurable TTL
    - Thread-safe cache access

    Attributes:
        _excluded_paths (Set[Path]): Paths to exclude from scanning
        _cache (Dict[Path, tuple[int, float]]): Size cache with timestamps
        _cache_ttl (float): Cache entry lifetime in seconds
        _lock (asyncio.Lock): Thread safety for cache access

    Example:
        >>> scanner = DirectoryScanner({Path("/tmp")}, cache_ttl=10.0)
        >>> size = await scanner.get_size(Path("/data"))
    """

    def __init__(self, excluded_paths: Set[Path], cache_ttl: float = 5.0):
        """Initialize directory scanner.

        Args:
            excluded_paths: Set of paths to exclude from scanning
            cache_ttl: Cache time-to-live in seconds
        """
        self._excluded_paths = excluded_paths
        self._cache: Dict[Path, tuple[int, float]] = {}
        self._cache_ttl = cache_ttl
        self._lock = asyncio.Lock()

    def _should_exclude(self, path: Path) -> bool:
        """Check if path should be excluded from scanning."""
        return any(
            try_path in self._excluded_paths
            for try_path in (path, *path.parents)
        )

    def _is_cache_valid(self, path: Path, current_time: float) -> bool:
        """Check if cached size for path is still valid."""
        if path not in self._cache:
            return False
        _, timestamp = self._cache[path]
        return (current_time - timestamp) < self._cache_ttl

    async def get_size(self, path: Path) -> int:
        """Get total size of directory and contents asynchronously.

        Args:
            path: Directory path to scan

        Returns:
            int: Total size in bytes

        Raises:
            OSError: If path cannot be accessed
        """
        current_time = asyncio.get_event_loop().time()

        # Check cache first
        async with self._lock:
            if self._is_cache_valid(path, current_time):
                return self._cache[path][0]

        # Handle single file
        if await aiofiles.os.path.isfile(str(path)):
            stat = await aiofiles.os.stat(str(path))
            return stat.st_size

        # Scan directory
        total_size = 0
        try:
            async for entry in aiofiles.os.scandir(str(path)):
                entry_path = Path(entry.path)
                if self._should_exclude(entry_path):
                    continue

                try:
                    if await aiofiles.os.path.isfile(entry.path):
                        stat = await aiofiles.os.stat(entry.path)
                        total_size += stat.st_size
                    elif await aiofiles.os.path.isdir(entry.path):
                        total_size += await self.get_size(entry_path)
                except (PermissionError, FileNotFoundError) as err:
                    logger.warning(
                        "Error accessing path",
                        path=entry.path,
                        error=str(err)
                    )

            # Update cache
            async with self._lock:
                self._cache[path] = (total_size, current_time)
            return total_size

        except OSError as err:
            logger.error(
                "Directory scan error",
                path=str(path),
                error=str(err)
            )
            raise

    async def clear_cache(self) -> None:
        """Clear the size cache."""
        async with self._lock:
            self._cache.clear()

@dataclass
class MonitorStats:
    """Statistics tracking for the monitoring system.

    Tracks various metrics about the current monitoring state, including:
    - Process state and transfer statistics
    - Error counts and notification timing
    - Active monitoring events
    - Start time for duration calculation

    Attributes:
        process_state (States.ProcessState): Current process state
        transfer_stats (Optional[TransferStats]): Current transfer progress
        last_notification (Optional[datetime]): Timestamp of last notification
        error_count (int): Number of errors encountered
        start_time (Optional[datetime]): Monitoring start timestamp
        events (Set[Events.MonitorEvent]): Currently active events
    """
    process_state: States.ProcessState = States.ProcessState.UNKNOWN
    transfer_stats: Optional[TransferStats] = None
    last_notification: Optional[datetime] = None
    error_count: int = 0
    start_time: Optional[datetime] = None
    events: Set[Events.MonitorEvent] = field(default_factory=set)


class MoverMonitor:
    """Main coordinator for file transfer monitoring and notifications.

    This class orchestrates the monitoring system with the following responsibilities:
    - Process state tracking and statistics collection
    - Directory size calculation and progress updates
    - Event-based notification system
    - Provider management and notification delivery
    - Resource cleanup and graceful shutdown

    The monitor uses an event-driven architecture where subscribers can receive
    notifications about various monitoring events (transfer complete, errors, etc.).
    It also manages multiple notification providers for different delivery methods.

    Attributes:
        state (property): Current monitoring state
        stats (property): Current monitoring statistics

    Example:
        >>> monitor = MoverMonitor(settings)
        >>> async with monitor:
        ...     # Subscribe to transfer completion
        ...     monitor.subscribe(Events.TransferComplete, on_complete)
        ...     # Start monitoring
        ...     await monitor.start()
        ...     # Monitor will run until stopped
        ...     await asyncio.sleep(3600)
        ...     # Stop monitoring
        ...     await monitor.stop()
    """

    def __init__(self, settings: Settings):
        """Initialize monitor with settings.

        Args:
            settings: Application configuration
        """
        self._settings = settings
        self._stats = MonitorStats()
        self._process_manager = ProcessManager(settings)
        self._calculator = TransferCalculator(settings)

        # Initialize directory scanner
        excluded = {Path(p).resolve() for p in settings.filesystem.excluded_paths}
        self._scanner = DirectoryScanner(excluded)

        # Provider management
        self._providers: Dict[str, NotificationProvider] = {}
        self._state = States.MonitorState.IDLE
        self._stopping = False
        self._tasks: Set[asyncio.Task] = set()
        self._event_handlers: Dict[Type[Events.MonitorEvent], Set[callable]] = {}

        # Thread safety
        self._state_lock = asyncio.Lock()
        self._provider_lock = asyncio.Lock()
        self._task_lock = asyncio.Lock()
        self._event_lock = asyncio.Lock()

    async def __aenter__(self) -> 'MoverMonitor':
        """Async context manager entry point.

        Returns:
            MoverMonitor: Self reference for context management
        """
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit point.

        Ensures graceful shutdown of the monitoring system by calling stop().
        """
        await self.stop()

    def subscribe(self, event_type: Type[Events.MonitorEvent], handler: callable) -> None:
        """Subscribe to specific monitor events.

        Registers a callback function to be called when events of the specified
        type occur. The handler can be either a regular function or a coroutine.

        Args:
            event_type (Type[Events.MonitorEvent]): Event type to listen for
            handler (callable): Callback function to handle the event

        Example:
            >>> async def on_complete(event):
            ...     print(f"Transfer completed: {event.stats}")
            >>> monitor.subscribe(Events.TransferComplete, on_complete)
        """
        async with self._event_lock:
            if event_type not in self._event_handlers:
                self._event_handlers[event_type] = set()
            self._event_handlers[event_type].add(handler)

    async def unsubscribe(self, event_type: Type[Events.MonitorEvent], handler: callable) -> None:
        """Remove a subscription to monitor events.

        Unregisters a previously registered callback function for the specified
        event type. If the handler is not found, this operation is a no-op.

        Args:
            event_type (Type[Events.MonitorEvent]): Event type to unsubscribe from
            handler (callable): Callback function to remove
        """
        async with self._event_lock:
            if event_type in self._event_handlers:
                self._event_handlers[event_type].discard(handler)

    async def _notify_event(self, event: Events.MonitorEvent) -> None:
        """Notify all subscribers of a monitor event.

        Calls all registered handlers for the event type, handling both regular
        functions and coroutines appropriately. Errors in handlers are logged
        but do not stop other handlers from being called.

        Args:
            event (Events.MonitorEvent): Event instance to notify about
        """
        if event.__class__ in self._event_handlers:
            for handler in self._event_handlers[event.__class__]:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(event)
                    else:
                        handler(event)
                except Exception as err:
                    logger.error(
                        "Event handler error",
                        event=event.__class__.__name__,
                        error=str(err)
                    )

    async def start(self) -> None:
        """Start the monitoring system.

        Initializes notification providers and starts the main monitoring loop.
        If version checking is enabled in settings, also starts the version
        check loop.

        The monitoring system transitions through the following states:
        1. IDLE -> STARTING: Initial state transition
        2. STARTING -> MONITORING: After provider setup
        3. MONITORING: Active monitoring state
        4. ERROR: If startup fails

        Raises:
            RuntimeError: If monitoring is already active or startup fails
        """
        if self._state != States.MonitorState.IDLE:
            raise RuntimeError("Monitor is already running")

        try:
            self._state = States.MonitorState.STARTING
            logger.info("Starting mover monitor")

            # Initialize notification providers
            await self._setup_providers()

            # Start monitoring
            self._state = States.MonitorState.MONITORING
            monitoring_task = asyncio.create_task(self._monitoring_loop())
            self._tasks.add(monitoring_task)
            monitoring_task.add_done_callback(self._tasks.discard)

            # Start version checking if enabled
            if self._settings.application.check_version:
                version_task = asyncio.create_task(self._version_check_loop())
                self._tasks.add(version_task)
                version_task.add_done_callback(self._tasks.discard)

        except Exception as err:
            self._state = States.MonitorState.ERROR
            logger.error("Monitor start failed", error=str(err))
            raise RuntimeError("Failed to start monitoring") from err

    async def stop(self) -> None:
        """Stop the monitoring system gracefully.

        Performs the following shutdown sequence:
        1. Sets stopping flag to prevent new tasks
        2. Cancels all running tasks
        3. Waits for tasks to complete
        4. Cleans up resources
        5. Transitions to STOPPED state

        This method is idempotent and can be called multiple times safely.
        If the system is already stopped, this is a no-op.
        """
        if self._state == States.MonitorState.STOPPED:
            return

        logger.info("Stopping mover monitor")
        self._stopping = True

        # Cancel all tasks
        for task in self._tasks:
            task.cancel()

        # Wait for tasks to complete
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)

        # Clean up
        await self._cleanup()
        self._state = States.MonitorState.STOPPED
        logger.info("Monitor stopped")

    async def _setup_providers(self) -> None:
        """Initialize and configure notification providers.

        Creates provider instances for each enabled provider in settings using
        the notification factory. Currently supports Discord and Telegram providers.
        Provider initialization failures are logged but don't stop other providers.

        Provider initialization sequence:
        1. Load provider-specific configuration
        2. Create provider instance via factory
        3. Store provider in internal registry
        """
        async with self._provider_lock:
            for provider_id in self._settings.active_providers:
                try:
                    config = None
                    if provider_id == NotificationProvider.DISCORD:
                        config = self._settings.discord.to_provider_config()
                    elif provider_id == NotificationProvider.TELEGRAM:
                        config = self._settings.telegram.to_provider_config()

                    if config:
                        provider = await notification_factory.create_provider(
                            provider_id, config
                        )
                        self._providers[provider_id] = provider
                        logger.info(f"Initialized {provider_id} provider")

                except Exception as err:
                    logger.error(
                        f"Failed to initialize {provider_id} provider",
                        error=str(err)
                    )

    async def _send_notifications(
        self,
        stats: TransferStats,
        force: bool = False
    ) -> None:
        """Send progress notifications to all configured providers.

        Creates a progress message from the current transfer statistics and
        sends it to each configured notification provider. Notification failures
        for individual providers are logged but don't prevent other providers
        from receiving updates.

        Args:
            stats (TransferStats): Current transfer progress statistics
            force (bool, optional): If True, send notification regardless of
                progress increment check. Defaults to False.

        Note:
            The notification includes:
            - Completion percentage
            - Remaining size/files
            - Elapsed time
            - Estimated time to completion
            - Custom progress message
        """
        async with self._provider_lock:
            for provider in self._providers.values():
                try:
                    # Create progress message
                    message = self._create_progress_message(stats)

                    # Send notification
                    await provider.notify_progress(
                        stats.percent_complete,
                        stats.remaining_formatted,
                        stats.elapsed_formatted,
                        stats.etc_formatted,
                        description=message
                    )

                except NotificationError as err:
                    logger.error(
                        "Failed to send notification",
                        provider=provider.__class__.__name__,
                        error=str(err)
                    )

    async def _update_monitoring(self) -> None:
        """Update monitoring state and transfer statistics.

        Performs a full update cycle:
        1. Update process state from process manager
        2. Calculate current cache directory size
        3. Update transfer statistics with calculator
        4. Send notifications if progress threshold reached
        5. Emit monitoring events based on state changes
        """
        # Update process state
        self._stats.process_state = await self._process_manager.get_state()

        try:
            # Get current cache size
            cache_size = await self._get_cache_size()

            # Update transfer stats
            stats = await self._calculator.update(cache_size)
            self._stats.transfer_stats = stats

            # Send notifications
            await self._send_notifications(stats)

        except Exception as err:
            logger.error("Monitoring update failed", error=str(err))
            self._stats.error_count += 1

    async def _cleanup(self) -> None:
        """Clean up monitoring system resources.

        Performs cleanup tasks:
        1. Close all notification providers
        2. Clear event handlers
        3. Reset internal state
        """
        # Close providers
        async with self._provider_lock:
            for provider in self._providers.values():
                try:
                    await provider.close()
                except Exception as err:
                    logger.error(
                        "Provider cleanup error",
                        provider=provider.__class__.__name__,
                        error=str(err)
                    )
            self._providers.clear()

        # Clear handlers
        async with self._event_lock:
            self._event_handlers.clear()

    async def _get_cache_size(self) -> int:
        """Calculate the current size of the cache directory.

        Uses the directory scanner to calculate the total size of the cache
        directory, respecting path exclusions defined in settings.

        Returns:
            int: Total size of cache directory in bytes

        Raises:
            RuntimeError: If size calculation fails
        """
        try:
            return await self._scanner.get_size(
                Path(self._settings.filesystem.cache_path)
            )
        except OSError as err:
            logger.error(
                "Cache size calculation failed",
                error=str(err)
            )
            raise RuntimeError("Failed to calculate cache size") from err

    async def _monitoring_loop(self) -> None:
        """Main monitoring loop.

        Runs the monitoring update cycle at the configured interval. The loop
        continues until the stopping flag is set or an unrecoverable error occurs.

        The loop performs the following steps:
        1. Update monitoring state and statistics
        2. Sleep for the configured interval
        3. Check for stopping condition
        """
        self._stats.start_time = datetime.now()
        logger.info("Monitoring loop started")

        while not self._stopping:
            try:
                await self._update_monitoring()
                await asyncio.sleep(self._settings.monitoring.update_interval)
            except asyncio.CancelledError:
                break
            except Exception as err:
                logger.error("Monitoring loop error", error=str(err))
                if self._stats.error_count >= self._settings.monitoring.max_errors:
                    logger.error("Maximum error count reached, stopping monitor")
                    break
                await asyncio.sleep(1)

        logger.info("Monitoring loop stopped")

    async def _version_check_loop(self) -> None:
        """Periodic version check loop.

        Checks for new versions of the application at the configured interval.
        If a new version is found, emits an update available event.

        The loop continues until the stopping flag is set or an error occurs.
        Version check failures are logged but don't stop the loop.
        """
        logger.info("Version check loop started")

        while not self._stopping:
            try:
                current = await version_checker.get_current_version()
                latest = await version_checker.get_latest_version()

                if latest > current:
                    await self._notify_event(Events.UpdateAvailable(latest))

                await asyncio.sleep(self._settings.application.version_check_interval)
            except asyncio.CancelledError:
                break
            except Exception as err:
                logger.error("Version check error", error=str(err))
                await asyncio.sleep(60)

        logger.info("Version check loop stopped")

    @property
    def state(self) -> States.MonitorState:
        """Get the current state of the monitoring system.

        Returns:
            States.MonitorState: Current monitor state
        """
        return self._state

    @property
    def stats(self) -> MonitorStats:
        """Get the current monitoring statistics.

        Returns:
            MonitorStats: Current monitoring statistics and state
        """
        return self._stats
