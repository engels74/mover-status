"""Integration tests for the orchestrator (requirement 12.4).

Tests verify full monitoring cycle coordination, notification dispatch at thresholds,
graceful shutdown, and provider lifecycle management. Uses mock components for isolation.
"""

from __future__ import annotations

import asyncio
import time
from collections import deque
from collections.abc import AsyncGenerator, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import override

import pytest

from mover_status.core.config import (
    ApplicationConfig,
    MainConfig,
    MonitoringConfig,
    NotificationsConfig,
    ProvidersConfig,
)
from mover_status.core.monitoring import MoverLifecycleEvent, MoverState
from mover_status.core.orchestrator import Orchestrator
from mover_status.plugins import LoadedPlugin, PluginLoader
from mover_status.plugins.discovery import PluginMetadata
from mover_status.types import (
    DiskSample,
    HealthStatus,
    NotificationData,
    NotificationProvider,
    NotificationResult,
    ProgressData,
)

pytestmark = pytest.mark.asyncio

# Type aliases for test fixtures
type NotificationRecord = tuple[str, NotificationData]  # (event_type, data)
type ThresholdRecord = tuple[float, float]  # (threshold, current_percent)


class InstrumentedProvider(NotificationProvider):
    """Provider double that records all notification calls for verification."""

    def __init__(
        self,
        identifier: str,
        *,
        delay: float = 0.0,
        fail_validation: bool = False,
        fail_health_check: bool = False,
    ) -> None:
        self.identifier: str = identifier
        self.delay: float = delay
        self.fail_validation: bool = fail_validation
        self.fail_health_check: bool = fail_health_check
        self.notifications: list[NotificationRecord] = []
        self.validation_calls: int = 0
        self.health_check_calls: int = 0

    @override
    async def send_notification(self, data: NotificationData) -> NotificationResult:
        """Record notification and simulate delivery."""
        self.notifications.append((data.event_type, data))
        if self.delay > 0:
            await asyncio.sleep(self.delay)
        return NotificationResult(
            success=True,
            provider_name=self.identifier,
            error_message=None,
            delivery_time_ms=self.delay * 1000.0,
        )

    @override
    def validate_config(self) -> bool:
        """Record validation call and return configured result."""
        self.validation_calls += 1
        return not self.fail_validation

    @override
    async def health_check(self) -> HealthStatus:
        """Record health check call and return configured result."""
        self.health_check_calls += 1
        if self.fail_health_check:
            raise RuntimeError("Health check failed")
        return HealthStatus(
            is_healthy=True,
            last_check=datetime.now(tz=UTC),
            consecutive_failures=0,
            error_message=None,
        )


class StubLoader(PluginLoader):
    """PluginLoader stub that returns predefined plugins."""

    def __init__(self, loaded: tuple[LoadedPlugin, ...]) -> None:
        super().__init__()
        self.loaded: tuple[LoadedPlugin, ...] = loaded
        self.load_calls: int = 0

    @override
    def load_enabled_plugins(
        self,
        *,
        provider_flags: Mapping[str, bool],
        factory_kwargs: Mapping[str, Mapping[str, object]] | None = None,
        force_rescan: bool = False,
    ) -> tuple[LoadedPlugin, ...]:
        _ = provider_flags, factory_kwargs, force_rescan
        self.load_calls += 1
        return self.loaded


class LifecycleStream:
    """Async generator factory yielding lifecycle events from a queue."""

    def __init__(self) -> None:
        self._events: asyncio.Queue[MoverLifecycleEvent | None] = asyncio.Queue()

    def push(self, event: MoverLifecycleEvent | None) -> None:
        """Push event to stream (None signals end)."""
        self._events.put_nowait(event)

    def factory(
        self,
        _pid_file: Path,
        _interval: float,
    ) -> AsyncGenerator[MoverLifecycleEvent]:
        """Create lifecycle monitor generator."""

        async def _generator() -> AsyncGenerator[MoverLifecycleEvent]:
            while True:
                item = await self._events.get()
                if item is None:
                    break
                yield item

        return _generator()


