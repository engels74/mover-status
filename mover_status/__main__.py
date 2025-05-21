"""
Main application entry point for the Mover Status Monitor.

This module provides the command line interface and main application loop
for the Mover Status Monitor. It handles command line arguments, initializes
the application components, and runs the monitoring loop.
"""

# pyright: reportUnknownMemberType=false
# pyright: reportUnknownArgumentType=false
# pyright: reportUnknownVariableType=false
# The above directives are necessary because this module handles configuration data
# loaded from YAML files, which have dynamic types that cannot be fully typed statically.
# We use runtime type checking with isinstance() to ensure type safety.

import sys
import argparse
import logging
from typing import TypedDict

from mover_status import __version__
from mover_status.config.config_manager import ConfigManager
from mover_status.utils.logger import setup_logger, LoggerConfig, LogLevel, LogFormat
from mover_status.notification.manager import NotificationManager
from mover_status.notification.providers.telegram.provider import TelegramProvider, TelegramConfig
from mover_status.notification.providers.discord.provider import DiscordProvider, DiscordConfig, EmbedColorsType
from mover_status.core.monitor import MonitorSession
from mover_status.core.dry_run import run_dry_mode
from mover_status.core.version import check_for_updates

# Get logger for this module
logger = logging.getLogger(__name__)


# Define TypedDict classes for configuration structures
class ConfigDict(TypedDict, total=False):
    """Generic dictionary type for configuration values."""
    enabled: bool
    bot_token: str
    chat_id: str
    message_template: str
    parse_mode: str
    disable_notification: bool
    webhook_url: str
    username: str
    use_embeds: bool
    embed_title: str
    embed_colors: dict[str, int]


def parse_args() -> argparse.Namespace:
    """
    Parse command line arguments.

    Returns:
        argparse.Namespace: The parsed command line arguments.
    """
    parser = argparse.ArgumentParser(
        description="Mover Status Monitor - Track Unraid mover progress and send notifications",
        add_help=False  # Disable built-in help to handle it manually
    )

    # Configuration options
    _ = parser.add_argument(
        "-c", "--config",
        help="Path to configuration file",
        type=str,
        default=None
    )

    # Mode options
    _ = parser.add_argument(
        "--dry-run",
        help="Run in dry run mode (test notifications without monitoring)",
        action="store_true",
        default=False
    )

    _ = parser.add_argument(
        "--debug",
        help="Enable debug logging",
        action="store_true",
        default=False
    )

    # Information options
    _ = parser.add_argument(
        "-v", "--version",
        help="Show version information and exit",
        action="store_true",
        default=False
    )

    _ = parser.add_argument(
        "-h", "--help",
        help="Show this help message and exit",
        action="store_true",
        default=False
    )

    return parser.parse_args()


def handle_version_command() -> None:
    """
    Handle the version command.

    This function prints the version information and exits.
    """
    print(f"Mover Status Monitor v{__version__}")
    sys.exit(0)


def handle_help_command(parser: argparse.ArgumentParser) -> None:
    """
    Handle the help command.

    This function prints the help message and exits.

    Args:
        parser: The argument parser to get help from.
    """
    print(parser.format_help())
    sys.exit(0)


