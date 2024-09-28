# notifiers/base.py
from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseNotifier(ABC):
    """
    Abstract base class for notifiers.
    All concrete notifier implementations should inherit from this class.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the notifier with configuration.

        :param config: Dictionary containing notifier-specific configuration
        """
        self.config = config

    @abstractmethod
    async def send_notification(self, percent: int, remaining_data: str, etc: str) -> bool:
        """
        Send a notification with the current status.

        :param percent: Current completion percentage
        :param remaining_data: Remaining data in human-readable format
        :param etc: Estimated time of completion
        :return: True if notification was sent successfully, False otherwise
        """
        pass

    @abstractmethod
    async def send_completion_notification(self) -> bool:
        """
        Send a notification indicating that the moving process is complete.

        :return: True if notification was sent successfully, False otherwise
        """
        pass

    @abstractmethod
    async def send_error_notification(self, error_message: str) -> bool:
        """
        Send a notification about an error that occurred during the moving process.

        :param error_message: Description of the error that occurred
        :return: True if notification was sent successfully, False otherwise
        """
        pass

    @classmethod
    @abstractmethod
    def from_config(cls, config: Dict[str, Any]) -> 'BaseNotifier':
        """
        Create a notifier instance from a configuration dictionary.

        :param config: Dictionary containing notifier configuration
        :return: An instance of the notifier
        """
        pass