def _make_lifecycle_event(
    previous_state: MoverState,
    new_state: MoverState,
    *,
    pid: int | None,
    message: str = "",
) -> MoverLifecycleEvent:
    """Create lifecycle event for testing."""
    return MoverLifecycleEvent(
        previous_state=previous_state,
        new_state=new_state,
        pid=pid,
        timestamp=datetime.now(tz=UTC),
        message=message or f"{previous_state.value} -> {new_state.value}",
    )


def _make_config(
    *,
    pid_file: Path,
    sampling_interval: int = 1,
    thresholds: list[float] | None = None,
) -> MainConfig:
    """Create test configuration."""
    return MainConfig(
        monitoring=MonitoringConfig(
            pid_file=pid_file,
            pid_check_interval=1,
            sampling_interval=sampling_interval,
            process_timeout=5,
            exclusion_paths=[],
        ),
        notifications=NotificationsConfig(thresholds=thresholds or [25.0, 50.0, 75.0, 100.0]),
        providers=ProvidersConfig(enabled=["discord"]),
        application=ApplicationConfig(),
    )


@pytest.fixture
def test_dir(tmp_path: Path) -> Path:
    """Create test directory structure."""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    return cache_dir


@pytest.fixture
def config(tmp_path: Path) -> MainConfig:
    """Create test configuration."""
    return _make_config(pid_file=tmp_path / "mover.pid")


@pytest.fixture
def providers() -> list[InstrumentedProvider]:
    """Create test providers."""
    return [
        InstrumentedProvider("alpha"),
        InstrumentedProvider("beta"),
    ]


@pytest.fixture
def loader(providers: list[InstrumentedProvider]) -> StubLoader:
    """Create plugin loader with test providers."""
    loaded_plugins = [
        LoadedPlugin(
            identifier=provider.identifier,
            provider=provider,
            metadata=PluginMetadata(
                identifier=provider.identifier,
                name=provider.identifier.title(),
                package=f"mover_status.plugins.{provider.identifier}",
                version="0.0.1",
            ),
        )
        for provider in providers
    ]
    return StubLoader(tuple(loaded_plugins))