def initialize_app(config_path: str | None, debug: bool) -> tuple[ConfigManager, NotificationManager]:
    """
    Initialize the application components.

    This function initializes the configuration manager, sets up logging,
    and initializes the notification manager with configured providers.

    Args:
        config_path: Path to the configuration file, or None to use defaults.
        debug: Whether to enable debug logging.

    Returns:
        Tuple containing the initialized ConfigManager and NotificationManager.
    """
    # Initialize configuration manager
    config_manager = ConfigManager(config_path)
    _ = config_manager.load()

    # Set up logging
    log_config = LoggerConfig(
        console_enabled=True,
        level=LogLevel.DEBUG if debug else LogLevel.INFO,
        format=LogFormat.DETAILED if debug else LogFormat.SIMPLE
    )
    _ = setup_logger("mover_status", log_config)
    logger.info("Mover Status Monitor starting up")
    logger.info(f"Version: {__version__}")

    # Check for updates
    try:
        update_available = check_for_updates()
        if update_available:
            logger.info("A new version is available. Please check the GitHub repository.")
        else:
            logger.info("You are running the latest version.")
    except Exception as e:
        logger.warning(f"Failed to check for updates: {e}")

    # Initialize notification manager
    notification_manager = NotificationManager()
    logger.info("Notification manager initialized")

    # Initialize notification providers based on configuration
    try:
        # Get list of enabled providers
        enabled_providers_obj = config_manager.config.get_nested_value("notification.enabled_providers")

        # Ensure enabled_providers is a list of strings
        if not isinstance(enabled_providers_obj, list):
            logger.warning("No enabled providers found in configuration")
            return config_manager, notification_manager

        # Convert to a list of strings, filtering out non-string items
        enabled_providers: list[str] = []
        for item in enabled_providers_obj:
            # Use type checking to ensure we only add strings
            if isinstance(item, str):
                enabled_providers.append(item)

        logger.info(f"Enabled providers: {', '.join(enabled_providers) if enabled_providers else 'None'}")

        # Initialize each enabled provider
        for provider_name in enabled_providers:
            if provider_name == "telegram":
                # Get Telegram configuration
                telegram_config_obj = config_manager.config.get_nested_value("notification.providers.telegram")
                if isinstance(telegram_config_obj, dict):
                    # Create the properly typed config dictionary with safe type conversions
                    telegram_config: TelegramConfig = {}

                    # Add required fields with proper type conversion
                    if "enabled" in telegram_config_obj:

                        telegram_config["enabled"] = bool(telegram_config_obj.get("enabled", False))
                    else:
                        telegram_config["enabled"] = False

                    if "bot_token" in telegram_config_obj:
                        token_value = telegram_config_obj.get("bot_token")
                        telegram_config["bot_token"] = str(token_value) if token_value is not None else ""
                    else:
                        telegram_config["bot_token"] = ""

                    if "chat_id" in telegram_config_obj:
                        chat_id_value = telegram_config_obj.get("chat_id")
                        telegram_config["chat_id"] = str(chat_id_value) if chat_id_value is not None else ""
                    else:
                        telegram_config["chat_id"] = ""

                    if "message_template" in telegram_config_obj:
                        template_value = telegram_config_obj.get("message_template")
                        telegram_config["message_template"] = str(template_value) if template_value is not None else ""
                    else:
                        telegram_config["message_template"] = ""

                    if "parse_mode" in telegram_config_obj:
                        parse_mode_value = telegram_config_obj.get("parse_mode")
                        telegram_config["parse_mode"] = str(parse_mode_value) if parse_mode_value is not None else "HTML"
                    else:
                        telegram_config["parse_mode"] = "HTML"

                    if "disable_notification" in telegram_config_obj:
                        disable_notif_value = telegram_config_obj.get("disable_notification")
                        telegram_config["disable_notification"] = bool(disable_notif_value) if disable_notif_value is not None else False
                    else:
                        telegram_config["disable_notification"] = False

                    # Create and register Telegram provider
                    telegram_provider = TelegramProvider(telegram_config)
                    if telegram_provider.enabled:
                        # Validate configuration
                        errors = telegram_provider.validate_config()
                        if errors:
                            logger.error(f"Invalid Telegram configuration: {', '.join(errors)}")
                        else:
                            notification_manager.register_provider(telegram_provider)
                            logger.info("Telegram provider registered")
                    else:
                        logger.info("Telegram provider is disabled in configuration")
                else:
                    logger.warning("Invalid Telegram configuration")

            elif provider_name == "discord":
                # Get Discord configuration
                discord_config_obj = config_manager.config.get_nested_value("notification.providers.discord")
                if isinstance(discord_config_obj, dict):
                    # Create a properly typed EmbedColorsType with default values
                    embed_colors: EmbedColorsType = {
                        "low_progress": 16744576,  # Light Red (0-34%)
                        "mid_progress": 16753920,  # Light Orange (35-65%)
                        "high_progress": 9498256,  # Light Green (66-99%)
                        "complete": 65280,         # Green (100%)
                    }

                    # Handle embed colors with proper typing
                    if "embed_colors" in discord_config_obj:
                        embed_colors_raw = discord_config_obj.get("embed_colors")
                        if isinstance(embed_colors_raw, dict):
                            # Update each color if it exists in the configuration
                            for color_key in ["low_progress", "mid_progress", "high_progress", "complete"]:
                                if color_key in embed_colors_raw:
                                    color_value = embed_colors_raw.get(color_key)
                                    if isinstance(color_value, int):
                                        embed_colors[color_key] = color_value

                    # Create the properly typed config dictionary with safe type conversions
                    discord_config: DiscordConfig = {}

                    # Add required fields with proper type conversion
                    if "enabled" in discord_config_obj:
                        enabled_value = discord_config_obj.get("enabled")
                        discord_config["enabled"] = bool(enabled_value) if enabled_value is not None else False
                    else:
                        discord_config["enabled"] = False

                    if "webhook_url" in discord_config_obj:
                        webhook_value = discord_config_obj.get("webhook_url")
                        discord_config["webhook_url"] = str(webhook_value) if webhook_value is not None else ""
                    else:
                        discord_config["webhook_url"] = ""

                    if "username" in discord_config_obj:
                        username_value = discord_config_obj.get("username")
                        discord_config["username"] = str(username_value) if username_value is not None else "Mover Bot"
                    else:
                        discord_config["username"] = "Mover Bot"

                    if "message_template" in discord_config_obj:
                        template_value = discord_config_obj.get("message_template")
                        discord_config["message_template"] = str(template_value) if template_value is not None else ""
                    else:
                        discord_config["message_template"] = ""

                    if "use_embeds" in discord_config_obj:
                        embeds_value = discord_config_obj.get("use_embeds")
                        discord_config["use_embeds"] = bool(embeds_value) if embeds_value is not None else True
                    else:
                        discord_config["use_embeds"] = True

                    if "embed_title" in discord_config_obj:
                        title_value = discord_config_obj.get("embed_title")
                        discord_config["embed_title"] = str(title_value) if title_value is not None else "Mover: Moving Data"
                    else:
                        discord_config["embed_title"] = "Mover: Moving Data"

                    # Add the embed colors
                    discord_config["embed_colors"] = embed_colors

                    # Create and register Discord provider
                    discord_provider = DiscordProvider(discord_config)
                    if discord_provider.enabled:
                        # Validate configuration
                        errors = discord_provider.validate_config()
                        if errors:
                            logger.error(f"Invalid Discord configuration: {', '.join(errors)}")
                        else:
                            notification_manager.register_provider(discord_provider)
                            logger.info("Discord provider registered")
                    else:
                        logger.info("Discord provider is disabled in configuration")
                else:
                    logger.warning("Invalid Discord configuration")
            else:
                logger.warning(f"Unknown provider: {provider_name}")
    except Exception as e:
        logger.error(f"Error initializing notification providers: {e}", exc_info=True)

    return config_manager, notification_manager


