"""Tests for the dynamic plugin loader."""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from types import ModuleType
from typing import Callable

import pytest

from mover_status.plugins import PluginLoader
from mover_status.plugins.discovery import PluginMetadata
from mover_status.types import HealthStatus, NotificationData, NotificationResult


class DummyProvider:
    """Simple NotificationProvider implementation for loader tests."""

    def __init__(self, *, label: str = "default") -> None:
        self.label: str = label

    async def send_notification(self, data: NotificationData) -> NotificationResult:  # pragma: no cover - protocol method
        _ = data
        return NotificationResult(
            success=True,
            provider_name=self.label,
            error_message=None,
            delivery_time_ms=1.0,
        )

    def validate_config(self) -> bool:  # pragma: no cover - protocol method
        return True

    async def health_check(self) -> HealthStatus:  # pragma: no cover - protocol method
        return HealthStatus(
            is_healthy=True,
            last_check=datetime.now(tz=UTC),
            consecutive_failures=0,
            error_message=None,
        )


def install_module(monkeypatch: pytest.MonkeyPatch, module_name: str, **attrs: object) -> ModuleType:
    """Install a synthetic module (and parents) into sys.modules for importlib."""
    parts = module_name.split(".")
    for index, part in enumerate(parts):
        name = ".".join(parts[: index + 1])
        if name not in sys.modules:
            module = ModuleType(name)
            if index < len(parts) - 1:
                module.__path__ = []  # type: ignore[attr-defined] - mark as package
            monkeypatch.setitem(sys.modules, name, module)
        else:
            module = sys.modules[name]
            if index < len(parts) - 1 and not hasattr(module, "__path__"):
                module.__path__ = []  # type: ignore[attr-defined]
        if index > 0:
            parent_name = ".".join(parts[:index])
            setattr(sys.modules[parent_name], part, sys.modules[name])

    module = sys.modules[module_name]
    for key, value in attrs.items():
        setattr(module, key, value)
    return module


def stub_discovery(metadata: PluginMetadata) -> Callable[..., tuple[PluginMetadata, ...]]:
    """Return a discover_plugins stub for a single metadata entry."""

    def _discover_plugins(**_: object) -> tuple[PluginMetadata, ...]:
        return (metadata,)

    return _discover_plugins


def test_loader_initializes_enabled_plugins(monkeypatch: pytest.MonkeyPatch) -> None:
    """Loader should instantiate providers from enabled plugins."""
    metadata = PluginMetadata(
        identifier="alpha",
        name="Alpha",
        package="alpha_plugin",
        version="1.0.0",
        entrypoint="alpha_plugin:create_provider",
    )

    def create_provider() -> DummyProvider:
        return DummyProvider(label="alpha")

    _ = install_module(monkeypatch, "alpha_plugin", create_provider=create_provider)
    monkeypatch.setattr(
        "mover_status.plugins.loader.discover_plugins",
        stub_discovery(metadata),
    )

    loader = PluginLoader()
    loaded = loader.load_enabled_plugins(provider_flags={"alpha": True})
    assert len(loaded) == 1
    assert loaded[0].metadata is metadata
    assert isinstance(loaded[0].provider, DummyProvider)
    assert loaded[0].provider.label == "alpha"


def test_loader_skips_invalid_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    """Plugins returning invalid objects should be skipped without interrupting load."""
    metadata = PluginMetadata(
        identifier="beta",
        name="Beta",
        package="beta_plugin",
        version="1.0.0",
        entrypoint="beta_plugin:create_provider",
    )

    def create_provider() -> str:
        return "not-a-provider"

    _ = install_module(monkeypatch, "beta_plugin", create_provider=create_provider)
    monkeypatch.setattr(
        "mover_status.plugins.loader.discover_plugins",
        stub_discovery(metadata),
    )

    loader = PluginLoader()
    loaded = loader.load_enabled_plugins(provider_flags={"beta": True})
    assert loaded == ()


def test_loader_passes_factory_kwargs(monkeypatch: pytest.MonkeyPatch) -> None:
    """Per-provider keyword arguments should be forwarded to entrypoints."""
    metadata = PluginMetadata(
        identifier="gamma",
        name="Gamma",
        package="gamma_plugin",
        version="1.0.0",
        entrypoint="gamma_plugin:create_provider",
    )

    def create_provider(*, label: str) -> DummyProvider:
        return DummyProvider(label=label)

    _ = install_module(monkeypatch, "gamma_plugin", create_provider=create_provider)
    monkeypatch.setattr(
        "mover_status.plugins.loader.discover_plugins",
        stub_discovery(metadata),
    )

    loader = PluginLoader()
    loaded = loader.load_enabled_plugins(
        provider_flags={"gamma": True},
        factory_kwargs={"gamma": {"label": "forwarded"}},
    )
    assert len(loaded) == 1
    assert isinstance(loaded[0].provider, DummyProvider)
    assert loaded[0].provider.label == "forwarded"


def test_loader_uses_default_entrypoint(monkeypatch: pytest.MonkeyPatch) -> None:
    """Loader should derive module path when entrypoint is not provided."""
    metadata = PluginMetadata(
        identifier="delta",
        name="Delta",
        package="delta_plugin",
        version="1.0.0",
        entrypoint=None,
    )

    def create_provider() -> DummyProvider:
        return DummyProvider(label="delta")

    _ = install_module(monkeypatch, "delta_plugin")
    _ = install_module(monkeypatch, "delta_plugin.provider", create_provider=create_provider)
    monkeypatch.setattr(
        "mover_status.plugins.loader.discover_plugins",
        stub_discovery(metadata),
    )

    loader = PluginLoader()
    loaded = loader.load_enabled_plugins(provider_flags={"delta": True})
    assert len(loaded) == 1
    assert isinstance(loaded[0].provider, DummyProvider)
    assert loaded[0].provider.label == "delta"
