"""Discord provider plugin metadata registration."""

from mover_status.plugins import PluginMetadata, register_plugin

register_plugin(
    PluginMetadata(
        identifier="discord",
        name="Discord",
        package=__name__,
        version="0.1.0",
        description="Sends mover status updates to Discord webhooks.",
        enabled_flag="discord_enabled",
    )
)
