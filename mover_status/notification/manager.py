"""
Notification manager module.

This module provides the NotificationManager class, which is responsible for
managing notification providers and sending notifications to all registered providers.
"""

import logging
from typing import Any

from mover_status.notification.base import NotificationProvider

# Get logger for this module
logger = logging.getLogger(__name__)


class NotificationManager:
    """
    Notification manager class.

    This class manages notification providers and sends notifications to all
    registered providers. It handles provider errors and ensures that notifications
    are sent to all providers, even if some fail.

    Attributes:
        providers: A list of registered notification providers.
    """

    def __init__(self) -> None:
        """Initialize the notification manager."""
        self.providers: list[NotificationProvider] = []

    def register_provider(self, provider: NotificationProvider) -> None:
        """
        Register a notification provider with the manager.

        Args:
            provider: The notification provider to register.
        """
        logger.debug("Registering notification provider: %s", provider.name)
        self.providers.append(provider)

    def send_notification(self, message: str, **kwargs: Any) -> bool:  # pyright: ignore[reportAny, reportExplicitAny]
        """
        Send a notification to all registered providers.

        This method sends the given message to all registered providers. If any
        provider fails to send the notification, the method will still attempt to
        send the notification to all other providers. The method returns True only
        if all providers successfully send the notification.

        Args:
            message: The message to send.
            **kwargs: Additional arguments to pass to the providers.
                raw_values: Optional raw values to format the message with.

        Returns:
            True if all providers successfully sent the notification, False otherwise.
            If no providers are registered, returns True.
        """
        if not self.providers:
            logger.warning("No notification providers registered")
            return True

        all_succeeded = True

        for provider in self.providers:
            try:
                logger.debug("Sending notification to provider: %s", provider.name)
                success = provider.send_notification(message, **kwargs)  # pyright: ignore[reportAny]
                if not success:
                    logger.warning("Provider %s failed to send notification", provider.name)
                    all_succeeded = False
            except Exception as e:
                logger.error("Error sending notification to provider %s: %s", provider.name, e)
                all_succeeded = False

        return all_succeeded
