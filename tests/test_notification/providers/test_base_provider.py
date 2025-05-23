"""
Tests for the base notification provider class.

This module contains tests for the BaseProvider class, which provides common
functionality for all notification providers.
"""

from typing import override

# Import the modules to test
from mover_status.notification.base import NotificationProvider
from mover_status.notification.providers.base_provider import BaseProvider
from mover_status.notification.formatter import RawValues


class TestBaseProvider:
    """Tests for the BaseProvider class."""

    def test_base_provider_with_common_functionality(self) -> None:
        """Test that BaseProvider provides common functionality for all providers."""
        # Create a concrete implementation for testing
        class TestProvider(BaseProvider):
            @override
            def _send_notification_impl(
                self,
                message: str,
                raw_values: RawValues,
                **kwargs: object
            ) -> bool:
                return True

            @override
            def validate_config(self) -> list[str]:
                return []

        # Test that BaseProvider can be instantiated with configuration
        config = {"enabled": True, "test_setting": "value"}
        provider = TestProvider("test", config)

        # Verify basic functionality
        assert provider.name == "test"
        assert provider.enabled is True
        assert provider.config == config
        assert provider.is_initialized() is False

    def test_provider_configuration_handling(self) -> None:
        """Test that BaseProvider handles provider configuration properly."""
        # Create a concrete implementation for testing
        class TestProvider(BaseProvider):
            @override
            def _send_notification_impl(
                self,
                message: str,
                raw_values: RawValues,
                **kwargs: object
            ) -> bool:
                return True

            @override
            def validate_config(self) -> list[str]:
                return []

        # Test configuration access
        config = {
            "enabled": True,
            "api_key": "test-key",
            "timeout": 30,
            "optional_setting": None
        }
        provider = TestProvider("test", config)

        # Test _get_config_value method (accessing protected method for testing)
        assert provider._get_config_value("enabled") is True  # pyright: ignore[reportPrivateUsage]
        assert provider._get_config_value("api_key") == "test-key"  # pyright: ignore[reportPrivateUsage]
        assert provider._get_config_value("timeout") == 30  # pyright: ignore[reportPrivateUsage]
        assert provider._get_config_value("optional_setting") is None  # pyright: ignore[reportPrivateUsage]
        assert provider._get_config_value("missing_key", "default") == "default"  # pyright: ignore[reportPrivateUsage]

    def test_provider_lifecycle_methods(self) -> None:
        """Test that BaseProvider implements provider lifecycle methods."""
        # Create a concrete implementation for testing
        class TestProvider(BaseProvider):
            def __init__(self, name: str, config: dict[str, object]) -> None:
                super().__init__(name, config)
                self.init_called: bool = False

            @override
            def _initialize_provider(self) -> bool:
                self.init_called = True
                return True

            @override
            def _send_notification_impl(
                self,
                message: str,
                raw_values: RawValues,
                **kwargs: object
            ) -> bool:
                return True

            @override
            def validate_config(self) -> list[str]:
                return []

        config: dict[str, object] = {"enabled": True}
        provider = TestProvider("test", config)

        # Test initial state
        assert provider.is_initialized() is False
        assert provider.init_called is False

        # Test initialization
        assert provider.initialize() is True
        assert provider.is_initialized() is True
        assert provider.init_called is True

        # Test health check
        assert provider.health_check() is True

    def test_base_provider_inheritance(self) -> None:
        """Test that BaseProvider properly inherits from NotificationProvider."""
        # Create a concrete implementation for testing
        class TestProvider(BaseProvider):
            @override
            def _send_notification_impl(
                self,
                message: str,
                raw_values: RawValues,
                **kwargs: object
            ) -> bool:
                return True

            @override
            def validate_config(self) -> list[str]:
                return []

        config: dict[str, object] = {"enabled": True}
        provider = TestProvider("test", config)

        # Verify inheritance
        assert isinstance(provider, NotificationProvider)
        assert isinstance(provider, BaseProvider)

        # Verify interface compliance
        assert hasattr(provider, "send_notification")
        assert hasattr(provider, "validate_config")
        assert hasattr(provider, "name")
        assert hasattr(provider, "metadata")

    def test_configuration_validation_integration(self) -> None:
        """Test that BaseProvider integrates with the configuration validation system."""
        # Create a provider that validates required fields
        class TestProvider(BaseProvider):
            @override
            def _send_notification_impl(
                self,
                message: str,
                raw_values: RawValues,
                **kwargs: object
            ) -> bool:
                return True

            @override
            def validate_config(self) -> list[str]:
                return self._validate_required_config(["api_key", "endpoint"])

        # Test with missing required fields
        config: dict[str, object] = {"enabled": True}
        provider = TestProvider("test", config)

        errors = provider.validate_config()
        assert len(errors) == 2
        assert "Test api_key is required" in errors
        assert "Test endpoint is required" in errors

        # Test with valid configuration
        valid_config: dict[str, object] = {
            "enabled": True,
            "api_key": "test-key",
            "endpoint": "https://api.example.com"
        }
        valid_provider = TestProvider("test", valid_config)
        assert valid_provider.validate_config() == []

    def test_provider_metadata_handling(self) -> None:
        """Test that BaseProvider handles provider metadata correctly."""
        # Create a concrete implementation for testing
        class TestProvider(BaseProvider):
            @override
            def _send_notification_impl(
                self,
                message: str,
                raw_values: RawValues,
                **kwargs: object
            ) -> bool:
                return True

            @override
            def validate_config(self) -> list[str]:
                return []

        # Test with metadata
        metadata = {"version": "1.0.0", "description": "Test provider"}
        config: dict[str, object] = {"enabled": True}
        provider = TestProvider("test", config, metadata)

        assert provider.metadata == metadata
        assert provider.name == "test"

        # Test without metadata
        provider_no_meta = TestProvider("test", config)
        assert provider_no_meta.metadata is None

    def test_error_handling_and_logging(self) -> None:
        """Test that BaseProvider provides proper error handling and logging."""
        # Create a provider that can fail during initialization
        class TestProvider(BaseProvider):
            def __init__(self, name: str, config: dict[str, object], should_fail: bool = False) -> None:
                super().__init__(name, config)
                self.should_fail: bool = should_fail

            @override
            def _initialize_provider(self) -> bool:
                if self.should_fail:
                    raise RuntimeError("Initialization failed")
                return True

            @override
            def _send_notification_impl(
                self,
                message: str,
                raw_values: RawValues,
                **kwargs: object
            ) -> bool:
                return True

            @override
            def validate_config(self) -> list[str]:
                return []

        # Test error handling during initialization
        config: dict[str, object] = {"enabled": True}
        failing_provider = TestProvider("test", config, should_fail=True)

        # Initialization should fail gracefully
        assert failing_provider.initialize() is False
        assert failing_provider.is_initialized() is False

    def test_raw_values_extraction(self) -> None:
        """Test that BaseProvider correctly extracts raw values."""
        # Create a concrete implementation for testing
        class TestProvider(BaseProvider):
            def __init__(self, name: str, config: dict[str, object]) -> None:
                super().__init__(name, config)
                self.last_raw_values: RawValues = {}

            @override
            def _send_notification_impl(
                self,
                message: str,
                raw_values: RawValues,
                **kwargs: object
            ) -> bool:
                self.last_raw_values = raw_values
                return True

            @override
            def validate_config(self) -> list[str]:
                return []

        config: dict[str, object] = {"enabled": True}
        provider = TestProvider("test", config)

        # Test with valid raw values
        raw_values = {
            "percent": 75.5,
            "remaining_bytes": 1024,
            "eta": 300.0
        }

        result = provider.send_notification("test message", raw_values=raw_values)
        assert result is True

        assert provider.last_raw_values.get("percent") == 75.5
        assert provider.last_raw_values.get("remaining_bytes") == 1024
        assert provider.last_raw_values.get("eta") == 300.0

    def test_enabled_check_functionality(self) -> None:
        """Test that BaseProvider properly handles enabled/disabled state."""
        # Create a concrete implementation for testing
        class TestProvider(BaseProvider):
            @override
            def _send_notification_impl(
                self,
                message: str,
                raw_values: RawValues,
                **kwargs: object
            ) -> bool:
                return True

            @override
            def validate_config(self) -> list[str]:
                return []

        # Test disabled provider
        disabled_config: dict[str, object] = {"enabled": False}
        disabled_provider = TestProvider("test", disabled_config)

        # Should return False when disabled
        assert disabled_provider.send_notification("test") is False
        assert disabled_provider.health_check() is False

        # Test enabled provider
        enabled_config: dict[str, object] = {"enabled": True}
        enabled_provider = TestProvider("test", enabled_config)

        # Should work when enabled
        assert enabled_provider.send_notification("test") is True


