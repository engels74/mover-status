"""Application orchestrator coordinating monitoring, progress tracking, and plugins.

The orchestrator wires together the monitoring engine, disk tracker, progress
calculator, and plugin system using structured concurrency. It is responsible
for:

- Loading enabled notification providers through the plugin loader
- Managing provider health information in the registry
- Running the mover lifecycle monitor loop
- Capturing disk usage baselines and periodic samples
- Calculating progress metrics and tracking threshold crossings
- Handling graceful shutdown and cleanup

This module focuses on coordination only; notification dispatch is handled by
the NotificationDispatcher. Provider-specific details remain isolated within
plugin packages to preserve architectural boundaries (Requirements 3.x/9.x).
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import AsyncGenerator, Callable, Mapping, Sequence
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from mover_status.core.calculation import calculate_progress_data, evaluate_threshold_crossed
from mover_status.core.config import MainConfig
from mover_status.core.disk_tracker import (
    capture_baseline_async,
    sample_current_usage_async,
)
from mover_status.core.dispatcher import NotificationDispatcher
from mover_status.core.monitoring import (
    MoverLifecycleEvent,
    MoverState,
    monitor_mover_lifecycle,
)
from mover_status.plugins import LoadedPlugin, PluginLoader, ProviderRegistry
from mover_status.types import DiskSample, NotificationData, NotificationProvider, ProgressData
from mover_status.utils.formatting import format_rate, format_size

__all__ = ["Orchestrator"]

type LifecycleMonitorFactory = Callable[[Path, float], AsyncGenerator[MoverLifecycleEvent]]
type ProgressCalculator = Callable[[int, int, Sequence[DiskSample], int], ProgressData]
type ThresholdEvaluator = Callable[[float, Sequence[float], Sequence[float]], float | None]
type ProviderInitKwargs = Mapping[str, Mapping[str, object]]

_DEFAULT_RATE_WINDOW_SIZE = 3


class BaselineSampler(Protocol):
    """Callable protocol for asynchronous baseline sampling.

    Implementations capture initial disk usage before monitoring begins.

    Example:
        async def sampler(paths: Sequence[Path], *, exclusion_paths: Sequence[Path] | None = None) -> DiskSample:
            return await capture_baseline_async(paths, exclusion_paths=exclusion_paths)
    """

    async def __call__(
        self,
        paths: Sequence[Path],
        *,
        exclusion_paths: Sequence[Path] | None = None,
    ) -> DiskSample: ...


class UsageSampler(Protocol):
    """Callable protocol for asynchronous usage sampling during monitoring.

    Implementations collect ongoing disk usage snapshots with optional caching.

    Example:
        async def sampler(
            paths: Sequence[Path],
            *,
            exclusion_paths: Sequence[Path] | None = None,
            cache_duration_seconds: int = 30,
        ) -> DiskSample:
            return await sample_current_usage_async(
                paths,
                exclusion_paths=exclusion_paths,
                cache_duration_seconds=cache_duration_seconds,
            )
    """

    async def __call__(
        self,
        paths: Sequence[Path],
        *,
        exclusion_paths: Sequence[Path] | None = None,
        cache_duration_seconds: int = ...,
    ) -> DiskSample: ...


def _default_lifecycle_monitor_factory(
    pid_file: Path,
    interval: float,
) -> AsyncGenerator[MoverLifecycleEvent]:
    return monitor_mover_lifecycle(pid_file, check_interval=interval)


def _flatten_paths(paths: Sequence[Path]) -> tuple[Path, ...]:
    return tuple(Path(path) for path in paths)


class Orchestrator:
    """Coordinate monitoring, progress tracking, and provider lifecycle."""

    def __init__(
        self,
        *,
        config: MainConfig,
        monitored_paths: Sequence[Path],
        plugin_loader: PluginLoader | None = None,
        registry: ProviderRegistry[NotificationProvider] | None = None,
        dispatcher: NotificationDispatcher | None = None,
        provider_init_kwargs: ProviderInitKwargs | None = None,
        lifecycle_monitor_factory: LifecycleMonitorFactory = _default_lifecycle_monitor_factory,
        baseline_sampler: BaselineSampler = capture_baseline_async,
        usage_sampler: UsageSampler = sample_current_usage_async,
        progress_calculator: ProgressCalculator | None = None,
        threshold_evaluator: ThresholdEvaluator | None = None,
        rate_window_size: int = _DEFAULT_RATE_WINDOW_SIZE,
    ) -> None:
        if not monitored_paths:
            msg = "At least one monitored path must be provided"
            raise ValueError(msg)

        self.config: MainConfig = config
        self.monitored_paths: tuple[Path, ...] = _flatten_paths(monitored_paths)
        self.lifecycle_monitor_factory: LifecycleMonitorFactory = lifecycle_monitor_factory
        self.baseline_sampler: BaselineSampler = baseline_sampler
        self.usage_sampler: UsageSampler = usage_sampler
        self.rate_window_size: int = rate_window_size
        self._dry_run_enabled: bool = bool(config.application.dry_run)

        self._monitor_paths: tuple[Path, ...] = self.monitored_paths
        self._exclusion_paths: tuple[Path, ...] = tuple(config.monitoring.exclusion_paths)
        self._plugin_loader: PluginLoader = plugin_loader or PluginLoader()
        self._registry: ProviderRegistry[NotificationProvider] = registry or ProviderRegistry()
        self._dispatcher: NotificationDispatcher
        if dispatcher is not None:
            self._dispatcher = dispatcher
        else:
            self._dispatcher = NotificationDispatcher(
                self._registry,
                dry_run_enabled=self._dry_run_enabled,
            )
        self._provider_init_kwargs: ProviderInitKwargs | None = provider_init_kwargs
        self._progress_calculator: ProgressCalculator = progress_calculator or self._default_progress_calculator
        self._threshold_evaluator: ThresholdEvaluator = threshold_evaluator or self._default_threshold_evaluator
        self._sampling_interval: float = float(config.monitoring.sampling_interval)
        if self._sampling_interval <= 0:
            msg = "sampling_interval must be greater than zero"
            raise ValueError(msg)

        self._pid_file: Path = config.monitoring.pid_file
        self._pid_check_interval: float = float(config.monitoring.pid_check_interval)
        self._notification_thresholds: tuple[float, ...] = tuple(sorted(config.notifications.thresholds))

        self._logger: logging.Logger = logging.getLogger(__name__)
        if self._dry_run_enabled:
            self._logger.info("Dry-run mode enabled: notifications will be logged without sending")
        self._shutdown_event: asyncio.Event = asyncio.Event()
        self._ready_event: asyncio.Event = asyncio.Event()
        self._task_group: asyncio.TaskGroup | None = None
        self._is_running: bool = False

        self._baseline: DiskSample | None = None
        self._samples: list[DiskSample] = []
        self._latest_progress: ProgressData | None = None
        self._notified_thresholds: set[float] = set()
        self._last_threshold_crossed: float | None = None
        self._active_cycle_id: str | None = None
        self._sampling_task: asyncio.Task[None] | None = None
        self._cycle_active: asyncio.Event = asyncio.Event()
        self._current_pid: int | None = None
        self._lifecycle_state: MoverState = MoverState.WAITING

    @property
    def ready_event(self) -> asyncio.Event:
        """Event triggered once providers are initialized and monitoring starts."""
        return self._ready_event

    @property
    def is_running(self) -> bool:
        """Return True if the orchestrator is actively running."""
        return self._is_running

    @property
    def latest_progress(self) -> ProgressData | None:
        """Return most recent progress calculation."""
        return self._latest_progress

    @property
    def lifecycle_state(self) -> MoverState:
        """Return current orchestrator lifecycle state."""
        return self._lifecycle_state

    @property
    def provider_registry(self) -> ProviderRegistry[NotificationProvider]:
        """Expose provider registry for diagnostics and tests."""
        return self._registry

    def request_shutdown(self) -> None:
        """Signal the orchestrator to stop gracefully."""
        if self._shutdown_event.is_set():
            return
        self._logger.info("Shutdown requested for orchestrator")
        _ = self._shutdown_event.set()
        if self._cycle_active.is_set():
            _ = self._cycle_active.clear()

    async def start(self) -> None:
        """Run orchestrator until shutdown is requested."""
        if self._is_running:
            msg = "Orchestrator is already running"
            raise RuntimeError(msg)

        self._is_running = True
        self._shutdown_event.clear()
        self._ready_event.clear()
        try:
            await self._initialize_providers()
            self._ready_event.set()
            async with asyncio.TaskGroup() as task_group:
                self._task_group = task_group
                _ = task_group.create_task(self._lifecycle_loop(), name="lifecycle-monitor")
                _ = task_group.create_task(self._shutdown_watcher(), name="shutdown-watcher")
        finally:
            await self._finalize_cycle()
            self._task_group = None
            self._is_running = False
            self._ready_event.clear()

    async def _shutdown_watcher(self) -> None:
        _ = await self._shutdown_event.wait()
        await self._finalize_cycle()

    async def _lifecycle_loop(self) -> None:
        monitor = self.lifecycle_monitor_factory(
            self._pid_file,
            self._pid_check_interval,
        )
        try:
            async for event in monitor:
                await self._handle_lifecycle_event(event)
                if self._shutdown_event.is_set():
                    break
        finally:
            with contextlib.suppress(RuntimeError):
                await monitor.aclose()

    async def _handle_lifecycle_event(self, event: MoverLifecycleEvent) -> None:
        _ = self._logger.info(
            "Lifecycle transition detected",
            extra={
                "previous_state": event.previous_state.value,
                "new_state": event.new_state.value,
                "pid": event.pid,
            },
        )

        if event.new_state == MoverState.STARTED:
            await self._on_mover_started(event)
        elif event.new_state == MoverState.COMPLETED:
            await self._on_mover_completed()
        elif event.new_state == MoverState.WAITING:
            # Reset to waiting state after monitor reset events
            if self._lifecycle_state != MoverState.WAITING:
                self._lifecycle_state = MoverState.WAITING
        # MONITORING transitions are handled by orchestration logic

    async def _on_mover_started(self, event: MoverLifecycleEvent) -> None:
        if self._baseline is not None:
            self._logger.debug("Baseline already captured, ignoring duplicate STARTED event")
            return

        self._current_pid = event.pid
        baseline = await self.baseline_sampler(
            self._monitor_paths,
            exclusion_paths=self._exclusion_paths or None,
        )
        self._baseline = baseline
        self._samples = [baseline]
        self._notified_thresholds.clear()
        self._last_threshold_crossed = None
        self._lifecycle_state = MoverState.MONITORING
        self._active_cycle_id = uuid4().hex

        # Dispatch "started" notification
        await self._dispatch_started_notification()

        _ = self._cycle_active.set()
        if self._task_group is None:
            msg = "Task group is not initialized"
            raise RuntimeError(msg)
        self._sampling_task = self._task_group.create_task(
            self._sampling_loop(self._active_cycle_id),
            name="sampling-loop",
        )

    async def _on_mover_completed(self) -> None:
        if self._baseline is None:
            self._logger.info("Received COMPLETED event with no active baseline; ignoring")
            self._lifecycle_state = MoverState.WAITING
            return

        self._lifecycle_state = MoverState.COMPLETED
        await self._stop_sampling_loop()

        # Dispatch "completed" notification before finalizing cycle
        await self._dispatch_completed_notification()

        await self._finalize_cycle()
        self._lifecycle_state = MoverState.WAITING

    async def _sampling_loop(self, cycle_id: str) -> None:
        try:
            while (
                not self._shutdown_event.is_set() and self._cycle_active.is_set() and self._active_cycle_id == cycle_id
            ):
                await asyncio.sleep(self._sampling_interval)
                if (
                    self._shutdown_event.is_set()
                    or not self._cycle_active.is_set()
                    or self._active_cycle_id != cycle_id
                ):
                    break
                await self._record_sample()
        finally:
            _ = self._cycle_active.clear()

    async def _record_sample(self) -> None:
        if self._baseline is None:
            return

        sample = await self.usage_sampler(
            self._monitor_paths,
            exclusion_paths=self._exclusion_paths or None,
        )
        self._samples.append(sample)
        progress = self._progress_calculator(
            self._baseline.bytes_used,
            sample.bytes_used,
            tuple(self._samples),
            self.rate_window_size,
        )
        self._latest_progress = progress

        threshold = self._threshold_evaluator(
            progress.percent,
            self._notification_thresholds,
            tuple(self._notified_thresholds),
        )
        if threshold is not None:
            _ = self._notified_thresholds.add(threshold)
            self._last_threshold_crossed = threshold
            # Dispatch progress notification when threshold is crossed
            await self._dispatch_progress_notification(threshold, progress)

    async def _stop_sampling_loop(self) -> None:
        if self._sampling_task is None:
            return
        _ = self._cycle_active.clear()
        _ = self._sampling_task.cancel()
        try:
            await self._sampling_task
        except asyncio.CancelledError:
            pass
        finally:
            self._sampling_task = None

    async def _finalize_cycle(self) -> None:
        await self._stop_sampling_loop()
        self._baseline = None
        self._samples.clear()
        self._latest_progress = None
        self._active_cycle_id = None
        self._current_pid = None
        self._notified_thresholds.clear()
        self._last_threshold_crossed = None
        _ = self._cycle_active.clear()

    async def _initialize_providers(self) -> None:
        provider_flags = {provider_id: True for provider_id in self.config.providers.enabled}
        loaded = self._plugin_loader.load_enabled_plugins(
            provider_flags=provider_flags,
            factory_kwargs=self._provider_init_kwargs,
        )

        if not loaded:
            msg = "No notification providers could be loaded"
            raise RuntimeError(msg)

        registered = 0
        for plugin in loaded:
            if not await self._register_loaded_plugin(plugin):
                continue
            registered += 1

        if registered == 0:
            msg = "All enabled providers failed validation or health checks"
            raise RuntimeError(msg)

    async def _register_loaded_plugin(self, plugin: LoadedPlugin) -> bool:
        provider = plugin.provider
        try:
            if not provider.validate_config():
                self._logger.error(
                    "Provider configuration invalid, skipping registration",
                    extra={"provider_identifier": plugin.identifier},
                )
                return False
        except Exception as exc:
            self._logger.exception(
                "Provider raised error during configuration validation",
                extra={"provider_identifier": plugin.identifier, "error": str(exc)},
            )
            return False

        try:
            health = await provider.health_check()
        except Exception as exc:  # pragma: no cover - defensive logging
            self._logger.exception(
                "Provider health check failed",
                extra={"provider_identifier": plugin.identifier, "error": str(exc)},
            )
            return False

        self._registry.register(
            plugin.identifier,
            provider,
            initial_health=health,
        )
        self._logger.info(
            "Registered provider",
            extra={"provider_identifier": plugin.identifier},
        )
        return True

    def _create_notification_data(
        self,
        event_type: str,
        progress: ProgressData | None = None,
    ) -> NotificationData:
        """Create NotificationData from ProgressData with formatted strings.

        Args:
            event_type: Type of event ("started", "progress", "completed")
            progress: Progress data to format. If None, uses baseline and latest progress.

        Returns:
            NotificationData with human-readable formatted strings.
        """
        if self._active_cycle_id is None:
            msg = "Cannot create notification without active cycle"
            raise RuntimeError(msg)

        # Use provided progress or latest available
        prog = progress or self._latest_progress

        # For "started" event, we may not have progress data yet
        if prog is None:
            if self._baseline is None:
                msg = "Cannot create notification without baseline"
                raise RuntimeError(msg)
            # Create minimal progress data showing 0% progress
            percent = 0.0
            total_bytes = self._baseline.bytes_used
            moved_bytes = 0
            remaining_bytes = total_bytes
            rate_bytes_per_second = 0.0
            etc_timestamp = None
        else:
            percent = prog.percent
            total_bytes = prog.total_bytes
            moved_bytes = prog.moved_bytes
            remaining_bytes = prog.remaining_bytes
            rate_bytes_per_second = prog.rate_bytes_per_second
            etc_timestamp = prog.etc

        return NotificationData(
            event_type=event_type,
            percent=percent,
            remaining_data=format_size(remaining_bytes),
            moved_data=format_size(moved_bytes),
            total_data=format_size(total_bytes),
            rate=format_rate(rate_bytes_per_second),
            etc_timestamp=etc_timestamp,
            correlation_id=self._active_cycle_id,
        )

    async def _dispatch_started_notification(self) -> None:
        """Dispatch notification when mover process starts."""
        try:
            notification_data = self._create_notification_data(event_type="started")
            results = await self._dispatcher.dispatch_notification(notification_data)

            # Log results for monitoring
            success_count = sum(1 for r in results if r.success)
            self._logger.info(
                "Dispatched mover started notification",
                extra={
                    "correlation_id": self._active_cycle_id,
                    "providers_notified": len(results),
                    "successful_deliveries": success_count,
                },
            )
        except Exception as exc:
            self._logger.exception(
                "Failed to dispatch started notification",
                extra={"correlation_id": self._active_cycle_id, "error": str(exc)},
            )

    async def _dispatch_progress_notification(
        self,
        threshold: float,
        progress: ProgressData,
    ) -> None:
        """Dispatch notification when progress threshold is crossed.

        Args:
            threshold: The threshold percentage that was crossed
            progress: Current progress data
        """
        try:
            notification_data = self._create_notification_data(
                event_type="progress",
                progress=progress,
            )
            results = await self._dispatcher.dispatch_notification(notification_data)

            success_count = sum(1 for r in results if r.success)
            self._logger.info(
                "Dispatched progress threshold notification",
                extra={
                    "correlation_id": self._active_cycle_id,
                    "threshold_percent": threshold,
                    "current_percent": progress.percent,
                    "providers_notified": len(results),
                    "successful_deliveries": success_count,
                },
            )
        except Exception as exc:
            self._logger.exception(
                "Failed to dispatch progress notification",
                extra={
                    "correlation_id": self._active_cycle_id,
                    "threshold": threshold,
                    "error": str(exc),
                },
            )

    async def _dispatch_completed_notification(self) -> None:
        """Dispatch notification when mover process completes."""
        try:
            # Use latest progress for final stats
            notification_data = self._create_notification_data(
                event_type="completed",
                progress=self._latest_progress,
            )
            results = await self._dispatcher.dispatch_notification(notification_data)

            success_count = sum(1 for r in results if r.success)
            self._logger.info(
                "Dispatched mover completed notification",
                extra={
                    "correlation_id": self._active_cycle_id,
                    "providers_notified": len(results),
                    "successful_deliveries": success_count,
                },
            )
        except Exception as exc:
            self._logger.exception(
                "Failed to dispatch completed notification",
                extra={"correlation_id": self._active_cycle_id, "error": str(exc)},
            )

    @staticmethod
    def _default_progress_calculator(
        baseline: int,
        current: int,
        samples: Sequence[DiskSample],
        window_size: int,
    ) -> ProgressData:
        return calculate_progress_data(
            baseline=baseline,
            current=current,
            samples=samples,
            window_size=window_size,
        )

    @staticmethod
    def _default_threshold_evaluator(
        current_percent: float,
        thresholds: Sequence[float],
        notified: Sequence[float],
    ) -> float | None:
        return evaluate_threshold_crossed(
            current_percent=current_percent,
            thresholds=thresholds,
            notified_thresholds=notified,
        )
