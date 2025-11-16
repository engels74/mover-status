"""Plugin system public API exports."""

from mover_status.plugins.discovery import (
    PluginMetadata,
    discover_plugins,
    get_plugin,
    get_registered_plugins,
    register_plugin,
)

__all__ = [
    "PluginMetadata",
    "discover_plugins",
    "get_plugin",
    "get_registered_plugins",
    "register_plugin",
]