async def test_full_monitoring_cycle(
    test_dir: Path,
    config: MainConfig,
    providers: list[InstrumentedProvider],
    loader: StubLoader,
) -> None:
    """Verify complete monitoring cycle: WAITING → STARTED → MONITORING → COMPLETED.

    Tests:
    - Baseline captured on STARTED event
    - Sampling loop runs during MONITORING state
    - Progress notifications dispatched at thresholds
    - Cleanup occurs on COMPLETED event
    - State returns to WAITING after completion
    """
    # Set up lifecycle event stream
    stream = LifecycleStream()

    # Mock baseline and usage samplers
    baseline_bytes = 1_000_000
    sample_values = deque([750_000, 500_000, 250_000, 0])

    async def capture_baseline(
        paths: Sequence[Path],
        *,
        exclusion_paths: Sequence[Path] | None = None,
    ) -> DiskSample:
        _ = paths, exclusion_paths
        return DiskSample(
            timestamp=datetime.now(tz=UTC),
            bytes_used=baseline_bytes,
            path=str(test_dir),
        )

    async def sample_usage(
        paths: Sequence[Path],
        *,
        exclusion_paths: Sequence[Path] | None = None,
        cache_duration_seconds: int = 30,
    ) -> DiskSample:
        _ = paths, exclusion_paths, cache_duration_seconds
        value = sample_values.popleft() if sample_values else 0
        return DiskSample(
            timestamp=datetime.now(tz=UTC),
            bytes_used=value,
            path=str(test_dir),
        )

    # Track progress calculations
    progress_records: list[ProgressData] = []

    def progress_calculator(
        baseline: int,
        current: int,
        samples: Sequence[DiskSample],
        window_size: int,
    ) -> ProgressData:
        _ = samples, window_size
        moved = max(0, baseline - current)
        percent = 0.0 if baseline == 0 else (moved / baseline) * 100.0
        progress = ProgressData(
            percent=percent,
            remaining_bytes=current,
            moved_bytes=moved,
            total_bytes=baseline,
            rate_bytes_per_second=1000.0,
            etc=None,
        )
        progress_records.append(progress)
        return progress

    # Create orchestrator
    orchestrator = Orchestrator(
        config=config,
        monitored_paths=[test_dir],
        plugin_loader=loader,
        lifecycle_monitor_factory=stream.factory,
        baseline_sampler=capture_baseline,
        usage_sampler=sample_usage,
        progress_calculator=progress_calculator,
    )
    # Speed up sampling for test
    orchestrator._sampling_interval = 0.01  # pyright: ignore[reportPrivateUsage]

    # Start orchestrator
    run_task = asyncio.create_task(orchestrator.start())
    _ = await asyncio.wait_for(orchestrator.ready_event.wait(), timeout=1.0)

    # Verify initial state
    assert orchestrator.lifecycle_state == MoverState.WAITING
    assert orchestrator.latest_progress is None

    # Send STARTED event
    stream.push(
        _make_lifecycle_event(
            MoverState.WAITING,
            MoverState.STARTED,
            pid=1234,
            message="Mover started",
        )
    )

    # Wait for sampling to begin
    await asyncio.sleep(0.05)

    # Verify MONITORING state and baseline capture
    assert orchestrator.lifecycle_state == MoverState.MONITORING
    assert orchestrator.latest_progress is not None

    # Verify progress calculations occurred
    assert len(progress_records) > 0

    # Send COMPLETED event
    stream.push(
        _make_lifecycle_event(
            MoverState.MONITORING,
            MoverState.COMPLETED,
            pid=1234,
            message="Mover completed",
        )
    )

    # Wait for completion processing
    await asyncio.sleep(0.02)

    # Signal stream end
    stream.push(None)

    # Request shutdown
    orchestrator.request_shutdown()
    await asyncio.wait_for(run_task, timeout=1.0)

    # Verify final state
    assert orchestrator.lifecycle_state == MoverState.WAITING
    assert orchestrator.latest_progress is None  # Cleaned up

    # Verify all providers were initialized
    assert loader.load_calls == 1
    for provider in providers:
        assert provider.validation_calls == 1
        assert provider.health_check_calls == 1

    # Verify notifications were dispatched
    all_notifications = [notif for provider in providers for notif in provider.notifications]
    event_types = [event_type for event_type, _ in all_notifications]

    # Should have at least "started" and "completed"
    assert "started" in event_types
    assert "completed" in event_types


