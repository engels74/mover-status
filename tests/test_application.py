"""
Tests for the Application class.

This module contains tests for the main Application class that manages
the application lifecycle, configuration, and provider loading.
"""

from unittest.mock import Mock, patch

from mover_status.application import Application
from mover_status.config.config_manager import ConfigManager
from mover_status.notification.manager import NotificationManager
from mover_status.notification.registry import ProviderRegistry
from mover_status.config.registry import ConfigRegistry


class TestApplication:
    """Test cases for the Application class."""

    def test_initialize_application_with_configuration(self) -> None:
        """Test initializing the application with configuration."""
        # This test should fail initially since Application class doesn't exist
        with patch('mover_status.application.ConfigManager') as mock_config_manager, \
             patch('mover_status.application.setup_logger') as mock_setup_logger, \
             patch('mover_status.application.NotificationManager') as mock_notification_manager, \
             patch('mover_status.application.ProviderRegistry') as mock_provider_registry, \
             patch('mover_status.application.ConfigRegistry') as mock_config_registry:

            # Setup mocks
            mock_config_instance = Mock(spec=ConfigManager)
            mock_config_manager.return_value = mock_config_instance

            mock_notification_instance = Mock(spec=NotificationManager)
            mock_notification_manager.return_value = mock_notification_instance

            mock_provider_registry_instance = Mock(spec=ProviderRegistry)
            mock_provider_registry.return_value = mock_provider_registry_instance

            mock_config_registry_instance = Mock(spec=ConfigRegistry)
            mock_config_registry.return_value = mock_config_registry_instance

            # Create application instance
            config_path = "test_config.yaml"
            debug = True
            app = Application(config_path=config_path, debug=debug)

            # Verify initialization
            assert app.config_path == config_path
            assert app.debug == debug
            assert app.config_manager == mock_config_instance
            assert app.notification_manager == mock_notification_instance
            assert app.provider_registry == mock_provider_registry_instance
            assert app.config_registry == mock_config_registry_instance

            # Verify configuration was loaded
            mock_config_instance.load.assert_called_once()  # pyright: ignore[reportAny]

            # Verify logger was set up
            mock_setup_logger.assert_called_once()

    def test_load_and_register_providers(self) -> None:
        """Test loading and registering notification providers."""
        with patch('mover_status.application.ConfigManager') as mock_config_manager, \
             patch('mover_status.application.setup_logger'), \
             patch('mover_status.application.NotificationManager') as mock_notification_manager, \
             patch('mover_status.application.ProviderRegistry') as mock_provider_registry, \
             patch('mover_status.application.ConfigRegistry') as mock_config_registry, \
             patch('mover_status.application.TelegramProvider') as mock_telegram_provider, \
             patch('mover_status.application.DiscordProvider') as mock_discord_provider:

            # Setup mocks
            mock_config_instance = Mock(spec=ConfigManager)
            mock_config_manager.return_value = mock_config_instance

            mock_notification_instance = Mock(spec=NotificationManager)
            mock_notification_manager.return_value = mock_notification_instance

            mock_provider_registry_instance = Mock(spec=ProviderRegistry)
            mock_provider_registry.return_value = mock_provider_registry_instance

            mock_config_registry_instance = Mock(spec=ConfigRegistry)
            mock_config_registry.return_value = mock_config_registry_instance

            # Mock configuration values
            def get_config_value(key_str: str) -> str | list[str] | bool | None:
                config_values = {
                    "notification.enabled_providers": ["telegram", "discord"],
                    "notification.providers.telegram.enabled": True,
                    "notification.providers.discord.enabled": True,
                    "notification.providers.telegram.bot_token": "test_token",
                    "notification.providers.telegram.chat_id": "test_chat",
                    "notification.providers.discord.webhook_url": "test_webhook"
                }
                return config_values.get(key_str, None)

            # Mock the config attribute and its get_nested_value method
            mock_config_obj = Mock()
            mock_config_obj.get_nested_value.side_effect = get_config_value  # pyright: ignore[reportAny]
            mock_config_instance.config = mock_config_obj

            # Create application and load providers
            app = Application(config_path="test_config.yaml", debug=False)
            app.load_and_register_providers()

            # Verify providers were created and registered
            mock_telegram_provider.assert_called_once()
            mock_discord_provider.assert_called_once()
            assert mock_notification_instance.register_provider.call_count == 2  # pyright: ignore[reportAny]

    def test_application_lifecycle_start_run_stop(self) -> None:
        """Test application lifecycle (start, run, stop)."""
        with patch('mover_status.application.ConfigManager') as mock_config_manager, \
             patch('mover_status.application.setup_logger'), \
             patch('mover_status.application.NotificationManager') as mock_notification_manager, \
             patch('mover_status.application.ProviderRegistry') as mock_provider_registry, \
             patch('mover_status.application.ConfigRegistry') as mock_config_registry, \
             patch('mover_status.application.MonitorSession') as mock_monitor_session:

            # Setup mocks
            mock_config_instance = Mock(spec=ConfigManager)
            mock_config_manager.return_value = mock_config_instance

            mock_notification_instance = Mock(spec=NotificationManager)
            mock_notification_manager.return_value = mock_notification_instance

            mock_provider_registry_instance = Mock(spec=ProviderRegistry)
            mock_provider_registry.return_value = mock_provider_registry_instance

            mock_config_registry_instance = Mock(spec=ConfigRegistry)
            mock_config_registry.return_value = mock_config_registry_instance

            mock_monitor_instance = Mock()
            mock_monitor_session.return_value = mock_monitor_instance

            # Mock configuration values
            def get_config_value(key_str: str) -> str | list[str] | int | float | None:
                config_values = {
                    "monitoring.mover_executable": "/test/mover",
                    "monitoring.cache_directory": "/test/cache",
                    "paths.exclude": ["/test/exclude"],
                    "notification.notification_increment": 20,
                    "monitoring.poll_interval": 2.5
                }
                return config_values.get(key_str, None)

            # Mock the config attribute and its get_nested_value method
            mock_config_obj = Mock()
            mock_config_obj.get_nested_value.side_effect = get_config_value  # pyright: ignore[reportAny]
            mock_config_instance.config = mock_config_obj

            # Create application
            app = Application(config_path="test_config.yaml", debug=False)

            # Test start
            app.start()
            assert app.is_running is True

            # Test run (should create and run monitor session)
            app.run()
            mock_monitor_session.assert_called_once()
            mock_monitor_instance.run_monitoring_loop.assert_called_once()  # pyright: ignore[reportAny]

            # Test stop
            app.stop()
            assert app.is_running is False

    def test_load_provider_plugins(self) -> None:
        """Test loading provider plugins."""
        with patch('mover_status.application.ConfigManager') as mock_config_manager, \
             patch('mover_status.application.setup_logger'), \
             patch('mover_status.application.NotificationManager') as mock_notification_manager, \
             patch('mover_status.application.ProviderRegistry') as mock_provider_registry, \
             patch('mover_status.application.ConfigRegistry') as mock_config_registry:

            # Setup mocks
            mock_config_instance = Mock(spec=ConfigManager)
            mock_config_manager.return_value = mock_config_instance

            mock_notification_instance = Mock(spec=NotificationManager)
            mock_notification_manager.return_value = mock_notification_instance

            mock_provider_registry_instance = Mock(spec=ProviderRegistry)
            mock_provider_registry.return_value = mock_provider_registry_instance

            mock_config_registry_instance = Mock(spec=ConfigRegistry)
            mock_config_registry.return_value = mock_config_registry_instance

            # Mock discovered providers
            mock_provider_class = Mock()
            mock_provider_registry_instance.discover_providers.return_value = {  # pyright: ignore[reportAny]
                "test_provider": mock_provider_class
            }

            # Create application and load plugins
            app = Application(config_path="test_config.yaml", debug=False)
            discovered_providers = app.load_provider_plugins()

            # Verify plugins were discovered
            mock_provider_registry_instance.discover_providers.assert_called_once()  # pyright: ignore[reportAny]
            assert "test_provider" in discovered_providers
            assert discovered_providers["test_provider"] == mock_provider_class

    def test_initialize_plugins_with_configuration(self) -> None:
        """Test initializing plugins with configuration."""
        with patch('mover_status.application.ConfigManager') as mock_config_manager, \
             patch('mover_status.application.setup_logger'), \
             patch('mover_status.application.NotificationManager') as mock_notification_manager, \
             patch('mover_status.application.ProviderRegistry') as mock_provider_registry, \
             patch('mover_status.application.ConfigRegistry') as mock_config_registry:

            # Setup mocks
            mock_config_instance = Mock(spec=ConfigManager)
            mock_config_manager.return_value = mock_config_instance

            mock_notification_instance = Mock(spec=NotificationManager)
            mock_notification_manager.return_value = mock_notification_instance

            mock_provider_registry_instance = Mock(spec=ProviderRegistry)
            mock_provider_registry.return_value = mock_provider_registry_instance

            mock_config_registry_instance = Mock(spec=ConfigRegistry)
            mock_config_registry.return_value = mock_config_registry_instance

            # Mock provider class and instance
            mock_provider_instance = Mock()
            mock_provider_class = Mock(return_value=mock_provider_instance)

            # Mock configuration
            mock_provider_config = {"enabled": True, "test_setting": "value"}

            # Mock the config attribute and its get_nested_value method
            mock_config_obj = Mock()
            mock_config_obj.get_nested_value.return_value = mock_provider_config  # pyright: ignore[reportAny]
            mock_config_instance.config = mock_config_obj

            # Create application and initialize plugin
            app = Application(config_path="test_config.yaml", debug=False)
            provider_instance = app.initialize_plugin_with_configuration("test_provider", mock_provider_class)  # pyright: ignore[reportArgumentType]

            # Verify plugin was initialized with configuration
            mock_provider_class.assert_called_once_with(mock_provider_config)
            assert provider_instance == mock_provider_instance

    def test_plugin_lifecycle_management(self) -> None:
        """Test plugin lifecycle management."""
        with patch('mover_status.application.ConfigManager') as mock_config_manager, \
             patch('mover_status.application.setup_logger'), \
             patch('mover_status.application.NotificationManager') as mock_notification_manager, \
             patch('mover_status.application.ProviderRegistry') as mock_provider_registry, \
             patch('mover_status.application.ConfigRegistry') as mock_config_registry:

            # Setup mocks
            mock_config_instance = Mock(spec=ConfigManager)
            mock_config_manager.return_value = mock_config_instance

            mock_notification_instance = Mock(spec=NotificationManager)
            mock_notification_manager.return_value = mock_notification_instance

            mock_provider_registry_instance = Mock(spec=ProviderRegistry)
            mock_provider_registry.return_value = mock_provider_registry_instance

            mock_config_registry_instance = Mock(spec=ConfigRegistry)
            mock_config_registry.return_value = mock_config_registry_instance

            # Create application
            app = Application(config_path="test_config.yaml", debug=False)

            # Test that application tracks plugin lifecycle
            assert hasattr(app, 'loaded_plugins')
            assert isinstance(app.loaded_plugins, dict)

            # Test plugin registration tracking
            mock_plugin = Mock()
            app.loaded_plugins["test_plugin"] = mock_plugin
            assert "test_plugin" in app.loaded_plugins
            assert app.loaded_plugins["test_plugin"] == mock_plugin
