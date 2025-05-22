"""
Abstract base class for notification providers.

This module defines the interface that all notification providers must implement.
Each provider (e.g., Telegram, Discord) will subclass this abstract base class
and implement the required methods.
"""

from abc import ABC, abstractmethod
from collections.abc import Mapping


class NotificationProvider(ABC):
    """
    Abstract base class for notification providers.

    This class defines the interface that all notification providers must implement.
    Subclasses must implement the send_notification and validate_config methods.

    Attributes:
        name: The name of the notification provider.
        metadata: Optional metadata about the provider (version, description, etc.).
    """

    def __init__(self, name: str, metadata: Mapping[str, object] | None = None) -> None:
        """
        Initialize the notification provider.

        Args:
            name: The name of the notification provider.
            metadata: Optional metadata about the provider.
        """
        self.name: str = name
        self.metadata: Mapping[str, object] | None = metadata

    @abstractmethod
    def send_notification(self, message: str, **kwargs: object) -> bool:
        """
        Send a notification with the given message.

        Args:
            message: The message to send.
            **kwargs: Additional provider-specific arguments.

        Returns:
            True if the notification was sent successfully, False otherwise.
        """
        pass

    @abstractmethod
    def validate_config(self) -> list[str]:
        """
        Validate the provider configuration.

        Returns:
            A list of error messages. An empty list indicates a valid configuration.
        """
        pass