async def test_threshold_notification_triggering(
    test_dir: Path,
    config: MainConfig,
    providers: list[InstrumentedProvider],
    loader: StubLoader,
) -> None:
    """Verify progress notifications dispatched only at threshold crossings.

    Tests:
    - Notifications sent when crossing 25%, 50%, 75%, 100%
    - No duplicate notifications for same threshold
    - Threshold tracking prevents re-notification
    """
    stream = LifecycleStream()

    # Sample values that cross thresholds: 25%, 50%, 75%, 100%
    baseline_bytes = 1_000_000
    sample_sequence = [
        750_000,  # 25% progress
        500_000,  # 50% progress
        250_000,  # 75% progress
        0,  # 100% progress
    ]
    sample_values = deque(sample_sequence)

    async def capture_baseline(
        paths: Sequence[Path],
        *,
        exclusion_paths: Sequence[Path] | None = None,
    ) -> DiskSample:
        _ = paths, exclusion_paths
        return DiskSample(
            timestamp=datetime.now(tz=UTC),
            bytes_used=baseline_bytes,
            path=str(test_dir),
        )

    async def sample_usage(
        paths: Sequence[Path],
        *,
        exclusion_paths: Sequence[Path] | None = None,
        cache_duration_seconds: int = 30,
    ) -> DiskSample:
        _ = paths, exclusion_paths, cache_duration_seconds
        value = sample_values.popleft() if sample_values else 0
        return DiskSample(
            timestamp=datetime.now(tz=UTC),
            bytes_used=value,
            path=str(test_dir),
        )

    def progress_calculator(
        baseline: int,
        current: int,
        samples: Sequence[DiskSample],
        window_size: int,
    ) -> ProgressData:
        _ = samples, window_size
        moved = max(0, baseline - current)
        percent = 0.0 if baseline == 0 else (moved / baseline) * 100.0
        return ProgressData(
            percent=percent,
            remaining_bytes=current,
            moved_bytes=moved,
            total_bytes=baseline,
            rate_bytes_per_second=1000.0,
            etc=None,
        )

    # Track threshold crossings
    threshold_records: list[ThresholdRecord] = []

    def threshold_evaluator(
        current_percent: float,
        thresholds: Sequence[float],
        notified: Sequence[float],
    ) -> float | None:
        """Evaluate if a threshold is crossed."""
        for threshold in sorted(thresholds):
            if current_percent >= threshold and threshold not in notified:
                threshold_records.append((threshold, current_percent))
                return threshold
        return None

    orchestrator = Orchestrator(
        config=config,
        monitored_paths=[test_dir],
        plugin_loader=loader,
        lifecycle_monitor_factory=stream.factory,
        baseline_sampler=capture_baseline,
        usage_sampler=sample_usage,
        progress_calculator=progress_calculator,
        threshold_evaluator=threshold_evaluator,
    )
    orchestrator._sampling_interval = 0.01  # pyright: ignore[reportPrivateUsage]

    run_task = asyncio.create_task(orchestrator.start())
    _ = await asyncio.wait_for(orchestrator.ready_event.wait(), timeout=1.0)

    # Send STARTED event
    stream.push(
        _make_lifecycle_event(
            MoverState.WAITING,
            MoverState.STARTED,
            pid=1234,
        )
    )

    # Wait for all samples to be processed
    await asyncio.sleep(0.1)

    # Send COMPLETED event
    stream.push(
        _make_lifecycle_event(
            MoverState.MONITORING,
            MoverState.COMPLETED,
            pid=1234,
        )
    )
    await asyncio.sleep(0.02)
    stream.push(None)

    orchestrator.request_shutdown()
    await asyncio.wait_for(run_task, timeout=1.0)

    # Verify threshold crossings occurred
    assert len(threshold_records) == 4  # 25%, 50%, 75%, 100%
    thresholds_crossed = [threshold for threshold, _ in threshold_records]
    assert 25.0 in thresholds_crossed
    assert 50.0 in thresholds_crossed
    assert 75.0 in thresholds_crossed
    assert 100.0 in thresholds_crossed

    # Verify each provider received progress notifications
    for provider in providers:
        progress_notifications = [data for event_type, data in provider.notifications if event_type == "progress"]
        # Should have 4 progress notifications (one per threshold)
        assert len(progress_notifications) == 4


