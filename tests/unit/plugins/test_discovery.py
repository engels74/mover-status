"""Tests for plugin discovery and metadata registration."""

import pytest

from mover_status.plugins import (
    PluginMetadata,
    discover_plugins,
    get_registered_plugins,
    register_plugin,
)


def test_registered_plugins_include_defaults() -> None:
    """Bundled plugins should register metadata automatically."""
    registered = get_registered_plugins()
    identifiers = {plugin.identifier for plugin in registered}
    assert {"discord", "telegram"}.issubset(identifiers)


def test_discover_plugins_filters_enabled_flags() -> None:
    """Only enabled providers should be returned when filtering."""
    enabled = discover_plugins(
        enabled_only=True,
        provider_flags={"discord": True, "telegram": False},
    )
    identifiers = {meta.identifier for meta in enabled}
    assert identifiers == {"discord"}


def test_discover_plugins_accepts_slug_keys() -> None:
    """Slug keys without _enabled suffix should also be honored."""
    enabled = discover_plugins(
        enabled_only=True,
        provider_flags={"telegram": True},
    )
    identifiers = {meta.identifier for meta in enabled}
    assert identifiers == {"telegram"}


def test_discover_plugins_requires_provider_flags() -> None:
    """Filtering without configuration flags should fail fast."""
    with pytest.raises(ValueError):
        _ = discover_plugins(enabled_only=True)


def test_register_plugin_rejects_duplicates() -> None:
    """Duplicate plugin registration should be prevented."""
    metadata = PluginMetadata(
        identifier="discord",
        name="Duplicate Discord",
        package="mover_status.plugins.discord",
        version="1.0.0",
    )
    with pytest.raises(ValueError):
        register_plugin(metadata)
