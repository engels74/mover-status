"""Abstract base class for notification providers."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from functools import wraps
from typing import TYPE_CHECKING, TypeVar, cast
from collections.abc import Mapping

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from mover_status.notifications.models.message import Message


F = TypeVar("F", bound="Callable[..., Awaitable[object]]")


class NotificationProvider(ABC):
    """Abstract base class for all notification providers."""
    
    def __init__(self, config: Mapping[str, object]) -> None:
        """Initialize the provider with configuration.
        
        Args:
            config: Provider configuration dictionary
        """
        self.config: Mapping[str, object] = config
        self.enabled: bool = bool(config.get("enabled", True))
    
    @abstractmethod
    async def send_notification(self, message: Message) -> bool:
        """Send a notification message.
        
        Args:
            message: The notification message to send
            
        Returns:
            True if the notification was sent successfully, False otherwise
        """
        ...
    
    @abstractmethod
    def validate_config(self) -> None:
        """Validate the provider configuration.
        
        Raises:
            ValueError: If the configuration is invalid
        """
        ...
    
    @abstractmethod
    def get_provider_name(self) -> str:
        """Get the name of this provider.
        
        Returns:
            The provider name
        """
        ...
    
    def is_enabled(self) -> bool:
        """Check if the provider is enabled.
        
        Returns:
            True if the provider is enabled, False otherwise
        """
        return self.enabled


def with_retry(
    max_attempts: int = 3,
    backoff_factor: float = 2.0
) -> Callable[[F], F]:
    """Decorator that adds retry logic with exponential backoff.
    
    Args:
        max_attempts: Maximum number of retry attempts
        backoff_factor: Multiplier for exponential backoff
        
    Returns:
        Decorated function with retry logic
    """
    def decorator(func: F) -> F:
        @wraps(func)
        async def wrapper(*args: object, **kwargs: object) -> object:
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)  # type: ignore[misc]
                except Exception:
                    if attempt == max_attempts - 1:
                        raise
                    wait_time = backoff_factor ** attempt
                    await asyncio.sleep(wait_time)
            return None
        return cast(F, wrapper)
    return decorator