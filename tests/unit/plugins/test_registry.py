"""Tests for the ProviderRegistry health tracking logic."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from mover_status.plugins import ProviderRegistry
from mover_status.types import HealthStatus, NotificationData, NotificationResult


class DummyProvider:
    """Minimal provider implementation for registry tests."""

    def __init__(self, name: str) -> None:
        self.name: str = name

    async def send_notification(self, data: NotificationData) -> NotificationResult:  # pragma: no cover - protocol compliance
        _ = data
        return NotificationResult(
            success=True,
            provider_name=self.name,
            error_message=None,
            delivery_time_ms=5.0,
        )

    def validate_config(self) -> bool:  # pragma: no cover - protocol compliance
        return True

    async def health_check(self) -> HealthStatus:  # pragma: no cover - protocol compliance
        return HealthStatus(
            is_healthy=True,
            last_check=datetime.now(tz=UTC),
            consecutive_failures=0,
            error_message=None,
        )


def create_registry(*, unhealthy_threshold: int = 3) -> ProviderRegistry[DummyProvider]:
    """Return a typed registry for dummy providers."""
    return ProviderRegistry[DummyProvider](unhealthy_threshold=unhealthy_threshold)


def test_register_and_get_provider() -> None:
    """Provider should be retrievable after registration."""
    registry = create_registry(unhealthy_threshold=2)
    provider = DummyProvider("alpha")
    registry.register("alpha", provider)

    assert registry.get("alpha") is provider
    assert registry.get_all() == (provider,)
    assert registry.get_identifiers() == ("alpha",)


def test_duplicate_registration_rejected() -> None:
    """Duplicate provider identifiers should raise an error."""
    registry = create_registry()
    provider = DummyProvider("duplicate")
    registry.register("duplicate", provider)

    with pytest.raises(ValueError):
        registry.register("duplicate", provider)


def test_record_failure_marks_provider_unhealthy() -> None:
    """Providers exceeding the failure threshold should be excluded."""
    registry = create_registry(unhealthy_threshold=1)
    healthy = DummyProvider("healthy")
    failing = DummyProvider("failing")
    registry.register("healthy", healthy)
    registry.register("failing", failing)

    status = registry.record_failure("failing", error_message="timeout")
    assert status.is_healthy is False
    assert status.consecutive_failures == 1
    assert registry.get_healthy_providers() == (healthy,)
    assert registry.get_unhealthy_providers() == (failing,)


def test_record_success_restores_health() -> None:
    """Successful delivery should reset failure counters."""
    registry = create_registry(unhealthy_threshold=1)
    provider = DummyProvider("provider")
    registry.register("provider", provider)
    _ = registry.record_failure("provider", error_message="temporary outage")

    status = registry.record_success("provider")
    assert status.is_healthy is True
    assert status.consecutive_failures == 0
    assert registry.get_healthy_providers() == (provider,)