async def test_graceful_shutdown(
    test_dir: Path,
    config: MainConfig,
    loader: StubLoader,
) -> None:
    """Verify graceful shutdown stops lifecycle and sampling cleanly.

    Tests:
    - request_shutdown() stops lifecycle loop
    - Sampling task is cancelled
    - No orphaned tasks remain
    - State is cleaned up properly
    """
    stream = LifecycleStream()

    baseline_bytes = 1_000_000

    async def capture_baseline(
        paths: Sequence[Path],
        *,
        exclusion_paths: Sequence[Path] | None = None,
    ) -> DiskSample:
        _ = paths, exclusion_paths
        return DiskSample(
            timestamp=datetime.now(tz=UTC),
            bytes_used=baseline_bytes,
            path=str(test_dir),
        )

    async def sample_usage(
        paths: Sequence[Path],
        *,
        exclusion_paths: Sequence[Path] | None = None,
        cache_duration_seconds: int = 30,
    ) -> DiskSample:
        _ = paths, exclusion_paths, cache_duration_seconds
        # Simulate slow sampling to test cancellation
        await asyncio.sleep(0.05)
        return DiskSample(
            timestamp=datetime.now(tz=UTC),
            bytes_used=baseline_bytes - 100_000,
            path=str(test_dir),
        )

    orchestrator = Orchestrator(
        config=config,
        monitored_paths=[test_dir],
        plugin_loader=loader,
        lifecycle_monitor_factory=stream.factory,
        baseline_sampler=capture_baseline,
        usage_sampler=sample_usage,
    )
    orchestrator._sampling_interval = 0.02  # pyright: ignore[reportPrivateUsage]

    run_task = asyncio.create_task(orchestrator.start())
    _ = await asyncio.wait_for(orchestrator.ready_event.wait(), timeout=1.0)

    # Send STARTED event to begin monitoring
    stream.push(
        _make_lifecycle_event(
            MoverState.WAITING,
            MoverState.STARTED,
            pid=1234,
        )
    )

    # Wait for monitoring to start
    await asyncio.sleep(0.03)
    assert orchestrator.lifecycle_state == MoverState.MONITORING

    # Request shutdown while actively monitoring
    start_time = time.perf_counter()
    orchestrator.request_shutdown()
    stream.push(None)  # End lifecycle stream

    # Shutdown should complete quickly
    await asyncio.wait_for(run_task, timeout=1.0)
    shutdown_duration = time.perf_counter() - start_time

    # Verify shutdown was fast (not waiting for full sampling cycles)
    assert shutdown_duration < 0.5

    # Verify orchestrator stopped cleanly
    assert orchestrator.is_running is False
    assert orchestrator.latest_progress is None

    # Verify no tasks are still running
    running_tasks = [task for task in asyncio.all_tasks() if not task.done()]
    # Only the test task itself should remain
    assert len(running_tasks) <= 1


async def test_provider_initialization_failures(
    test_dir: Path,
    config: MainConfig,
) -> None:
    """Verify RuntimeError when all providers fail validation or health checks.

    Tests:
    - Provider validation failures prevent registration
    - Provider health check failures prevent registration
    - RuntimeError raised when no providers can be loaded
    """
    # Test case 1: All providers fail validation
    failing_providers = [
        InstrumentedProvider("alpha", fail_validation=True),
        InstrumentedProvider("beta", fail_validation=True),
    ]
    failing_loader = StubLoader(
        tuple(
            LoadedPlugin(
                identifier=provider.identifier,
                provider=provider,
                metadata=PluginMetadata(
                    identifier=provider.identifier,
                    name=provider.identifier.title(),
                    package=f"mover_status.plugins.{provider.identifier}",
                    version="0.0.1",
                ),
            )
            for provider in failing_providers
        )
    )

    stream = LifecycleStream()
    orchestrator = Orchestrator(
        config=config,
        monitored_paths=[test_dir],
        plugin_loader=failing_loader,
        lifecycle_monitor_factory=stream.factory,
    )

    # Should raise RuntimeError during startup
    # Use asyncio.wait_for to prevent test hanging
    with pytest.raises(RuntimeError, match="All enabled providers failed validation or health checks"):
        try:
            await asyncio.wait_for(orchestrator.start(), timeout=2.0)
        except TimeoutError:
            pytest.fail("Orchestrator start() timed out instead of raising RuntimeError")

    # Test case 2: All providers fail health checks
    unhealthy_providers = [
        InstrumentedProvider("gamma", fail_health_check=True),
        InstrumentedProvider("delta", fail_health_check=True),
    ]
    unhealthy_loader = StubLoader(
        tuple(
            LoadedPlugin(
                identifier=provider.identifier,
                provider=provider,
                metadata=PluginMetadata(
                    identifier=provider.identifier,
                    name=provider.identifier.title(),
                    package=f"mover_status.plugins.{provider.identifier}",
                    version="0.0.1",
                ),
            )
            for provider in unhealthy_providers
        )
    )

    stream2 = LifecycleStream()
    orchestrator2 = Orchestrator(
        config=config,
        monitored_paths=[test_dir],
        plugin_loader=unhealthy_loader,
        lifecycle_monitor_factory=stream2.factory,
    )

    with pytest.raises(RuntimeError, match="All enabled providers failed validation or health checks"):
        try:
            await asyncio.wait_for(orchestrator2.start(), timeout=2.0)
        except TimeoutError:
            pytest.fail("Orchestrator start() timed out instead of raising RuntimeError")