def main() -> None:
    """
    Main application entry point.

    This function parses command line arguments, initializes the application,
    and runs the monitoring loop or dry run mode as specified.
    """
    # Parse command line arguments
    args = parse_args()

    # Create parser for help command
    parser = argparse.ArgumentParser(
        description="Mover Status Monitor - Track Unraid mover progress and send notifications",
        add_help=False
    )
    _ = parser.add_argument("-c", "--config", help="Path to configuration file")
    _ = parser.add_argument("--dry-run", help="Run in dry run mode (test notifications without monitoring)", action="store_true")
    _ = parser.add_argument("--debug", help="Enable debug logging", action="store_true")
    _ = parser.add_argument("-v", "--version", help="Show version information and exit", action="store_true")
    _ = parser.add_argument("-h", "--help", help="Show this help message and exit", action="store_true")

    # Handle information commands
    if getattr(args, 'version', False):
        handle_version_command()
    if getattr(args, 'help', False):
        handle_help_command(parser)

    # Initialize application
    config_manager, notification_manager = initialize_app(
        getattr(args, 'config', None),
        bool(getattr(args, 'debug', False))
    )

    try:
        # Run in dry run mode if specified
        if getattr(args, 'dry_run', False):
            logger.info("Running in dry run mode")
            _ = run_dry_mode(notification_manager)
        else:
            # Create and run monitor session
            logger.info("Starting monitoring session")

            # Get configuration values with proper type casting
            mover_path = str(config_manager.config.get_nested_value("monitoring.mover_executable"))
            cache_path = str(config_manager.config.get_nested_value("monitoring.cache_directory"))

            # Handle exclusions list
            exclusions_obj = config_manager.config.get_nested_value("paths.exclude")
            exclusions: list[str] | None = None
            if isinstance(exclusions_obj, list):
                # Convert to a list of strings, filtering out non-string items
                exclusions = []
                # Use the object directly
                exclusions_list = exclusions_obj

                # Process each item, checking its type
                for item in exclusions_list:
                    if isinstance(item, str):
                        exclusions.append(item)

            # Get numeric values with safe conversion
            notification_increment_obj = config_manager.config.get_nested_value("notification.notification_increment")
            notification_increment = 25  # Default value
            if isinstance(notification_increment_obj, (int, float, str)):
                try:
                    notification_increment = int(notification_increment_obj)
                except (ValueError, TypeError):
                    pass

            poll_interval_obj = config_manager.config.get_nested_value("monitoring.poll_interval")
            poll_interval = 1.0  # Default value
            if isinstance(poll_interval_obj, (int, float, str)):
                try:
                    poll_interval = float(poll_interval_obj)
                except (ValueError, TypeError):
                    pass

            # Create and run monitor session
            monitor_session = MonitorSession(
                mover_path=mover_path,
                cache_path=cache_path,
                exclusions=exclusions,
                notification_increment=notification_increment,
                poll_interval=poll_interval,
            )
            monitor_session.run_monitoring_loop(notification_manager)
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down")
    except Exception as e:
        logger.error(f"Error in main loop: {e}", exc_info=True)
    finally:
        logger.info("Mover Status Monitor shutting down")


if __name__ == "__main__":
    main()