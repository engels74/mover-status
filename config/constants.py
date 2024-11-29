# config/constants.py

"""
Project-wide constants, type aliases, and configuration defaults.
Provides centralized definition of constants and types used across the application.
Provider-specific constants should be defined in their respective modules.
"""

from enum import IntEnum, StrEnum
from pathlib import Path
from typing import Dict, List, TypeAlias, Union

# Type Aliases with explicit nesting limits
JsonValue: TypeAlias = Union[str, int, float, bool, None]
JsonDict: TypeAlias = Dict[str, Union[JsonValue, Dict[str, JsonValue], List[JsonValue]]]
ByteSize: TypeAlias = int
Percentage: TypeAlias = float
PathLike: TypeAlias = Union[str, Path]
ExcludedPaths: TypeAlias = List[Path]
ProviderConfig: TypeAlias = Dict[str, Union[str, bool, int]]

class TimeConstants(IntEnum):
    """Time-related constants in seconds."""
    SECOND = 1
    MINUTE = 60 * SECOND
    HOUR = 60 * MINUTE
    DAY = 24 * HOUR
    VERSION_CHECK_INTERVAL = HOUR  # Check version every hour

class ByteSizes(IntEnum):
    """Byte size constants."""
    KB = 1024
    MB = KB * 1024
    GB = MB * 1024
    TB = GB * 1024

class NotificationProvider(StrEnum):
    """Supported notification providers."""
    DISCORD = "discord"
    TELEGRAM = "telegram"

class LogLevel(StrEnum):
    """Available logging levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

class NotificationLevel(StrEnum):
    """Notification severity levels."""
    DEBUG = "debug"         # Detailed information for debugging purposes
    INFO = "info"          # General informational messages
    WARNING = "warning"    # Warning messages that require attention
    ERROR = "error"        # Error messages indicating failures
    CRITICAL = "critical"  # Critical errors requiring immediate attention
    INFO_SUCCESS = "info_success"  # Success information messages
    INFO_FAILURE = "info_failure"  # Failure information messages

class MessagePriority(StrEnum):
    """Message priority levels."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"

class MessageType(StrEnum):
    """Message type classifications."""
    PROGRESS = "progress"      # Progress updates for ongoing operations
    COMPLETION = "completion"  # Operation completion notifications
    ERROR = "error"           # Error notifications
    WARNING = "warning"       # Warning messages (non-critical issues)
    SYSTEM = "system"         # System status and health updates
    DEBUG = "debug"           # Debug messages for development
    BATCH = "batch"          # Batch operation updates
    INTERACTIVE = "interactive"  # Messages with interactive elements
    CUSTOM = "custom"         # Custom/generic messages

class Version:
    """Version information."""
    CURRENT = "0.1.0"
    GITHUB_API_URL = "https://api.github.com/repos/engels74/mover-status/releases"

class Paths:
    """Default path configurations."""
    DEFAULT_CACHE = Path("/mnt/cache")
    DEFAULT_LOGS = Path("logs")
    DEFAULT_CONFIG = Path("config")
    MOVER_EXECUTABLE = Path("/usr/local/sbin/mover")

class Monitoring:
    """Monitoring-related constants."""
    PROCESS_CHECK_INTERVAL = 10  # seconds
    MONITORING_INTERVAL = 1      # seconds

    # Notification settings
    DEFAULT_INCREMENT = 25       # percentage
    MIN_INCREMENT = 5
    MAX_INCREMENT = 50
    RETRY_ATTEMPTS = 3
    RETRY_DELAY = 5             # seconds

class API:
    """API-related constants."""
    DEFAULT_TIMEOUT = 30        # seconds
    DEFAULT_RETRIES = 3
    DEFAULT_RETRY_DELAY = 5     # seconds

class Templates:
    """Message template definitions."""
    DEFAULT_MESSAGE = (
        "Transfer Progress: {percent}%\n"
        "Remaining Data: {remaining_data}\n"
        "ETC: {etc}"
    )

    PLACEHOLDERS = {
        "percent": "{percent}",
        "remaining_data": "{remaining_data}",
        "etc": "{etc}",
        "version": "{version}",
        "total_data": "{total_data}",
        "elapsed_time": "{elapsed_time}",
        "transfer_rate": "{transfer_rate}",
        "progress_bar": "{progress_bar}"
    }

class ErrorMessages:
    """Standard error message templates."""
    INVALID_PATH = "Invalid path specified: {path}"
    PROCESS_NOT_FOUND = "Mover process not found"
    NOTIFICATION_FAILED = "Failed to send notification: {error}"
    CONFIG_INVALID = "Invalid configuration: {detail}"
    VERSION_CHECK_FAILED = "Failed to check for updates: {error}"
    PROVIDER_NOT_FOUND = "Provider not found: {provider}"
    PROVIDER_DISABLED = "Provider is disabled: {provider}"
    RATE_LIMIT_EXCEEDED = "Rate limit exceeded for provider: {provider}"

class SuccessMessages:
    """Standard success message templates."""
    PROCESS_STARTED = "Mover process detected, starting monitoring"
    PROCESS_COMPLETED = "Mover process completed successfully"
    NOTIFICATION_SENT = "Notification sent successfully"
    VERSION_CURRENT = "Running latest version: {version}"
    PROVIDER_INITIALIZED = "Provider initialized successfully: {provider}"

# Export commonly used constants
__all__ = [
    'ByteSizes',
    'TimeConstants',
    'NotificationProvider',
    'LogLevel',
    'NotificationLevel',
    'MessagePriority',
    'MessageType',
    'Version',
    'Paths',
    'Monitoring',
    'API',
    'Templates',
    'ErrorMessages',
    'SuccessMessages',
]