class TestBaseProviderIntegration:
    """Integration tests for BaseProvider with other components."""

    def test_integration_with_provider_registry(self) -> None:
        """Test that BaseProvider integrates properly with the provider registry."""
        from mover_status.notification.registry import ProviderRegistry

        # Create a concrete implementation for testing
        class TestProvider(BaseProvider):
            @override
            def _send_notification_impl(
                self,
                message: str,
                raw_values: RawValues,
                **kwargs: object
            ) -> bool:
                return True

            @override
            def validate_config(self) -> list[str]:
                return []

        # Create provider with metadata
        metadata = {"version": "1.0.0", "description": "Test provider"}
        config: dict[str, object] = {"enabled": True}
        provider = TestProvider("test", config, metadata)

        # Test registration with provider registry
        registry = ProviderRegistry()
        registry.register_provider("test", provider)

        registered_providers = registry.get_registered_providers()
        assert "test" in registered_providers
        assert registered_providers["test"] == provider

    def test_integration_with_notification_manager(self) -> None:
        """Test that BaseProvider integrates with the notification manager."""
        from mover_status.notification.manager import NotificationManager

        # Create a concrete implementation for testing
        class TestProvider(BaseProvider):
            def __init__(self, name: str, config: dict[str, object]) -> None:
                super().__init__(name, config)
                self.messages_sent: list[str] = []

            @override
            def _send_notification_impl(
                self,
                message: str,
                raw_values: RawValues,
                **kwargs: object
            ) -> bool:
                self.messages_sent.append(message)
                return True

            @override
            def validate_config(self) -> list[str]:
                return []

        # Create provider and manager
        config: dict[str, object] = {"enabled": True}
        provider = TestProvider("test", config)
        manager = NotificationManager()

        # Register provider with manager
        manager.register_provider(provider)

        # Test sending notification through manager
        result = manager.send_notification("test message")
        assert result is True
        assert "test message" in provider.messages_sent

    def test_configuration_validation_workflow(self) -> None:
        """Test the complete configuration validation workflow."""
        # Create a provider that validates configuration
        class TestProvider(BaseProvider):
            @override
            def _send_notification_impl(
                self,
                message: str,
                raw_values: RawValues,
                **kwargs: object
            ) -> bool:
                return True

            @override
            def validate_config(self) -> list[str]:
                errors: list[str] = []

                # Use the base class validation helper
                required_errors = self._validate_required_config(["api_key"])
                errors.extend(required_errors)

                # Add custom validation
                api_key = self._get_config_value("api_key", "")
                if api_key and isinstance(api_key, str) and len(api_key) < 10:
                    errors.append("API key must be at least 10 characters")

                return errors

        # Test with invalid configuration
        invalid_config: dict[str, object] = {"enabled": True}
        invalid_provider = TestProvider("test", invalid_config)

        # Should fail validation
        assert invalid_provider.send_notification("test") is False

        # Test with valid configuration
        valid_config: dict[str, object] = {
            "enabled": True,
            "api_key": "valid-api-key-123"
        }
        valid_provider = TestProvider("test", valid_config)

        # Should pass validation
        assert valid_provider.send_notification("test") is True
