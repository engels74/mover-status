"""
Mover Status Monitor - A Python 3.13 application to monitor Unraid's mover process.

This package provides functionality to monitor the Unraid mover process and send
notifications about its progress via various notification providers.
"""

__version__ = "0.1.0"

# Export public interface
from mover_status.config import ConfigManager
from mover_status.core.monitor import MonitorSession
from mover_status.core.dry_run import run_dry_mode
from mover_status.notification.manager import NotificationManager
from mover_status.notification.providers.telegram.provider import TelegramProvider
from mover_status.notification.providers.discord.provider import DiscordProvider
from mover_status.utils.logger import setup_logger, LoggerConfig, LogLevel, LogFormat

# Define public API
__all__ = [
    'ConfigManager',
    'MonitorSession',
    'run_dry_mode',
    'NotificationManager',
    'TelegramProvider',
    'DiscordProvider',
    'setup_logger',
    'LoggerConfig',
    'LogLevel',
    'LogFormat',
]