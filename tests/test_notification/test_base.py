"""
Tests for the abstract notification provider base class.
"""

import pytest
from typing import override

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
