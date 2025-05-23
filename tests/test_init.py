"""
Tests for the mover_status package initialization and public API.

This module tests the package's public API to ensure it provides a clean interface
without hardcoded provider imports and maintains backward compatibility.
"""

import mover_status


class TestPublicAPI:
    """Test the public API exposed by the mover_status package."""

    def test_import_and_use_public_api(self) -> None:
        """Test that the public API can be imported and used."""
        # Test that core components are available
        assert hasattr(mover_status, 'Application')
        assert hasattr(mover_status, 'ConfigManager')
        assert hasattr(mover_status, 'MonitorSession')
        assert hasattr(mover_status, 'NotificationManager')

        # Test that utility functions are available
        assert hasattr(mover_status, 'setup_logger')
        assert hasattr(mover_status, 'LoggerConfig')
        assert hasattr(mover_status, 'LogLevel')
        assert hasattr(mover_status, 'LogFormat')

        # Test that version is available
        assert hasattr(mover_status, '__version__')
        assert isinstance(mover_status.__version__, str)

    def test_no_hardcoded_provider_imports(self) -> None:
        """Test that specific provider classes are not directly imported in __init__.py."""
        # These should NOT be available in the public API
        assert not hasattr(mover_status, 'TelegramProvider')
        assert not hasattr(mover_status, 'DiscordProvider')

        # Providers should be discovered through the registry system
        # This test ensures we don't have hardcoded provider imports

    def test_backward_compatibility(self) -> None:
        """Test that the public API maintains backward compatibility."""
        # Test that essential components are still available
        # These were in the original __init__.py and should remain for compatibility

        # Core functionality
        assert hasattr(mover_status, 'ConfigManager')
        assert hasattr(mover_status, 'MonitorSession')
        assert hasattr(mover_status, 'NotificationManager')

        # Utility functions
        assert hasattr(mover_status, 'setup_logger')

        # Test that these can be imported
        from mover_status import ConfigManager, MonitorSession, NotificationManager, setup_logger

        # Basic smoke test - ensure they are callable/instantiable
        assert callable(ConfigManager)
        assert callable(MonitorSession)
        assert callable(NotificationManager)
        assert callable(setup_logger)

    def test_application_class_available(self) -> None:
        """Test that the new Application class is available in the public API."""
        assert hasattr(mover_status, 'Application')

        # Test that it can be imported
        from mover_status import Application

        # Test that it's callable
        assert callable(Application)

    def test_provider_registry_available(self) -> None:
        """Test that provider registry functionality is available."""
        assert hasattr(mover_status, 'ProviderRegistry')

        # Test that it can be imported
        from mover_status import ProviderRegistry

        # Test that it's callable
        assert callable(ProviderRegistry)

    def test_config_registry_available(self) -> None:
        """Test that configuration registry functionality is available."""
        assert hasattr(mover_status, 'ConfigRegistry')

        # Test that it can be imported
        from mover_status import ConfigRegistry

        # Test that it's callable
        assert callable(ConfigRegistry)

    def test_all_exports_defined(self) -> None:
        """Test that __all__ is properly defined and contains expected exports."""
        assert hasattr(mover_status, '__all__')
        assert isinstance(mover_status.__all__, list)

        # Test that all items in __all__ are actually available
        for item in mover_status.__all__:
            assert hasattr(mover_status, item), f"Item '{item}' in __all__ is not available"

    def test_clean_api_structure(self) -> None:
        """Test that the API structure is clean and well-organized."""
        # Test that we don't export internal modules
        internal_modules = [
            'config_manager',  # Should use ConfigManager class instead
            'monitor',         # Should use MonitorSession class instead
            'base',           # Internal notification base class
            'registry',       # Internal registry modules
        ]

        for module in internal_modules:
            assert not hasattr(mover_status, module), f"Internal module '{module}' should not be exported"

    def test_application_integration(self) -> None:
        """Test that the Application class can be used through the public API."""
        from mover_status import Application

        # Test that we can create an instance (this tests the real functionality)
        app = Application()

        # Verify it's the correct type
        assert isinstance(app, Application)

        # Test that it has the expected attributes
        assert hasattr(app, 'config_manager')
        assert hasattr(app, 'notification_manager')
        assert hasattr(app, 'provider_registry')
        assert hasattr(app, 'config_registry')

    def test_provider_discovery_through_api(self) -> None:
        """Test that provider discovery works through the public API."""
        from mover_status import ProviderRegistry

        # Create a registry instance
        registry = ProviderRegistry()

        # Test that discovery methods are available
        assert hasattr(registry, 'discover_providers')
        assert hasattr(registry, 'get_registered_providers')
        assert callable(registry.discover_providers)
        assert callable(registry.get_registered_providers)
