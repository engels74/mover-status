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
    ...     monitor.subscribe(MonitorEvent.TRANSFER_COMPLETE, on_complete)
    ...     # Start monitoring
    ...     await monitor.start()
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import os
from pathlib import Path
from typing import Dict, Optional, Set, Any, Callable

import aiofiles
import aiofiles.os
import structlog

from config.constants import (
    MonitorEvent,
    MonitorState,
    NotificationLevel,
    MessageType,
    NotificationProvider,
    Version,
)
from config.settings import Settings
from core.calculator import TransferCalculator, TransferStats
from core.process import ProcessManager, ProcessStats, ProcessState
from notifications.base import NotificationError, NotificationProvider as BaseNotificationProvider
from notifications.factory import notification_factory
from utils.formatters import format_duration, format_eta
from utils.version import VersionChecker, Version as SemanticVersion

logger = structlog.get_logger(__name__)

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
        """Get size of a file or directory.

        Args:
            path: Path to get size for

        Returns:
            int: Total size in bytes
        """
        try:
            if path.is_file():
                return os.path.getsize(path)

            # Calculate directory size
            total_size = 0
            try:
                scanner = await aiofiles.os.scandir(str(path))
                for entry in scanner:
                    if self._should_exclude(Path(entry.path)):
                        continue
                    try:
                        if entry.is_file():
                            total_size += os.path.getsize(entry.path)
                        elif entry.is_dir():
                            total_size += await self.get_size(Path(entry.path))
                    except (OSError, PermissionError) as e:
                        logger.warning("Error getting size", path=entry.path, error=str(e))
            except Exception as e:
                logger.error("Error scanning directory", path=path, error=str(e))

            return total_size

        except (OSError, PermissionError) as e:
            logger.error("Error getting size", path=path, error=str(e))
            return 0

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
        start_time (Optional[datetime]): Monitoring start timestamp
        error_count (int): Number of errors encountered
        process_state (Optional[ProcessState]): Current process state
        transfer_stats (Optional[TransferStats]): Current transfer progress
    """
    start_time: Optional[datetime] = None
    error_count: int = 0
    process_state: Optional[ProcessState] = None
    transfer_stats: Optional[TransferStats] = None

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
        ...     monitor.subscribe(MonitorEvent.TRANSFER_COMPLETE, on_complete)
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
        self._process_manager = ProcessManager(settings)
        self._calculator = TransferCalculator(settings)
        self._providers: Dict[str, BaseNotificationProvider] = {}
        self._event_handlers: Dict[MonitorEvent, Set[Callable[..., Any]]] = {}
        self._event_lock = asyncio.Lock()
        self._provider_lock = asyncio.Lock()
        self._stats = MonitorStats()
        self._state = MonitorState.STOPPED
        self._stopping = False
        self._tasks: Set[asyncio.Task] = set()

        # Initialize directory scanner
        excluded = {Path(p).resolve() for p in settings.filesystem.excluded_paths}
        self._scanner = DirectoryScanner(excluded)

        self._version_checker = VersionChecker()

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

    def subscribe(self, event_type: MonitorEvent, handler: Callable[..., Any]) -> None:
        """Subscribe to specific monitor events.

        Args:
            event_type (MonitorEvent): Event type to listen for
            handler (Callable[..., Any]): Callback function to handle the event
        """
        if event_type not in self._event_handlers:
            self._event_handlers[event_type] = set()
        self._event_handlers[event_type].add(handler)

    def unsubscribe(self, event_type: MonitorEvent, handler: Callable[..., Any]) -> None:
        """Remove a subscription to monitor events.

        Args:
            event_type (MonitorEvent): Event type to unsubscribe from
            handler (Callable[..., Any]): Callback function to remove
        """
        if event_type in self._event_handlers:
            self._event_handlers[event_type].discard(handler)

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
        if self._state != MonitorState.STOPPED:
            raise RuntimeError("Monitor is already running")

        try:
            self._state = MonitorState.STARTING
            logger.info("Starting mover monitor")

            # Initialize notification providers
            await self._setup_providers()

            # Start monitoring
            self._state = MonitorState.MONITORING
            monitoring_task = asyncio.create_task(self._monitoring_loop())
            self._tasks.add(monitoring_task)
            monitoring_task.add_done_callback(self._tasks.discard)

            # Start version checking if enabled
            if self._settings.check_version:
                version_task = asyncio.create_task(self._version_check_loop())
                self._tasks.add(version_task)
                version_task.add_done_callback(self._tasks.discard)

        except Exception as err:
            self._state = MonitorState.ERROR
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
        if self._state == MonitorState.STOPPED:
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
        self._state = MonitorState.STOPPED
        logger.info("Monitor stopped")

    async def _setup_providers(self):
        """Initialize notification providers."""
        async with self._provider_lock:
            if self._settings.discord.enabled:
                try:
                    provider = await notification_factory.get_provider(
                        NotificationProvider.DISCORD,
                        self._settings.discord.dict()
                    )
                    if provider:
                        self._providers["discord"] = provider
                except Exception as e:
                    logger.error("Failed to initialize Discord provider", error=str(e))

            if self._settings.telegram.enabled:
                try:
                    provider = await notification_factory.get_provider(
                        NotificationProvider.TELEGRAM,
                        self._settings.telegram.dict()
                    )
                    if provider:
                        self._providers["telegram"] = provider
                except Exception as e:
                    logger.error("Failed to initialize Telegram provider", error=str(e))

    async def _create_progress_message(self, stats: TransferStats) -> str:
        """Create a progress notification message."""
        percent = stats.percent_complete
        remaining = stats.bytes_remaining
        elapsed = format_duration(stats.elapsed_time)
        eta = format_eta(datetime.now() + timedelta(seconds=stats.remaining_time))

        return (
            f"Transfer Progress: {percent:.1f}%\n"
            f"Remaining: {remaining} bytes\n"
            f"Elapsed: {elapsed}\n"
            f"ETA: {eta}"
        )

    async def _send_notifications(self, stats: TransferStats, force: bool = False) -> None:
        """Send progress notifications to all providers."""
        if not force and (
            not self._stats.start_time
            or (datetime.now() - self._stats.start_time)
            < timedelta(seconds=self._settings.monitoring.polling_interval)
        ):
            return

        message = await self._create_progress_message(stats)

        for provider in self._providers.values():
            try:
                await provider.notify(
                    message=str(message),
                    level=NotificationLevel.INFO,
                    message_type=MessageType.PROGRESS
                )
            except NotificationError as e:
                logger.error(
                    "Failed to send notification",
                    provider=provider.__class__.__name__,
                    error=str(e)
                )

        self._stats.start_time = datetime.now()

    async def _cleanup(self):
        """Clean up monitoring system resources."""
        async with self._provider_lock:
            for provider in self._providers.values():
                try:
                    await provider.notify(
                        "Monitoring stopped",
                        level=NotificationLevel.INFO,
                        message_type=MessageType.SYSTEM
                    )
                except Exception as e:
                    logger.error("Failed to send shutdown notification", provider=provider, error=str(e))
            self._providers.clear()

        self._event_handlers.clear()
        self._stats = MonitorStats()
        self._state = MonitorState.STOPPED

    async def _monitoring_loop(self) -> None:
        """Main monitoring loop."""
        while not self._stopping:
            try:
                # Check version if enabled
                if self._settings.check_version:
                    update_available = await self._version_checker.check_for_updates()
                    if update_available:
                        await self._notify_event(MonitorEvent.VERSION_CHECK)

                await self._update_monitoring()

            except Exception as e:
                logger.error("Monitoring loop error", error=str(e))
                self._stats.error_count += 1
                await self._notify_event(MonitorEvent.MONITOR_ERROR)

            await asyncio.sleep(self._settings.monitoring.polling_interval)

    async def _version_check_loop(self):
        """Periodic version check loop."""
        if not self._settings.check_version:
            return

        while not self._stopping:
            try:
                update_available, latest_version = await self._version_checker.check_for_updates()

                if update_available:
                    await self._notify_event(
                        MonitorEvent.VERSION_CHECK,
                        version=latest_version
                    )

            except Exception as e:
                logger.error("Version check failed", error=str(e))

            try:
                await asyncio.sleep(self._settings.monitoring.polling_interval)
            except asyncio.CancelledError:
                break

    async def _update_monitoring(self) -> None:
        """Update monitoring state and statistics."""
        try:
            # Get process stats and cache size
            process_stats = await self._process_manager._get_process_stats()
            cache_size = await self._get_cache_size()

            # Update calculator with latest stats
            transfer_stats = self._calculator.update_progress(
                current_size=cache_size
            )

            # Update monitoring stats
            self._stats.process_state = ProcessState(process_stats.process_state)
            self._stats.transfer_stats = transfer_stats

            # Send notifications if needed
            await self._send_notifications(transfer_stats)

            # Handle state transitions
            if process_stats.process_state == ProcessState.ERROR:
                self._stats.error_count += 1
                await self._notify_event(MonitorEvent.MONITOR_ERROR)
            elif process_stats.process_state == ProcessState.STOPPED:
                await self._notify_event(MonitorEvent.TRANSFER_COMPLETE)

        except Exception as e:
            logger.error("Error updating monitoring state", error=str(e))
            self._stats.error_count += 1
            await self._notify_event(MonitorEvent.MONITOR_ERROR)

    async def _get_cache_size(self) -> int:
        """Get total size of cache directory."""
        try:
            if not self._settings.filesystem.cache_path.exists():
                return 0

            total_size = 0
            try:
                scanner = await aiofiles.os.scandir(str(self._settings.filesystem.cache_path))
                for entry in scanner:
                    try:
                        if entry.is_file():
                            total_size += os.path.getsize(entry.path)
                        elif entry.is_dir():
                            total_size += await self._scanner.get_size(Path(entry.path))
                    except (OSError, PermissionError) as e:
                        logger.warning("Error scanning path", path=entry.path, error=str(e))
            except Exception as e:
                logger.error("Error iterating directory", error=str(e))

            return total_size
        except (OSError, PermissionError) as e:
            logger.error("Error scanning cache directory", error=str(e))
            return 0

    async def _notify_event(self, event: MonitorEvent, **kwargs) -> None:
        """Notify all subscribers of a monitor event.

        Args:
            event (MonitorEvent): Event instance to notify about
            **kwargs: Additional event data
        """
        async with self._event_lock:
            if event in self._event_handlers:
                for handler in self._event_handlers[event]:
                    try:
                        if asyncio.iscoroutinefunction(handler):
                            await handler(event, **kwargs)
                        else:
                            handler(event, **kwargs)
                    except Exception as e:
                        logger.error(
                            "Event handler failed",
                            event=event,
                            handler=handler,
                            error=str(e)
                        )

    async def _check_version(self) -> None:
        """Check for new version and notify if available."""
        try:
            current_version = SemanticVersion.from_string(Version.CURRENT)
            latest_version = await self._version_checker.get_latest_version()

            if latest_version and latest_version > current_version:
                await self._notify_event(
                    MonitorEvent.VERSION_CHECK,
                    current_version=Version.CURRENT,
                    latest_version=str(latest_version)
                )

        except Exception as e:
            logger.error("Version check failed", error=str(e))

    @property
    def state(self) -> MonitorState:
        """Get the current state of the monitoring system.

        Returns:
            MonitorState: Current monitor state
        """
        return self._state

    @property
    def stats(self) -> MonitorStats:
        """Get the current monitoring statistics.

        Returns:
            MonitorStats: Current monitoring statistics and state
        """
        return self._stats
