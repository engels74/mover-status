# config/constants.py

"""
Project-wide constants, type aliases, and configuration defaults.
Provider-specific constants should be defined in their respective modules.
"""

from enum import Enum
from pathlib import Path
from typing import Dict, List, TypeAlias, Union

# Version Information
CURRENT_VERSION = "0.1.0"
GITHUB_API_RELEASES_URL = "https://api.github.com/repos/engels74/mover-status/releases"
VERSION_CHECK_INTERVAL = 3600  # 1 hour in seconds

# Default Paths
DEFAULT_CACHE_PATH = Path("/mnt/cache")
DEFAULT_LOG_DIR = Path("logs")
DEFAULT_CONFIG_DIR = Path("config")

# Process Settings
MOVER_EXECUTABLE = "/usr/local/sbin/mover"
PROCESS_CHECK_INTERVAL = 10  # seconds
MONITORING_INTERVAL = 1  # seconds

# Notification Settings
DEFAULT_NOTIFICATION_INCREMENT = 25  # percentage
MIN_NOTIFICATION_INCREMENT = 5
MAX_NOTIFICATION_INCREMENT = 50
NOTIFICATION_RETRY_ATTEMPTS = 3
NOTIFICATION_RETRY_DELAY = 5  # seconds

# Size Constants
BYTES_PER_KB = 1024
BYTES_PER_MB = BYTES_PER_KB * 1024
BYTES_PER_GB = BYTES_PER_MB * 1024
BYTES_PER_TB = BYTES_PER_GB * 1024

class NotificationProvider(str, Enum):
    """Supported notification providers."""
    DISCORD = "discord"
    TELEGRAM = "telegram"

class LogLevel(str, Enum):
    """Available logging levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

# Type Aliases
ByteSize: TypeAlias = int
Percentage: TypeAlias = float
PathLike: TypeAlias = Union[str, Path]
ExcludedPaths: TypeAlias = List[Path]
ProviderConfig: TypeAlias = Dict[str, Union[str, bool, int]]

# Time Constants
SECONDS_PER_MINUTE = 60
SECONDS_PER_HOUR = SECONDS_PER_MINUTE * 60
SECONDS_PER_DAY = SECONDS_PER_HOUR * 24

# Error Messages
ERR_INVALID_PATH = "Invalid path specified: {path}"
ERR_PROCESS_NOT_FOUND = "Mover process not found"
ERR_NOTIFICATION_FAILED = "Failed to send notification: {error}"
ERR_CONFIG_INVALID = "Invalid configuration: {detail}"
ERR_VERSION_CHECK_FAILED = "Failed to check for updates: {error}"

# Success Messages
MSG_PROCESS_STARTED = "Mover process detected, starting monitoring"
MSG_PROCESS_COMPLETED = "Mover process completed successfully"
MSG_NOTIFICATION_SENT = "Notification sent successfully"
MSG_VERSION_CURRENT = "Running latest version: {version}"

# Template Placeholders
TEMPLATE_PLACEHOLDERS = {
    "percent": "{percent}",
    "remaining_data": "{remaining_data}",
    "etc": "{etc}",
    "version": "{version}",
    "total_data": "{total_data}",
    "elapsed_time": "{elapsed_time}"
}
