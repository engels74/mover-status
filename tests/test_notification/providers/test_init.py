"""
Tests for the notification providers package discovery.

This module contains tests for the provider package discovery functionality
in the providers/__init__.py module.
"""

from typing import override
from unittest.mock import Mock, patch

from mover_status.notification.base import NotificationProvider
from mover_status.notification.registry import ProviderRegistry


class TestProviderPackageDiscovery:
    """Tests for provider package discovery functionality."""

    def test_discover_provider_packages(self) -> None:
        """Test discovering provider packages from the providers directory."""
        # This test will fail until we implement the discovery functionality
        from mover_status.notification.providers import discover_provider_packages

        # Mock the file system to simulate provider packages
        with patch('os.listdir') as mock_listdir, \
             patch('os.path.isdir') as mock_isdir, \
             patch('os.path.exists') as mock_exists:

            # Simulate provider directories
            mock_listdir.return_value = ['telegram', 'discord', '__pycache__', 'template']

            def mock_isdir_func(path: object) -> bool:
                return not str(path).endswith('__pycache__')

            mock_isdir.side_effect = mock_isdir_func
            mock_exists.return_value = True  # All directories have __init__.py

            discovered_packages = discover_provider_packages()

            assert isinstance(discovered_packages, list)
            assert 'telegram' in discovered_packages
            assert 'discord' in discovered_packages
            assert 'template' in discovered_packages
            assert '__pycache__' not in discovered_packages

    def test_register_discovered_providers(self) -> None:
        """Test registering discovered providers with the registry."""
        from mover_status.notification.providers import register_discovered_providers

        # Create a mock registry
        registry = ProviderRegistry()

        # Create mock provider classes
        class MockTelegramProvider(NotificationProvider):
            def __init__(self) -> None:
                super().__init__("telegram", {"version": "1.0.0", "description": "Telegram provider"})

            @override
            def send_notification(self, message: str, **kwargs: object) -> bool:
                return True

            @override
            def validate_config(self) -> list[str]:
                return []

        class MockDiscordProvider(NotificationProvider):
            def __init__(self) -> None:
                super().__init__("discord", {"version": "1.0.0", "description": "Discord provider"})

            @override
            def send_notification(self, message: str, **kwargs: object) -> bool:
                return True

            @override
            def validate_config(self) -> list[str]:
                return []

        # Mock the provider loading
        provider_classes = {
            'telegram': MockTelegramProvider,
            'discord': MockDiscordProvider
        }

        with patch('mover_status.notification.providers.load_provider_class') as mock_load:
            def mock_load_func(name: str) -> type[NotificationProvider] | None:
                return provider_classes.get(name)

            mock_load.side_effect = mock_load_func

            # Register providers
            registered_count = register_discovered_providers(registry, ['telegram', 'discord'])

            assert registered_count == 2

            # Verify providers were registered
            registered_providers = registry.get_registered_providers()
            assert len(registered_providers) == 2
            assert 'telegram' in registered_providers
            assert 'discord' in registered_providers

    def test_handle_missing_or_invalid_provider_packages(self) -> None:
        """Test handling of missing or invalid provider packages."""
        from mover_status.notification.providers import load_provider_class

        # Test loading a non-existent provider
        with patch('importlib.import_module') as mock_import:
            mock_import.side_effect = ImportError("No module named 'nonexistent'")

            provider_class = load_provider_class('nonexistent')
            assert provider_class is None

        # Test loading a provider without the required get_provider_class function
        with patch('importlib.import_module') as mock_import:
            mock_module = Mock()
            del mock_module.get_provider_class  # Remove the required function
            mock_import.return_value = mock_module

            provider_class = load_provider_class('invalid_provider')
            assert provider_class is None

        # Test loading a provider that returns an invalid class
        with patch('importlib.import_module') as mock_import:
            mock_module = Mock()
            mock_module.get_provider_class = Mock(return_value="not_a_class")
            mock_import.return_value = mock_module

            provider_class = load_provider_class('invalid_class_provider')
            assert provider_class is None

    def test_load_provider_class_success(self) -> None:
        """Test successfully loading a provider class."""
        from mover_status.notification.providers import load_provider_class

        # Create a mock provider class
        class MockProvider(NotificationProvider):
            def __init__(self) -> None:
                super().__init__("mock", {"version": "1.0.0"})

            @override
            def send_notification(self, message: str, **kwargs: object) -> bool:
                return True

            @override
            def validate_config(self) -> list[str]:
                return []

        # Mock the module loading
        with patch('importlib.import_module') as mock_import:
            mock_module = Mock()
            mock_module.get_provider_class = Mock(return_value=MockProvider)
            mock_import.return_value = mock_module

            provider_class = load_provider_class('mock_provider')

            assert provider_class is MockProvider
            mock_import.assert_called_once_with('mover_status.notification.providers.mock_provider')

    def test_auto_discovery_and_registration(self) -> None:
        """Test automatic discovery and registration of all providers."""
        from mover_status.notification.providers import auto_discover_and_register

        # Create a registry
        registry = ProviderRegistry()

        # Mock the discovery and loading process
        with patch('mover_status.notification.providers.discover_provider_packages') as mock_discover, \
             patch('mover_status.notification.providers.register_discovered_providers') as mock_register:

            mock_discover.return_value = ['telegram', 'discord']
            mock_register.return_value = 2

            # Perform auto-discovery
            registered_count = auto_discover_and_register(registry)

            assert registered_count == 2
            mock_discover.assert_called_once()
            mock_register.assert_called_once_with(registry, ['telegram', 'discord'])

    def test_provider_package_validation(self) -> None:
        """Test validation of provider packages."""
        from mover_status.notification.providers import validate_provider_package

        # Test valid provider package
        with patch('os.path.exists') as mock_exists:
            def mock_exists_valid(path: object) -> bool:
                path_str = str(path)
                return path_str.endswith('__init__.py') or path_str.endswith('provider.py')

            mock_exists.side_effect = mock_exists_valid

            is_valid = validate_provider_package('telegram')
            assert is_valid is True

        # Test invalid provider package (missing __init__.py)
        with patch('os.path.exists') as mock_exists:
            def mock_exists_no_init(path: object) -> bool:
                return str(path).endswith('provider.py')  # Only provider.py exists

            mock_exists.side_effect = mock_exists_no_init

            is_valid = validate_provider_package('invalid_provider')
            assert is_valid is False

        # Test invalid provider package (missing provider.py)
        with patch('os.path.exists') as mock_exists:
            def mock_exists_no_provider(path: object) -> bool:
                return str(path).endswith('__init__.py')  # Only __init__.py exists

            mock_exists.side_effect = mock_exists_no_provider

            is_valid = validate_provider_package('incomplete_provider')
            assert is_valid is False
