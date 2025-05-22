"""
Tests for the abstract notification provider base class.
"""

import pytest
from typing import override
from collections.abc import Mapping

# Import the module to test
from mover_status.notification.base import NotificationProvider


class TestNotificationProvider:
    """Tests for the NotificationProvider abstract base class."""

    def test_cannot_instantiate_abstract_class(self) -> None:
        """Test that NotificationProvider cannot be instantiated directly."""
        # Attempting to instantiate an abstract class should raise TypeError
        with pytest.raises(TypeError):
            # We expect this to fail since it's an abstract class
            # The type ignore is needed because mypy would catch this at compile time
            _ = NotificationProvider("test_provider")  # type: ignore

    def test_required_methods_defined(self) -> None:
        """Test that required methods are defined in the abstract class."""
        # Check that the class has the required abstract methods
        assert hasattr(NotificationProvider, "send_notification")
        assert hasattr(NotificationProvider, "validate_config")

        # Check that the methods are marked as abstract
        assert getattr(NotificationProvider.send_notification, "__isabstractmethod__", False)
        assert getattr(NotificationProvider.validate_config, "__isabstractmethod__", False)

    def test_concrete_implementation(self) -> None:
        """Test that a concrete implementation can be instantiated."""
        # Create a concrete implementation of the abstract class
        class ConcreteProvider(NotificationProvider):
            @override
            def send_notification(self, message: str, **kwargs: object) -> bool:
                """
                Send a notification with the given message.

                Override the abstract method from the parent class.
                """
                return True

            @override
            def validate_config(self) -> list[str]:
                """
                Validate the provider configuration.

                Override the abstract method from the parent class.
                """
                return []

        # Instantiate the concrete implementation
        provider = ConcreteProvider("test_provider")

        # Check that the provider has the expected attributes
        assert provider.name == "test_provider"

        # Check that the methods work as expected
        assert provider.send_notification("Test message") is True
        assert provider.validate_config() == []

    def test_provider_with_metadata(self) -> None:
        """Test that a provider can be created with metadata."""
        # Create a concrete implementation with metadata
        class ConcreteProviderWithMetadata(NotificationProvider):
            def __init__(self, name: str, metadata: Mapping[str, object] | None = None) -> None:
                super().__init__(name, metadata)

            @override
            def send_notification(self, message: str, **kwargs: object) -> bool:
                return True

            @override
            def validate_config(self) -> list[str]:
                return []

        # Test with metadata
        metadata = {"version": "1.0.0", "description": "Test provider"}
        provider = ConcreteProviderWithMetadata("test_provider", metadata)

        assert provider.name == "test_provider"
        assert provider.metadata == metadata

    def test_provider_metadata_validation(self) -> None:
        """Test that provider metadata is validated."""
        # Create a concrete implementation
        class ConcreteProvider(NotificationProvider):
            def __init__(self, name: str, metadata: Mapping[str, object] | None = None) -> None:
                super().__init__(name, metadata)

            @override
            def send_notification(self, message: str, **kwargs: object) -> bool:
                return True

            @override
            def validate_config(self) -> list[str]:
                return []

        # Test with valid metadata
        valid_metadata = {"version": "1.0.0", "description": "Test provider"}
        provider = ConcreteProvider("test_provider", valid_metadata)
        assert provider.metadata == valid_metadata

        # Test with None metadata (should be allowed)
        provider_no_metadata = ConcreteProvider("test_provider", None)
        assert provider_no_metadata.metadata is None

    def test_default_metadata_values(self) -> None:
        """Test that default metadata values are handled correctly."""
        # Create a concrete implementation
        class ConcreteProvider(NotificationProvider):
            def __init__(self, name: str, metadata: Mapping[str, object] | None = None) -> None:
                super().__init__(name, metadata)

            @override
            def send_notification(self, message: str, **kwargs: object) -> bool:
                return True

            @override
            def validate_config(self) -> list[str]:
                return []

        # Test with no metadata provided (should default to None)
        provider = ConcreteProvider("test_provider")
        assert provider.metadata is None

    def test_provider_self_registration_with_registry(self) -> None:
        """Test that a provider can self-register with a registry."""
        from mover_status.notification.registry import ProviderRegistry

        # Create a registry
        registry = ProviderRegistry()

        # Create a concrete provider that can self-register
        class SelfRegisteringProvider(NotificationProvider):
            def __init__(self, name: str, metadata: Mapping[str, object] | None = None) -> None:
                super().__init__(name, metadata)

            @override
            def send_notification(self, message: str, **kwargs: object) -> bool:
                return True

            @override
            def validate_config(self) -> list[str]:
                return []

            def register_with(self, registry: ProviderRegistry) -> None:
                """Register this provider with the given registry."""
                registry.register_provider(self.name, self)

        # Create provider with metadata
        metadata = {"version": "1.0.0", "description": "Self-registering provider"}
        provider = SelfRegisteringProvider("self_registering_provider", metadata)

        # Provider should be able to register itself
        provider.register_with(registry)

        # Verify provider was registered
        registered_providers = registry.get_registered_providers()
        assert "self_registering_provider" in registered_providers
        assert registered_providers["self_registering_provider"] is provider

    def test_provider_factory_pattern(self) -> None:
        """Test provider factory pattern for creating providers."""
        # Create a factory function
        def create_test_provider(name: str, config: Mapping[str, object]) -> NotificationProvider:
            class FactoryProvider(NotificationProvider):
                def __init__(self, name: str, config: Mapping[str, object]) -> None:
                    metadata = {"version": "1.0.0", "config": dict(config)}
                    super().__init__(name, metadata)
                    self.config: Mapping[str, object] = config

                @override
                def send_notification(self, message: str, **kwargs: object) -> bool:
                    return True

                @override
                def validate_config(self) -> list[str]:
                    return []

            return FactoryProvider(name, config)

        # Use factory to create provider
        config: Mapping[str, object] = {"enabled": True, "test_setting": "value"}
        provider = create_test_provider("factory_provider", config)

        # Verify provider was created correctly
        assert provider.name == "factory_provider"
        assert provider.metadata is not None
        assert provider.metadata["version"] == "1.0.0"
        assert provider.metadata["config"] == config

    def test_provider_initialization_with_configuration(self) -> None:
        """Test provider initialization with configuration."""
        # Create a configurable provider
        class ConfigurableProvider(NotificationProvider):
            def __init__(self, name: str, config: Mapping[str, object]) -> None:
                metadata = {
                    "version": "1.0.0",
                    "description": "Configurable provider",
                    "config_schema": {
                        "enabled": bool,
                        "api_key": str,
                        "timeout": int
                    }
                }
                super().__init__(name, metadata)
                enabled_value = config.get("enabled", False)
                api_key_value = config.get("api_key", "")
                timeout_value = config.get("timeout", 30)

                self.enabled: bool = bool(enabled_value)
                self.api_key: str = str(api_key_value)
                self.timeout: int = int(timeout_value) if isinstance(timeout_value, (int, str)) else 30

            @override
            def send_notification(self, message: str, **kwargs: object) -> bool:
                if not self.enabled:
                    return False
                # Simulate sending notification
                return bool(self.api_key)

            @override
            def validate_config(self) -> list[str]:
                errors: list[str] = []
                if not self.api_key:
                    errors.append("API key is required")
                if self.timeout <= 0:
                    errors.append("Timeout must be positive")
                return errors

        # Test with valid configuration
        valid_config: Mapping[str, object] = {
            "enabled": True,
            "api_key": "test_key_123",
            "timeout": 60
        }
        provider = ConfigurableProvider("configurable_provider", valid_config)

        assert provider.name == "configurable_provider"
        assert provider.enabled is True
        assert provider.api_key == "test_key_123"
        assert provider.timeout == 60
        assert provider.send_notification("test") is True
        assert provider.validate_config() == []

        # Test with invalid configuration
        invalid_config: Mapping[str, object] = {
            "enabled": True,
            "api_key": "",  # Missing API key
            "timeout": -5   # Invalid timeout
        }
        invalid_provider = ConfigurableProvider("invalid_provider", invalid_config)

        assert invalid_provider.send_notification("test") is False
        errors = invalid_provider.validate_config()
        assert "API key is required" in errors
        assert "Timeout must be positive" in errors
