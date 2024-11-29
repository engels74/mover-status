# core/monitor.py

"""
Main monitoring loop and event handling for the MoverStatus system.
Coordinates process monitoring, progress calculation, and notifications.

Example:
    >>> from core.monitor import MoverMonitor
    >>> monitor = MoverMonitor(settings)
    >>> async with monitor:
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
    NotificationProvider,
    States,
)
from config.settings import Settings
from core.calculator import TransferCalculator, TransferStats
from core.process import ProcessManager
from notifications.base import NotificationError
from notifications.factory import notification_factory
from utils.formatters import format_size
from utils.version import version_checker

logger = get_logger(__name__)

class DirectoryScanner:
    """Asynchronous directory size scanner with path exclusion support."""

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
    """Combined monitoring statistics."""
    process_state: States.ProcessState = States.ProcessState.UNKNOWN
    transfer_stats: Optional[TransferStats] = None
    last_notification: Optional[datetime] = None
    error_count: int = 0
    start_time: Optional[datetime] = None
    events: Set[Events.MonitorEvent] = field(default_factory=set)

class MoverMonitor:
    """Coordinates process monitoring, transfer tracking, and notifications."""

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

        # Use Dict[str, NotificationProvider] for type hints to avoid name collision
        self._providers: Dict[str, NotificationProvider] = {}
        self._state = States.MonitorState.IDLE
        self._stopping = False
        self._tasks: Set[asyncio.Task] = set()
        self._event_handlers: Dict[Type[Events.MonitorEvent], Set[callable]] = {}

    async def __aenter__(self) -> 'MoverMonitor':
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.stop()

    def subscribe(self, event_type: Type[Events.MonitorEvent], handler: callable) -> None:
        """Subscribe to monitor events.

        Args:
            event_type: Type of event to subscribe to
            handler: Callback function
        """
        if event_type not in self._event_handlers:
            self._event_handlers[event_type] = set()
        self._event_handlers[event_type].add(handler)

    def unsubscribe(self, event_type: Type[Events.MonitorEvent], handler: callable) -> None:
        """Unsubscribe from monitor events.

        Args:
            event_type: Type of event to unsubscribe from
            handler: Callback function to remove
        """
        if event_type in self._event_handlers:
            self._event_handlers[event_type].discard(handler)

    async def _notify_event(self, event: Events.MonitorEvent) -> None:
        """Notify subscribers of an event.

        Args:
            event: Event to notify about
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

        Raises:
            RuntimeError: If monitoring is already active
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
            if self._settings.check_version:
                version_task = asyncio.create_task(self._version_check_loop())
                self._tasks.add(version_task)
                version_task.add_done_callback(self._tasks.discard)

        except Exception as err:
            self._state = States.MonitorState.ERROR
            logger.error("Monitor start failed", error=str(err))
            raise RuntimeError("Failed to start monitoring") from err

    async def stop(self) -> None:
        """Stop the monitoring system gracefully."""
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
        """Initialize configured notification providers."""
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

    async def _cleanup(self) -> None:
        """Clean up resources and connections."""
        self._process_manager.stop()
        self._calculator.reset()
        await self._scanner.clear_cache()

        for provider in self._providers.values():
            try:
                if hasattr(provider, 'disconnect'):
                    await provider.disconnect()
            except Exception as err:
                logger.warning(
                    "Provider disconnect error",
                    error=str(err)
                )

    async def _get_cache_size(self) -> int:
        """Get current cache directory size.

        Returns:
            int: Size in bytes

        Raises:
            RuntimeError: If size calculation fails
        """
        try:
            cache_path = Path(self._settings.filesystem.cache_path)
            if not await aiofiles.os.path.exists(str(cache_path)):
                raise RuntimeError(f"Cache path does not exist: {cache_path}")
            return await self._scanner.get_size(cache_path)
        except Exception as err:
            logger.error("Cache size error", error=str(err))
            raise RuntimeError("Cache size calculation failed") from err

    async def _send_notifications(
        self,
        stats: TransferStats,
        force: bool = False
    ) -> None:
        """Send notifications to all configured providers.

        Args:
            stats: Current transfer statistics
            force: Send notification regardless of increment check
        """
        now = datetime.now()
        if not force and self._stats.last_notification:
            time_since_last = (now - self._stats.last_notification).total_seconds()
            if time_since_last < self._settings.notification_increment:
                return

        notification_tasks = []
        for provider in self._providers.values():
            try:
                task = asyncio.create_task(provider.notify(
                    template=self._settings.message_template,
                    stats=stats
                ))
                notification_tasks.append(task)
            except Exception as err:
                logger.error("Notification creation error", error=str(err))

        if notification_tasks:
            try:
                await asyncio.gather(*notification_tasks)
                self._stats.last_notification = now
            except NotificationError as err:
                logger.error("Notification sending error", error=str(err))

    async def _update_monitoring(self) -> None:
        """Update monitoring state and statistics."""
        try:
            # Update process state
            is_running = await self._process_manager.is_running()
            new_state = self._process_manager.current_state

            if new_state != self._stats.process_state:
                self._stats.process_state = new_state
                await self._notify_event(Events.MonitorEvent.STATE_CHANGED)

            # Handle process state
            if is_running and not self._stats.start_time:
                # Process just started
                self._stats.start_time = datetime.now()
                initial_size = await self._get_cache_size()
                self._calculator.initialize_transfer(initial_size)
                logger.info(
                    "Transfer started",
                    initial_size=format_size(initial_size)
                )
                await self._notify_event(Events.MonitorEvent.TRANSFER_STARTED)

            elif is_running:
                # Process is running
                current_size = await self._get_cache_size()
                stats = self._calculator.update_progress(current_size)
                self._stats.transfer_stats = stats
                await self._send_notifications(stats)
                await self._notify_event(Events.MonitorEvent.TRANSFER_PROGRESS)

            elif self._stats.start_time and not is_running:
                # Process just completed
                if self._stats.transfer_stats:
                    await self._send_notifications(
                        self._stats.transfer_stats,
                        force=True
                    )
                self._calculator.reset()
                self._stats.start_time = None
                self._stats.transfer_stats = None
                logger.info("Transfer completed")
                await self._notify_event(Events.MonitorEvent.TRANSFER_COMPLETED)

        except Exception as err:
            self._stats.error_count += 1
            logger.error("Monitoring update error", error=str(err))
            if self._stats.error_count >= 3:
                self._state = States.MonitorState.ERROR
                await self._notify_event(Events.MonitorEvent.ERROR)
                raise RuntimeError("Too many monitoring errors") from err

    async def _monitoring_loop(self) -> None:
        """Main monitoring loop."""
        try:
            while not self._stopping:
                try:
                    await self._update_monitoring()
                    await asyncio.sleep(self._settings.monitoring.polling_interval)
                except asyncio.CancelledError:
                    raise
                except Exception as err:
                    logger.error("Monitoring loop error", error=str(err))
                    await asyncio.sleep(5)  # Brief delay before retry

        except asyncio.CancelledError:
            logger.info("Monitoring loop cancelled")
            raise

    async def _version_check_loop(self) -> None:
        """Periodic version check loop."""
        while not self._stopping:
            try:
                update_available, latest_version = await version_checker.check_for_updates()
                if update_available:
                    logger.info(
                        "Update available",
                        current=str(version_checker.current_version),
                        latest=latest_version
                    )
                    await self._notify_event(Events.MonitorEvent.UPDATE_AVAILABLE)
            except Exception as err:
                logger.error("Version check error", error=str(err))

            await asyncio.sleep(3600)  # Check once per hour

    @property
    def state(self) -> States.MonitorState:
        """Get current monitor state."""
        return self._state

    @property
    def stats(self) -> MonitorStats:
        """Get current monitoring statistics."""
        return self._stats
