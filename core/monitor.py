# core/monitor.py

"""
Main monitoring loop and event handling for the MoverStatus system.
Coordinates process monitoring, progress calculation, and notifications.

Example:
    >>> from core.monitor import MoverMonitor
    >>> monitor = MoverMonitor(settings)
    >>> await monitor.start()
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, Optional, Set, Tuple

import aiofiles
import aiofiles.os
from structlog import get_logger

from config.constants import NotificationProvider as ProviderType
from config.settings import Settings
from core.calculator import TransferCalculator, TransferStats
from core.process import ProcessManager, ProcessState
from notifications.base import NotificationError
from notifications.factory import NotificationFactory
from utils.formatters import format_size
from utils.version import version_checker

logger = get_logger(__name__)

class MonitorState(str, Enum):
    """Possible states of the monitoring system."""
    IDLE = "idle"
    STARTING = "starting"
    MONITORING = "monitoring"
    ERROR = "error"
    STOPPED = "stopped"

@dataclass
class MonitorStats:
    """Combined statistics from process and transfer monitoring."""
    process_state: ProcessState
    transfer_stats: Optional[TransferStats] = None
    last_notification_time: Optional[datetime] = None
    error_count: int = 0
    start_time: Optional[datetime] = None

class DirectoryScanner:
    """Asynchronous directory size scanner with caching and exclusion support."""

    def __init__(self, excluded_paths: Set[Path] = None):
        """Initialize directory scanner.

        Args:
            excluded_paths: Set of paths to exclude from scanning
        """
        self._excluded_paths = excluded_paths or set()
        self._cache: Dict[Path, Tuple[int, float]] = {}  # path -> (size, timestamp)
        self._cache_ttl = 5.0  # Cache entries valid for 5 seconds

    def _should_exclude(self, path: Path) -> bool:
        """Check if path should be excluded from scanning.

        Args:
            path: Path to check

        Returns:
            bool: True if path should be excluded
        """
        return any(
            try_path in self._excluded_paths
            for try_path in (path, *path.parents)
        )

    def _is_cache_valid(self, path: Path) -> bool:
        """Check if cached size for path is still valid.

        Args:
            path: Path to check

        Returns:
            bool: True if cache entry is valid
        """
        if path not in self._cache:
            return False
        _, timestamp = self._cache[path]
        return (datetime.now().timestamp() - timestamp) < self._cache_ttl

    async def get_size(self, path: Path) -> int:
        """Get total size of directory and its contents.

        Args:
            path: Directory path to scan

        Returns:
            int: Total size in bytes

        Raises:
            OSError: If path cannot be accessed
        """
        if path.is_file():
            stat = await aiofiles.os.stat(path)
            return stat.st_size

        if self._is_cache_valid(path):
            return self._cache[path][0]

        total_size = 0
        try:
            async for entry in aiofiles.os.scandir(str(path)):
                entry_path = Path(entry.path)
                if self._should_exclude(entry_path):
                    continue

                try:
                    if entry.is_file():
                        stat = await aiofiles.os.stat(entry.path)
                        total_size += stat.st_size
                    elif entry.is_dir():
                        total_size += await self.get_size(entry_path)
                except (PermissionError, FileNotFoundError) as err:
                    logger.warning(
                        f"Error accessing {entry.path}",
                        error=str(err)
                    )
                    continue

            # Cache the result
            self._cache[path] = (total_size, datetime.now().timestamp())
            return total_size

        except OSError as err:
            logger.error(
                f"Error scanning directory {path}",
                error=str(err)
            )
            raise

class MoverMonitor:
    """
    Main monitoring system coordinator.
    Handles process detection, progress calculation, and notification distribution.
    """

    def __init__(self, settings: Settings):
        """Initialize monitor with settings.

        Args:
            settings: Application settings instance
        """
        self._settings = settings
        self._process_manager = ProcessManager(settings)
        self._calculator = TransferCalculator(settings)
        self._notification_factory = NotificationFactory()
        self._providers: Dict[str, NotificationError] = {}
        self._state = MonitorState.IDLE
        self._stats = MonitorStats(process_state=ProcessState.UNKNOWN)
        self._stopping = False
        self._tasks: Set[asyncio.Task] = set()
        # Initialize directory scanner with excluded paths
        excluded_paths = {Path(p) for p in settings.excluded_paths}
        self._scanner = DirectoryScanner(excluded_paths)

    async def start(self) -> None:
        """Start the monitoring system.

        Raises:
            RuntimeError: If monitoring is already active
        """
        if self._state != MonitorState.IDLE:
            raise RuntimeError("Monitor is already running")

        try:
            self._state = MonitorState.STARTING
            logger.info("Starting mover monitor")

            # Initialize notification providers
            await self._setup_providers()

            # Start the main monitoring loop
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
            logger.error("Failed to start monitor", error=str(err))
            raise RuntimeError("Failed to start monitoring system") from err

    async def stop(self) -> None:
        """Stop the monitoring system gracefully."""
        if self._state == MonitorState.STOPPED:
            return

        logger.info("Stopping mover monitor")
        self._stopping = True

        # Cancel all running tasks
        for task in self._tasks:
            task.cancel()

        # Wait for tasks to complete
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)

        # Clean up resources
        await self._cleanup()
        self._state = MonitorState.STOPPED
        logger.info("Monitor stopped")

    async def _setup_providers(self) -> None:
        """Initialize configured notification providers."""
        for provider_id in self._settings.active_providers:
            try:
                config = None
                if provider_id == ProviderType.DISCORD:
                    config = self._settings.discord.to_provider_config()
                elif provider_id == ProviderType.TELEGRAM:
                    config = self._settings.telegram.to_provider_config()

                if config:
                    provider = await self._notification_factory.create_provider(
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
        # Stop process monitoring
        self._process_manager.stop()

        # Reset calculator
        self._calculator.reset()

        # Clean up notification providers
        for provider in self._providers.values():
            try:
                if hasattr(provider, 'disconnect'):
                    await provider.disconnect()
            except Exception as err:
                logger.warning(
                    "Error disconnecting provider",
                    error=str(err)
                )

    async def _handle_process_start(self) -> None:
        """Handle process start event."""
        self._stats.start_time = datetime.now()
        initial_size = await self._get_cache_size()
        self._calculator.initialize_transfer(initial_size)
        logger.info(
            "Transfer started",
            initial_size=format_size(initial_size)
        )

    async def _handle_process_running(self) -> None:
        """Handle running process updates."""
        current_size = await self._get_cache_size()
        stats = self._calculator.update_progress(current_size)
        self._stats.transfer_stats = stats
        await self._send_notifications(stats)

    async def _handle_process_completion(self) -> None:
        """Handle process completion event."""
        if self._stats.transfer_stats:
            await self._send_notifications(
                self._stats.transfer_stats,
                force=True
            )
        self._calculator.reset()
        self._stats.start_time = None
        self._stats.transfer_stats = None
        logger.info("Transfer completed")

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
        # Check if notification should be sent based on increment
        if not force:
            last_notified = getattr(self._stats.last_notification_time, 'timestamp', lambda: 0)()
            if (datetime.now().timestamp() - last_notified) < self._settings.notification_increment:
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
                logger.error("Failed to create notification task", error=str(err))

        if notification_tasks:
            try:
                await asyncio.gather(*notification_tasks)
                self._stats.last_notification_time = datetime.now()
            except NotificationError as err:
                logger.error("Failed to send notifications", error=str(err))

    async def _monitoring_loop(self) -> None:
        """Main monitoring loop."""
        try:
            while not self._stopping:
                try:
                    # Check mover process state
                    is_running = await self._process_manager.is_running()
                    current_state = self._process_manager.current_state

                    if current_state != self._stats.process_state:
                        logger.info(
                            "Process state changed",
                            old_state=self._stats.process_state,
                            new_state=current_state
                        )
                        self._stats.process_state = current_state

                    # Handle process state transitions
                    if is_running and not self._stats.start_time:
                        await self._handle_process_start()
                    elif is_running:
                        await self._handle_process_running()
                    elif self._stats.start_time and not is_running:
                        await self._handle_process_completion()

                    await asyncio.sleep(self._settings.polling_interval)

                except Exception as err:
                    self._stats.error_count += 1
                    logger.error("Monitoring error", error=str(err))
                    if self._stats.error_count >= 3:
                        raise RuntimeError("Too many monitoring errors") from err
                    await asyncio.sleep(5)  # Brief delay before retry

        except asyncio.CancelledError:
            logger.info("Monitoring loop cancelled")
            raise
        except Exception as err:
            self._state = MonitorState.ERROR
            logger.error("Fatal monitoring error", error=str(err))
            raise RuntimeError("Fatal monitoring error") from err

    async def _version_check_loop(self) -> None:
        """Periodic version check loop."""
        while not self._stopping:
            try:
                update_available, latest_version = await version_checker.check_for_updates()
                if update_available:
                    logger.info(
                        "Update available",
                        current_version=str(version_checker.current_version),
                        latest_version=latest_version
                    )
            except Exception as err:
                logger.error("Version check failed", error=str(err))

            await asyncio.sleep(3600)  # Check once per hour

    async def _get_cache_size(self) -> int:
        """Get current cache directory size using async operations.

        Returns:
            int: Size in bytes

        Raises:
            RuntimeError: If size calculation fails
        """
        try:
            cache_path = Path(self._settings.cache_path)
            if not await aiofiles.os.path.exists(str(cache_path)):
                raise RuntimeError(f"Cache path does not exist: {cache_path}")
            return await self._scanner.get_size(cache_path)
        except Exception as err:
            logger.error("Failed to get cache size", error=str(err))
            raise RuntimeError("Cache size calculation failed") from err

    @property
    def state(self) -> MonitorState:
        """Get current monitor state."""
        return self._state

    @property
    def stats(self) -> MonitorStats:
        """Get current monitoring statistics."""
        return self._stats
