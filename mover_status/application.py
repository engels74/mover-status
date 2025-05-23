"""
Main application class for the Mover Status Monitor.

This module provides the Application class that manages the application lifecycle,
configuration loading, provider registration, and monitoring execution.
"""

import logging
from typing import cast

from mover_status.config.config_manager import ConfigManager
from mover_status.notification.manager import NotificationManager
from mover_status.notification.registry import ProviderRegistry
from mover_status.config.registry import ConfigRegistry
from mover_status.notification.base import NotificationProvider
from mover_status.notification.providers.telegram.provider import TelegramProvider, TelegramConfig
from mover_status.notification.providers.discord.provider import DiscordProvider
from mover_status.core.monitor import MonitorSession
from mover_status.utils.logger import setup_logger

# Get logger for this module
logger = logging.getLogger(__name__)


class Application:
    """
    Main application class for the Mover Status Monitor.

    This class manages the application lifecycle, including configuration loading,
    provider registration, and monitoring execution. It provides a centralized
    way to initialize and run the application.

    Attributes:
        config_path: Path to the configuration file.
        debug: Whether debug mode is enabled.
        config_manager: Configuration manager instance.
        notification_manager: Notification manager instance.
        provider_registry: Provider registry instance.
        config_registry: Configuration registry instance.
        is_running: Whether the application is currently running.
        loaded_plugins: Dictionary of loaded provider plugins.
    """

    def __init__(self, config_path: str | None = None, debug: bool = False) -> None:
        """
        Initialize the application.

        Args:
            config_path: Path to the configuration file, or None to use defaults.
            debug: Whether to enable debug logging.
        """
        self.config_path: str | None = config_path
        self.debug: bool = debug
        self.is_running: bool = False
        self.loaded_plugins: dict[str, NotificationProvider] = {}

        # Initialize core components
        self.config_manager: ConfigManager = ConfigManager(config_path)
        self.notification_manager: NotificationManager = NotificationManager()
        self.provider_registry: ProviderRegistry = ProviderRegistry()
        self.config_registry: ConfigRegistry = ConfigRegistry()

        # Load configuration
        _ = self.config_manager.load()

        # Set up logging (use default configuration)
        from mover_status.utils.logger import LoggerConfig
        _ = setup_logger("mover_status", LoggerConfig())

        logger.info("Application initialized")

    def load_and_register_providers(self) -> None:
        """
        Load and register notification providers based on configuration.

        This method reads the enabled providers from configuration and
        initializes them with their respective configurations.
        """
        enabled_providers = self.config_manager.config.get_nested_value("notification.enabled_providers")

        if not enabled_providers:
            logger.warning("No notification providers enabled")
            return

        # Cast to list of strings for type safety
        provider_list = cast(list[str], enabled_providers)

        for provider_name in provider_list:
            try:
                # Check if provider is enabled
                provider_enabled = self.config_manager.config.get_nested_value(
                    f"notification.providers.{provider_name}.enabled"
                )

                if not provider_enabled:
                    logger.debug(f"Provider {provider_name} is disabled, skipping")
                    continue

                # Initialize provider based on name
                provider = self._create_provider(provider_name)

                if provider:
                    # Register with notification manager
                    self.notification_manager.register_provider(provider)

                    # Track loaded plugin
                    self.loaded_plugins[provider_name] = provider

                    logger.info(f"Registered provider: {provider_name}")

            except Exception as e:
                logger.error(f"Failed to load provider {provider_name}: {e}")

    def _create_provider(self, provider_name: str) -> NotificationProvider | None:
        """
        Create a provider instance based on the provider name.

        Args:
            provider_name: Name of the provider to create.

        Returns:
            Provider instance or None if creation failed.
        """
        if provider_name == "telegram":
            return self._create_telegram_provider()
        elif provider_name == "discord":
            return self._create_discord_provider()
        else:
            logger.warning(f"Unknown provider: {provider_name}")
            return None

    def _create_telegram_provider(self) -> TelegramProvider | None:
        """Create and configure a Telegram provider."""
        try:
            # Get Telegram configuration
            bot_token = self.config_manager.config.get_nested_value("notification.providers.telegram.bot_token")
            chat_id = self.config_manager.config.get_nested_value("notification.providers.telegram.chat_id")

            if not bot_token or not chat_id:
                logger.error("Telegram provider configuration incomplete")
                return None

            # Create provider configuration
            config = {
                "bot_token": bot_token,
                "chat_id": chat_id
            }

            return TelegramProvider("telegram", cast(TelegramConfig, cast(object, config)))

        except Exception as e:
            logger.error(f"Failed to create Telegram provider: {e}")
            return None

    def _create_discord_provider(self) -> DiscordProvider | None:
        """Create and configure a Discord provider."""
        try:
            # Get Discord configuration
            webhook_url = self.config_manager.config.get_nested_value("notification.providers.discord.webhook_url")

            if not webhook_url:
                logger.error("Discord provider configuration incomplete")
                return None

            # Create provider configuration
            config = {
                "webhook_url": webhook_url
            }

            return DiscordProvider("discord", config)

        except Exception as e:
            logger.error(f"Failed to create Discord provider: {e}")
            return None

    def start(self) -> None:
        """
        Start the application.

        This method sets the application state to running and performs
        any necessary startup tasks.
        """
        self.is_running = True
        logger.info("Application started")

    def stop(self) -> None:
        """
        Stop the application.

        This method sets the application state to stopped and performs
        any necessary cleanup tasks.
        """
        self.is_running = False
        logger.info("Application stopped")

    def run(self) -> None:
        """
        Run the main application logic.

        This method creates a monitoring session and runs the monitoring loop
        with the configured notification manager.
        """
        if not self.is_running:
            logger.error("Application is not running. Call start() first.")
            return

        try:
            # Get monitoring configuration
            mover_path = str(self.config_manager.config.get_nested_value("monitoring.mover_executable"))
            cache_path = str(self.config_manager.config.get_nested_value("monitoring.cache_directory"))
            exclusions_raw = self.config_manager.config.get_nested_value("paths.exclude") or []  # pyright: ignore[reportUnknownVariableType]
            exclusions = cast(list[str], exclusions_raw)
            notification_increment_raw = self.config_manager.config.get_nested_value("notification.notification_increment") or 25
            notification_increment = int(cast(int, notification_increment_raw))
            poll_interval_raw = self.config_manager.config.get_nested_value("monitoring.poll_interval") or 1.0
            poll_interval = float(cast(float, poll_interval_raw))

            # Create and run monitor session
            monitor = MonitorSession(
                mover_path=mover_path,
                cache_path=cache_path,
                exclusions=exclusions,
                notification_increment=notification_increment,
                poll_interval=poll_interval
            )

            # Run monitoring loop
            monitor.run_monitoring_loop(self.notification_manager)

        except Exception as e:
            logger.error(f"Error running application: {e}")
            raise

    def load_provider_plugins(self) -> dict[str, type[NotificationProvider]]:
        """
        Load provider plugins using the provider registry.

        Returns:
            Dictionary of discovered provider classes.
        """
        return self.provider_registry.discover_providers()

    def initialize_plugin_with_configuration(
        self,
        provider_name: str,
        provider_class: type[NotificationProvider]
    ) -> NotificationProvider:
        """
        Initialize a plugin with its configuration.

        Args:
            provider_name: Name of the provider.
            provider_class: Provider class to initialize.

        Returns:
            Initialized provider instance.
        """
        # Get provider configuration
        provider_config = self.config_manager.config.get_nested_value(f"notification.providers.{provider_name}")

        # Initialize provider with configuration
        # Cast to object first to avoid type checker issues with generic provider classes
        return provider_class(provider_config)  # pyright: ignore[reportArgumentType]
