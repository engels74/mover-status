"""Plugin system public API exports."""

from mover_status.plugins.discovery import (
    PluginMetadata,
    discover_plugins,
    get_plugin,
    get_registered_plugins,
    register_plugin,
)
from mover_status.plugins.registry import ProviderRegistry

__all__ = [
    "PluginMetadata",
    "discover_plugins",
    "get_plugin",
    "get_registered_plugins",
    "ProviderRegistry",
    "register_plugin",
]
