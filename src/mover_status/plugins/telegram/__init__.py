"""Telegram provider plugin metadata registration."""

from mover_status.plugins import PluginMetadata, register_plugin

register_plugin(
    PluginMetadata(
        identifier="telegram",
        name="Telegram",
        package=__name__,
        version="0.1.0",
        description="Delivers mover status updates to Telegram chats.",
    )
)