async def test_no_providers_loaded(
    test_dir: Path,
    config: MainConfig,
) -> None:
    """Verify RuntimeError when plugin loader returns no providers."""
    empty_loader = StubLoader(())
    stream = LifecycleStream()

    orchestrator = Orchestrator(
        config=config,
        monitored_paths=[test_dir],
        plugin_loader=empty_loader,
        lifecycle_monitor_factory=stream.factory,
    )

    with pytest.raises(RuntimeError, match="No notification providers could be loaded"):
        try:
            await asyncio.wait_for(orchestrator.start(), timeout=2.0)
        except TimeoutError:
            pytest.fail("Orchestrator start() timed out instead of raising RuntimeError")


async def test_multiple_complete_cycles(
    test_dir: Path,
    config: MainConfig,
    providers: list[InstrumentedProvider],
    loader: StubLoader,
) -> None:
    """Verify state isolation across multiple monitoring cycles.

    Tests:
    - Second cycle starts with fresh baseline
    - Threshold notifications reset between cycles
    - Each cycle has unique correlation ID
    - No state leakage between cycles
    """
    stream = LifecycleStream()

    baseline_bytes = 1_000_000
    cycle_samples: dict[int, deque[int]] = {
        1: deque([750_000, 500_000]),
        2: deque([800_000, 600_000]),
    }
    current_cycle = 0

    async def capture_baseline(
        paths: Sequence[Path],
        *,
        exclusion_paths: Sequence[Path] | None = None,
    ) -> DiskSample:
        _ = paths, exclusion_paths
        return DiskSample(
            timestamp=datetime.now(tz=UTC),
            bytes_used=baseline_bytes,
            path=str(test_dir),
        )

    async def sample_usage(
        paths: Sequence[Path],
        *,
        exclusion_paths: Sequence[Path] | None = None,
        cache_duration_seconds: int = 30,
    ) -> DiskSample:
        _ = paths, exclusion_paths, cache_duration_seconds
        samples = cycle_samples.get(current_cycle, deque([baseline_bytes]))
        value = samples.popleft() if samples else baseline_bytes
        return DiskSample(
            timestamp=datetime.now(tz=UTC),
            bytes_used=value,
            path=str(test_dir),
        )

    orchestrator = Orchestrator(
        config=config,
        monitored_paths=[test_dir],
        plugin_loader=loader,
        lifecycle_monitor_factory=stream.factory,
        baseline_sampler=capture_baseline,
        usage_sampler=sample_usage,
    )
    orchestrator._sampling_interval = 0.01  # pyright: ignore[reportPrivateUsage]

    run_task = asyncio.create_task(orchestrator.start())
    _ = await asyncio.wait_for(orchestrator.ready_event.wait(), timeout=1.0)

    # First cycle
    current_cycle = 1
    stream.push(
        _make_lifecycle_event(
            MoverState.WAITING,
            MoverState.STARTED,
            pid=1234,
            message="Cycle 1 started",
        )
    )
    await asyncio.sleep(0.05)

    first_cycle_id = orchestrator._active_cycle_id  # pyright: ignore[reportPrivateUsage]
    assert first_cycle_id is not None

    stream.push(
        _make_lifecycle_event(
            MoverState.MONITORING,
            MoverState.COMPLETED,
            pid=1234,
            message="Cycle 1 completed",
        )
    )
    await asyncio.sleep(0.02)

    # Verify cleanup after first cycle
    assert orchestrator.lifecycle_state == MoverState.WAITING
    assert orchestrator.latest_progress is None

    # Second cycle
    current_cycle = 2
    stream.push(
        _make_lifecycle_event(
            MoverState.WAITING,
            MoverState.STARTED,
            pid=5678,
            message="Cycle 2 started",
        )
    )
    await asyncio.sleep(0.05)

    second_cycle_id = orchestrator._active_cycle_id  # pyright: ignore[reportPrivateUsage]
    assert second_cycle_id is not None
    assert second_cycle_id != first_cycle_id  # Unique correlation IDs

    stream.push(
        _make_lifecycle_event(
            MoverState.MONITORING,
            MoverState.COMPLETED,
            pid=5678,
            message="Cycle 2 completed",
        )
    )
    await asyncio.sleep(0.02)
    stream.push(None)

    orchestrator.request_shutdown()
    await asyncio.wait_for(run_task, timeout=1.0)

    # Verify both cycles completed
    for provider in providers:
        notifications = provider.notifications
        started_count = sum(1 for event_type, _ in notifications if event_type == "started")
        completed_count = sum(1 for event_type, _ in notifications if event_type == "completed")

        # Should have 2 started and 2 completed notifications
        assert started_count == 2
        assert completed_count == 2

        # Verify correlation IDs are different
        correlation_ids = {data.correlation_id for _, data in notifications}
        assert len(correlation_ids) == 2  # Two unique correlation IDs


