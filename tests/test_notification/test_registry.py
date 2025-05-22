"""
Tests for the notification provider registry.

This module contains tests for the ProviderRegistry class that manages
provider registration and discovery.
"""

import pytest
from typing import override
from unittest.mock import Mock, patch

# Import the module to test
from mover_status.notification.base import NotificationProvider


class TestProviderRegistry:
    """Tests for the ProviderRegistry class."""

    def test_register_provider(self) -> None:
        """Test registering a provider with the registry."""
        # This test will fail until we implement the ProviderRegistry
        from mover_status.notification.registry import ProviderRegistry

        # Create a mock provider
        mock_provider = Mock(spec=NotificationProvider)
        mock_provider.name = "test_provider"
        mock_provider.metadata = {"version": "1.0.0", "description": "Test provider"}

        # Create registry and register provider
        registry = ProviderRegistry()
        registry.register_provider("test_provider", mock_provider)

        # Verify provider was registered
        registered_providers = registry.get_registered_providers()
        assert "test_provider" in registered_providers
        assert registered_providers["test_provider"] is mock_provider

    def test_get_registered_providers(self) -> None:
        """Test getting all registered providers."""
        from mover_status.notification.registry import ProviderRegistry

        # Create registry
        registry = ProviderRegistry()

        # Initially should be empty
        providers = registry.get_registered_providers()
        assert isinstance(providers, dict)
        assert len(providers) == 0

        # Register a provider
        mock_provider = Mock(spec=NotificationProvider)
        mock_provider.name = "test_provider"
        mock_provider.metadata = {"version": "1.0.0"}
        registry.register_provider("test_provider", mock_provider)

        # Should now contain the provider
        providers = registry.get_registered_providers()
        assert len(providers) == 1
        assert "test_provider" in providers

    def test_provider_uniqueness_prevent_duplicates(self) -> None:
        """Test that duplicate provider registration is prevented."""
        from mover_status.notification.registry import ProviderRegistry

        # Create registry and mock provider
        registry = ProviderRegistry()
        mock_provider1 = Mock(spec=NotificationProvider)
        mock_provider1.name = "test_provider"
        mock_provider1.metadata = {"version": "1.0.0"}

        mock_provider2 = Mock(spec=NotificationProvider)
        mock_provider2.name = "test_provider"
        mock_provider2.metadata = {"version": "2.0.0"}

        # Register first provider
        registry.register_provider("test_provider", mock_provider1)

        # Attempting to register duplicate should raise an error
        with pytest.raises(ValueError, match="Provider 'test_provider' is already registered"):
            registry.register_provider("test_provider", mock_provider2)

        # Verify only the first provider is registered
        providers = registry.get_registered_providers()
        assert len(providers) == 1
        assert providers["test_provider"] is mock_provider1

    def test_provider_metadata_validation(self) -> None:
        """Test that provider metadata is validated during registration."""
        from mover_status.notification.registry import ProviderRegistry

        registry = ProviderRegistry()

        # Test provider without metadata
        mock_provider_no_metadata = Mock(spec=NotificationProvider)
        mock_provider_no_metadata.name = "test_provider"
        mock_provider_no_metadata.metadata = None

        with pytest.raises(ValueError, match="Provider metadata is required"):
            registry.register_provider("test_provider", mock_provider_no_metadata)

        # Test provider with valid metadata - this should work since
        # the type system ensures metadata is Mapping[str, object] | None
        mock_provider_valid_metadata = Mock(spec=NotificationProvider)
        mock_provider_valid_metadata.name = "test_provider_2"
        mock_provider_valid_metadata.metadata = {"version": "1.0.0"}  # Valid metadata

        # This should not raise an error since metadata is valid
        registry.register_provider("test_provider_2", mock_provider_valid_metadata)

        # Test provider with valid metadata
        mock_provider_valid = Mock(spec=NotificationProvider)
        mock_provider_valid.name = "test_provider_3"
        mock_provider_valid.metadata = {"version": "1.0.0", "description": "Test provider"}

        # This should not raise an error
        registry.register_provider("test_provider_3", mock_provider_valid)

        providers = registry.get_registered_providers()
        assert "test_provider_3" in providers

    def test_discover_providers_from_entry_points(self) -> None:
        """Test discovering providers from entry points."""
        from mover_status.notification.registry import ProviderRegistry

        # Create a mock provider class
        class MockProviderClass(NotificationProvider):
            @override
            def send_notification(self, message: str, **kwargs: object) -> bool:
                return True

            @override
            def validate_config(self) -> list[str]:
                return []

        # Mock entry points
        mock_entry_point = Mock()
        mock_entry_point.name = "test_provider"
        mock_entry_point.load.return_value = MockProviderClass  # pyright: ignore[reportAny]

        with patch('importlib.metadata.entry_points') as mock_entry_points:
            mock_entry_points.return_value = [mock_entry_point]

            registry = ProviderRegistry()
            discovered_providers = registry.discover_providers()

            assert len(discovered_providers) == 1
            assert "test_provider" in discovered_providers
            assert discovered_providers["test_provider"] is MockProviderClass

    def test_handle_missing_or_invalid_providers(self) -> None:
        """Test handling of missing or invalid providers during discovery."""
        from mover_status.notification.registry import ProviderRegistry

        # Mock entry point that fails to load
        mock_entry_point_fail = Mock()
        mock_entry_point_fail.name = "failing_provider"
        mock_entry_point_fail.load.side_effect = ImportError("Module not found")  # pyright: ignore[reportAny]

        # Mock entry point that loads invalid provider
        mock_entry_point_invalid = Mock()
        mock_entry_point_invalid.name = "invalid_provider"
        mock_entry_point_invalid.load.return_value = "not_a_provider"  # pyright: ignore[reportAny]

        with patch('importlib.metadata.entry_points') as mock_entry_points:
            mock_entry_points.return_value = [mock_entry_point_fail, mock_entry_point_invalid]

            registry = ProviderRegistry()
            discovered_providers = registry.discover_providers()

            # Should handle errors gracefully and return empty dict
            assert len(discovered_providers) == 0

    def test_load_provider_modules_dynamically(self) -> None:
        """Test loading provider modules dynamically."""
        from mover_status.notification.registry import ProviderRegistry

        registry = ProviderRegistry()

        # Mock a provider module
        mock_provider_class = Mock(spec=NotificationProvider)
        mock_provider_class.name = "dynamic_provider"
        mock_provider_class.metadata = {"version": "1.0.0"}

        with patch('importlib.import_module') as mock_import:
            mock_module = Mock()
            mock_module.get_provider_class.return_value = mock_provider_class  # pyright: ignore[reportAny]
            mock_import.return_value = mock_module

            provider = registry.load_provider_module("test.module")

            assert provider is mock_provider_class
            mock_import.assert_called_once_with("test.module")
