"""Tests for the Orchestrator core component."""

from __future__ import annotations

import asyncio
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


class DummyProvider(NotificationProvider):
    """Simple NotificationProvider implementation for orchestrator tests."""

    def __init__(self) -> None:
        self.health_checks: int = 0

    @override
    async def send_notification(
        self, data: NotificationData
    ) -> NotificationResult:  # pragma: no cover - dispatcher integration
        _ = data
        return NotificationResult(
            success=True,
            provider_name="dummy",
            error_message=None,
            delivery_time_ms=0.5,
        )

    @override
    def validate_config(self) -> bool:
        return True

    @override
    async def health_check(self) -> HealthStatus:
        self.health_checks += 1
        return HealthStatus(
            is_healthy=True,
            last_check=datetime.now(tz=UTC),
            consecutive_failures=0,
            error_message=None,
        )


class StubLoader(PluginLoader):
    """PluginLoader stub returning predefined plugins."""

    def __init__(self, loaded: tuple[LoadedPlugin, ...]) -> None:
        super().__init__()
        self.loaded: tuple[LoadedPlugin, ...] = loaded
        self.calls: list[dict[str, object]] = []

    @override
    def load_enabled_plugins(
        self,
        *,
        provider_flags: Mapping[str, bool],
        factory_kwargs: Mapping[str, Mapping[str, object]] | None = None,
        force_rescan: bool = False,
    ) -> tuple[LoadedPlugin, ...]:
        self.calls.append(
            {
                "flags": dict(provider_flags),
                "factory_kwargs": dict(factory_kwargs) if factory_kwargs else {},
                "force_rescan": force_rescan,
            }
        )
        return self.loaded


class LifecycleStream:
    """Async generator factory that yields lifecycle events from a queue."""

    def __init__(self) -> None:
        self._events: asyncio.Queue[MoverLifecycleEvent | None] = asyncio.Queue()

    def push(self, event: MoverLifecycleEvent | None) -> None:
        self._events.put_nowait(event)

    def factory(
        self,
        _pid_file: Path,
        _interval: float,
    ) -> AsyncGenerator[MoverLifecycleEvent]:
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
    message: str,
) -> MoverLifecycleEvent:
    return MoverLifecycleEvent(
        previous_state=previous_state,
        new_state=new_state,
        pid=pid,
        timestamp=datetime.now(tz=UTC),
        message=message,
    )


@pytest.mark.asyncio
async def test_orchestrator_handles_lifecycle_and_sampling(tmp_path: Path) -> None:
    """Orchestrator should respond to lifecycle events and record progress samples."""
    # Prepare monitored path and config
    monitored_dir = tmp_path / "cache"
    monitored_dir.mkdir()
    pid_file = tmp_path / "mover.pid"
    config = MainConfig(
        monitoring=MonitoringConfig(
            pid_file=pid_file,
            pid_check_interval=1,
            sampling_interval=1,
            process_timeout=5,
            exclusion_paths=[],
        ),
        notifications=NotificationsConfig(thresholds=[0.0, 50.0, 100.0]),
        providers=ProvidersConfig(enabled=["discord"]),
        application=ApplicationConfig(),
    )

    # Stub provider and loader
    provider = DummyProvider()
    metadata = PluginMetadata(
        identifier="dummy",
        name="Dummy",
        package="mover_status.plugins.dummy",
        version="0.0.1",
    )
    loaded_plugin = LoadedPlugin(
        identifier="dummy",
        provider=provider,
        metadata=metadata,
    )
    loader = StubLoader((loaded_plugin,))

    # Lifecycle event stream
    stream = LifecycleStream()

    # Baseline and sampling stubs
    baseline_bytes = 1_000
    sample_values = deque([400])

    async def capture_baseline(
        paths: Sequence[Path],
        *,
        exclusion_paths: Sequence[Path] | None = None,
    ) -> DiskSample:
        _ = (paths, exclusion_paths)
        return DiskSample(timestamp=datetime.now(tz=UTC), bytes_used=baseline_bytes, path="cache")

    async def sample_usage(
        paths: Sequence[Path],
        *,
        exclusion_paths: Sequence[Path] | None = None,
        cache_duration_seconds: int = 30,
    ) -> DiskSample:
        _ = (paths, exclusion_paths, cache_duration_seconds)
        value = sample_values.popleft() if sample_values else 700
        return DiskSample(timestamp=datetime.now(tz=UTC), bytes_used=value, path="cache")

    progress_records: list[ProgressData] = []

    def progress_calculator(
        baseline: int,
        current: int,
        samples: Sequence[DiskSample],
        window_size: int,
    ) -> ProgressData:
        _ = samples, window_size
        moved = max(0, baseline - current)
        percent = 0.0 if baseline == 0 else (moved / baseline) * 100
        progress = ProgressData(
            percent=percent,
            remaining_bytes=current,
            moved_bytes=moved,
            total_bytes=baseline,
            rate_bytes_per_second=10.0,
            etc=None,
        )
        progress_records.append(progress)
        return progress

    threshold_hits: list[float] = []

    def threshold_evaluator(
        current_percent: float,
        thresholds: Sequence[float],
        notified: Sequence[float],
    ) -> float | None:
        _ = thresholds
        if current_percent >= 50.0 and 50.0 not in notified:
            threshold_hits.append(current_percent)
            return 50.0
        return None

    orchestrator = Orchestrator(
        config=config,
        monitored_paths=[monitored_dir],
        plugin_loader=loader,
        lifecycle_monitor_factory=stream.factory,
        baseline_sampler=capture_baseline,
        usage_sampler=sample_usage,
        progress_calculator=progress_calculator,
        threshold_evaluator=threshold_evaluator,
    )
    # Speed up sampling loop for the test
    orchestrator._sampling_interval = 0.01  # pyright: ignore[reportPrivateUsage]

    run_task = asyncio.create_task(orchestrator.start())
    _ = await orchestrator.ready_event.wait()

    _ = stream.push(
        _make_lifecycle_event(
            MoverState.WAITING,
            MoverState.STARTED,
            pid=1234,
            message="mover started",
        )
    )
    await asyncio.sleep(0.02)
    _ = stream.push(
        _make_lifecycle_event(
            MoverState.MONITORING,
            MoverState.COMPLETED,
            pid=1234,
            message="mover completed",
        )
    )
    _ = stream.push(None)

    _ = orchestrator.request_shutdown()
    await asyncio.wait_for(run_task, timeout=1)

    assert loader.calls, "Plugin loader should be invoked"
    assert "dummy" in orchestrator.provider_registry.get_identifiers()
    assert provider.health_checks == 1
    assert progress_records, "Progress calculator should be invoked"
    assert progress_records[-1].percent >= 20.0
    assert threshold_hits, "Threshold evaluator should detect threshold crossing"