async def test_duplicate_started_events_ignored(
    test_dir: Path,
    config: MainConfig,
    providers: list[InstrumentedProvider],
    loader: StubLoader,
) -> None:
    """Verify duplicate STARTED events don't re-capture baseline."""
    stream = LifecycleStream()

    baseline_calls = 0

    async def capture_baseline(
        paths: Sequence[Path],
        *,
        exclusion_paths: Sequence[Path] | None = None,
    ) -> DiskSample:
        _ = paths, exclusion_paths
        nonlocal baseline_calls
        baseline_calls += 1
        return DiskSample(
            timestamp=datetime.now(tz=UTC),
            bytes_used=1_000_000,
            path=str(test_dir),
        )

    orchestrator = Orchestrator(
        config=config,
        monitored_paths=[test_dir],
        plugin_loader=loader,
        lifecycle_monitor_factory=stream.factory,
        baseline_sampler=capture_baseline,
    )

    run_task = asyncio.create_task(orchestrator.start())
    _ = await asyncio.wait_for(orchestrator.ready_event.wait(), timeout=1.0)

    # Send first STARTED event
    stream.push(
        _make_lifecycle_event(
            MoverState.WAITING,
            MoverState.STARTED,
            pid=1234,
        )
    )
    await asyncio.sleep(0.02)

    # Send duplicate STARTED event
    stream.push(
        _make_lifecycle_event(
            MoverState.MONITORING,
            MoverState.STARTED,
            pid=1234,
        )
    )
    await asyncio.sleep(0.02)

    stream.push(
        _make_lifecycle_event(
            MoverState.MONITORING,
            MoverState.COMPLETED,
            pid=1234,
        )
    )
    await asyncio.sleep(0.02)
    stream.push(None)

    orchestrator.request_shutdown()
    await asyncio.wait_for(run_task, timeout=1.0)

    # Baseline should only be captured once
    assert baseline_calls == 1

    # Each provider should receive only one "started" notification
    for provider in providers:
        started_count = sum(1 for event_type, _ in provider.notifications if event_type == "started")
        assert started_count == 1


async def test_completed_event_without_baseline(
    test_dir: Path,
    config: MainConfig,
    providers: list[InstrumentedProvider],
    loader: StubLoader,
) -> None:
    """Verify COMPLETED event without active baseline is handled gracefully."""
    stream = LifecycleStream()

    orchestrator = Orchestrator(
        config=config,
        monitored_paths=[test_dir],
        plugin_loader=loader,
        lifecycle_monitor_factory=stream.factory,
    )

    run_task = asyncio.create_task(orchestrator.start())
    _ = await asyncio.wait_for(orchestrator.ready_event.wait(), timeout=1.0)

    # Send COMPLETED without STARTED
    stream.push(
        _make_lifecycle_event(
            MoverState.WAITING,
            MoverState.COMPLETED,
            pid=1234,
        )
    )
    await asyncio.sleep(0.02)

    # Should remain in WAITING state
    assert orchestrator.lifecycle_state == MoverState.WAITING

    stream.push(None)
    orchestrator.request_shutdown()
    await asyncio.wait_for(run_task, timeout=1.0)

    # No completed notifications should be sent
    for provider in providers:
        completed_count = sum(1 for event_type, _ in provider.notifications if event_type == "completed")
        assert completed_count == 0
