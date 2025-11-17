"""Integration tests for the plugin discovery, loader, and registry."""

from __future__ import annotations

import importlib
import sys
import textwrap
from collections.abc import Iterator
from pathlib import Path

import pytest

from mover_status.plugins import (
    PluginLoader,
    PluginMetadata,
    ProviderRegistry,
    discover_plugins,
)
from mover_status.types import NotificationProvider

_DISCOVERY_MODULE = "mover_status.plugins.discovery"


class PluginPackageBuilder:
    """Helper for creating isolated plugin packages for integration tests."""

    def __init__(self, base_path: Path, package_name: str) -> None:
        self._base_path: Path = base_path
        self._package_name: str = package_name
        self._package_path: Path = base_path / package_name
        self._package_path.mkdir(parents=True)
        _ = (self._package_path / "__init__.py").write_text("", encoding="utf-8")
        importlib.invalidate_caches()

    @property
    def package(self) -> str:
        return self._package_name

    @property
    def package_path(self) -> Path:
        return self._package_path

    def create_plugin(self, identifier: str, *, enabled_flag: str | None = None) -> None:
        """Create a synthetic plugin package with metadata and provider factory."""
        plugin_dir = self._package_path / identifier
        plugin_dir.mkdir()
        _ = (plugin_dir / "__init__.py").write_text(
            self._metadata_source(identifier, enabled_flag),
            encoding="utf-8",
        )
        _ = (plugin_dir / "provider.py").write_text(
            self._provider_source(identifier),
            encoding="utf-8",
        )
        importlib.invalidate_caches()

    def cleanup(self) -> None:
        """Remove dynamically created modules from sys.modules."""
        prefix = f"{self._package_name}."
        for module_name in list(sys.modules):
            if module_name == self._package_name or module_name.startswith(prefix):
                _ = sys.modules.pop(module_name, None)
        importlib.invalidate_caches()

    def _metadata_source(self, identifier: str, enabled_flag: str | None) -> str:
        enabled_line = f'        enabled_flag="{enabled_flag}",\n' if enabled_flag else ""
        lines = [
            "from mover_status.plugins import PluginMetadata, register_plugin",
            "",
            "register_plugin(",
            "    PluginMetadata(",
            f'        identifier="{identifier}",',
            f'        name="{identifier.title()}",',
            "        package=__name__,",
            '        version="1.0.0",',
        ]
        if enabled_line:
            lines.append(enabled_line.rstrip("\n"))
        lines.extend(
            [
                "    )",
                ")",
            ]
        )
        return "\n".join(lines) + "\n"

    def _provider_source(self, identifier: str) -> str:
        """Return provider module source code for the synthetic plugin."""
        return textwrap.dedent(
            f'''
            from __future__ import annotations

            from datetime import UTC, datetime

            from mover_status.types import (
                HealthStatus,
                NotificationData,
                NotificationResult,
            )


            class ExampleProvider:
                def __init__(self, label: str = "{identifier}") -> None:
                    self.label = label

                async def send_notification(self, data: NotificationData) -> NotificationResult:
                    _ = data
                    return NotificationResult(
                        success=True,
                        provider_name=self.label,
                        error_message=None,
                        delivery_time_ms=1.0,
                    )

                def validate_config(self) -> bool:
                    return True

                async def health_check(self) -> HealthStatus:
                    return HealthStatus(
                        is_healthy=True,
                        last_check=datetime.now(tz=UTC),
                        consecutive_failures=0,
                        error_message=None,
                    )


            def create_provider(*, label: str = "{identifier}") -> ExampleProvider:
                return ExampleProvider(label=label)
            '''
        )


@pytest.fixture()
def plugin_test_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[PluginPackageBuilder]:
    """Provide isolated plugin package directory wired to discovery module."""
    base_path = tmp_path / "plugin_packages"
    package_name = "integration_plugins"
    builder = PluginPackageBuilder(base_path, package_name)

    path_entry = str(base_path)
    sys.path.insert(0, path_entry)
    monkeypatch.setattr(f"{_DISCOVERY_MODULE}._PLUGIN_ROOT", builder.package_path)
    monkeypatch.setattr(f"{_DISCOVERY_MODULE}._PLUGIN_PACKAGE", builder.package)
    empty_registry: dict[str, PluginMetadata] = {}
    monkeypatch.setattr(f"{_DISCOVERY_MODULE}._PLUGIN_REGISTRY", empty_registry)
    empty_scanned: set[str] = set()
    monkeypatch.setattr(f"{_DISCOVERY_MODULE}._SCANNED_PACKAGES", empty_scanned)

    try:
        yield builder
    finally:
        builder.cleanup()
        sys.path.remove(path_entry)


def test_plugin_discovery_detects_packages(plugin_test_env: PluginPackageBuilder) -> None:
    """Plugin discovery should read metadata from the plugins directory."""
    plugin_test_env.create_plugin("alpha")

    discovered = discover_plugins(force_rescan=True)
    identifiers = tuple(metadata.identifier for metadata in discovered)

    assert identifiers == ("alpha",)


def test_loader_respects_configuration_flags(plugin_test_env: PluginPackageBuilder) -> None:
    """Plugin loader should only initialize providers enabled in configuration."""
    plugin_test_env.create_plugin("alpha", enabled_flag="alpha_enabled")
    plugin_test_env.create_plugin("beta", enabled_flag="beta_enabled")

    loader = PluginLoader()
    loaded = loader.load_enabled_plugins(
        provider_flags={"alpha_enabled": True, "beta_enabled": False},
        force_rescan=True,
    )

    assert tuple(plugin.identifier for plugin in loaded) == ("alpha",)


def test_registry_registers_loaded_providers(plugin_test_env: PluginPackageBuilder) -> None:
    """Loaded providers should be stored and retrievable from the registry."""
    plugin_test_env.create_plugin("alpha")
    plugin_test_env.create_plugin("beta")

    loader = PluginLoader()
    loaded = loader.load_enabled_plugins(
        provider_flags={"alpha": True, "beta": True},
        force_rescan=True,
    )
    registry: ProviderRegistry[NotificationProvider] = ProviderRegistry()
    for plugin in loaded:
        registry.register(plugin.identifier, plugin.provider)

    assert registry.get_identifiers() == ("alpha", "beta")
    assert registry.get_all() == tuple(plugin.provider for plugin in loaded)


def test_registry_tracks_health_status(plugin_test_env: PluginPackageBuilder) -> None:
    """Registry health tracking should reflect successes and failures."""
    plugin_test_env.create_plugin("gamma")

    loader = PluginLoader()
    (plugin,) = loader.load_enabled_plugins(
        provider_flags={"gamma": True},
        force_rescan=True,
    )
    registry: ProviderRegistry[NotificationProvider] = ProviderRegistry(unhealthy_threshold=2)
    registry.register(plugin.identifier, plugin.provider)

    first_failure = registry.record_failure(plugin.identifier, error_message="timeout")
    assert first_failure.is_healthy is True

    second_failure = registry.record_failure(
        plugin.identifier,
        error_message="still failing",
    )
    assert second_failure.is_healthy is False
    assert registry.get_unhealthy_providers() == (plugin.provider,)

    recovery = registry.record_success(plugin.identifier)
    assert recovery.is_healthy is True
    assert registry.get_healthy_providers() == (plugin.provider,)
