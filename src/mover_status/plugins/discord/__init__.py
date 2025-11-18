"""Discord provider plugin metadata registration."""

import re
from typing import Final

from mover_status.plugins import PluginMetadata, register_plugin
from mover_status.utils.sanitization import REDACTED, register_sanitization_pattern

# URL sanitization pattern for Discord webhook URLs
# Matches: https://discord.com/api/webhooks/<id>/<token>
#          https://discordapp.com/api/webhooks/<id>/<token>
_DISCORD_WEBHOOK_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"(https?://(?:discord(?:app)?\.com)/api/webhooks/\d+/)([^/?#]+)",
    re.IGNORECASE,
)

register_plugin(
    PluginMetadata(
        identifier="discord",
        name="Discord",
        package=__name__,
        version="0.1.0",
        description="Sends mover status updates to Discord webhooks.",
    )
)

# Register URL sanitization pattern at import time (before provider instantiation)
# This ensures sanitization works even in unit tests that don't create providers
register_sanitization_pattern(_DISCORD_WEBHOOK_PATTERN, rf"\1{REDACTED}")
