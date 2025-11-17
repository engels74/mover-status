"""Plugin discovery and metadata registration system.

This module implements convention-based discovery of provider plugins from the
``mover_status.plugins`` package. Plugin packages register descriptive
metadata, allowing the application to enumerate available providers and select
only those enabled in configuration.
"""

from __future__ import annotations

import importlib
import logging
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# Root directory that contains provider plugin packages
_PLUGIN_ROOT = Path(__file__).resolve().parent
# Fully-qualified package prefix for provider plugins
_PLUGIN_PACKAGE = __name__.rsplit(".", maxsplit=1)[0]
# Pattern enforcing lowercase identifiers for provider packages
_IDENTIFIER_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


@dataclass(slots=True, frozen=True)
class PluginMetadata:
    """Describes a provider plugin package."""

    identifier: str
    name: str
    package: str
    version: str
    description: str = ""
    enabled_flag: str | None = None
    entrypoint: str | None = None


_PLUGIN_REGISTRY: dict[str, PluginMetadata] = {}
_SCANNED_PACKAGES: set[str] = set()


def register_plugin(metadata: PluginMetadata) -> None:
    """Register plugin metadata provided by a plugin package.

    Plugin packages call this function during import to register their
    metadata. Identifiers must be unique and match the package directory name.
    """
    identifier = metadata.identifier.strip()
    if not _IDENTIFIER_PATTERN.match(identifier):
        msg = f"Plugin identifier must be lowercase alphanumeric with optional underscores: {identifier!r}"
        raise ValueError(msg)

    if identifier in _PLUGIN_REGISTRY:
        msg = f"Plugin identifier already registered: {identifier}"
        raise ValueError(msg)

    module_suffix = metadata.package.rsplit(".", maxsplit=1)[-1]
    if module_suffix != identifier:
        msg = f"Plugin identifier must match package name (identifier={identifier}, package={metadata.package})"
        raise ValueError(msg)

    _PLUGIN_REGISTRY[identifier] = metadata


def get_registered_plugins(*, force_rescan: bool = False) -> tuple[PluginMetadata, ...]:
    """Return registered plugin metadata sorted by identifier."""
    _scan_plugin_packages(force_rescan=force_rescan)
    return tuple(sorted(_PLUGIN_REGISTRY.values(), key=lambda meta: meta.identifier))


def discover_plugins(
    *,
    enabled_only: bool = False,
    provider_flags: Mapping[str, bool] | None = None,
    force_rescan: bool = False,
) -> tuple[PluginMetadata, ...]:
    """Discover available plugins and optionally filter to enabled providers."""
    plugins = get_registered_plugins(force_rescan=force_rescan)
    if not enabled_only:
        return plugins

    if provider_flags is None:
        msg = "provider_flags is required when enabled_only=True"
        raise ValueError(msg)

    enabled_plugins: list[PluginMetadata] = []
    for metadata in plugins:
        if _is_enabled(metadata, provider_flags):
            enabled_plugins.append(metadata)
    return tuple(enabled_plugins)


def get_plugin(identifier: str) -> PluginMetadata | None:
    """Retrieve metadata for the specified plugin identifier."""
    return _PLUGIN_REGISTRY.get(identifier)


def _is_enabled(metadata: PluginMetadata, flags: Mapping[str, bool]) -> bool:
    """Return True if the provider is enabled based on configuration flags."""
    slug_value = flags.get(metadata.identifier)
    if slug_value is not None:
        return bool(slug_value)

    if metadata.enabled_flag is None:
        return False

    flag_value = flags.get(metadata.enabled_flag)
    if flag_value is None:
        return False
    return bool(flag_value)


def _scan_plugin_packages(*, force_rescan: bool) -> None:
    """Scan the plugins directory and import provider packages."""
    for entry in _PLUGIN_ROOT.iterdir():
        if not entry.is_dir():
            continue
        if entry.name.startswith("_") or entry.name == "__pycache__":
            continue
        init_file = entry / "__init__.py"
        if not init_file.exists():
            continue

        module_name = f"{_PLUGIN_PACKAGE}.{entry.name}"
        if not force_rescan and module_name in _SCANNED_PACKAGES:
            continue

        registry_before = set(_PLUGIN_REGISTRY)
        try:
            _module = importlib.import_module(module_name)
        except Exception:
            logger.exception("Failed to import plugin package", extra={"plugin_module": module_name})
            continue

        if registry_before == set(_PLUGIN_REGISTRY):
            logger.warning(
                "Plugin package imported but did not register metadata",
                extra={"plugin_module": module_name},
            )

        _SCANNED_PACKAGES.add(module_name)
