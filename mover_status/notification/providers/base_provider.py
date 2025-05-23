"""
Base provider class for notification providers.

This module provides the BaseProvider class, which implements common functionality
for all notification providers. It extends the NotificationProvider abstract base
class and provides standardized configuration handling, validation, and lifecycle
management.
"""

import logging
from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any, TypeVar, overload, override

from mover_status.notification.base import NotificationProvider
from mover_status.notification.formatter import RawValues

# Type variable for configuration value types
T = TypeVar('T')

# Get logger for this module
logger = logging.getLogger(__name__)


class BaseProvider(NotificationProvider, ABC):
    """
    Base provider class with common functionality.

    This class provides common functionality for all notification providers,
    including configuration handling, validation, lifecycle management, and
    error handling. It extends the NotificationProvider abstract base class.

    Attributes:
        name: The name of the notification provider.
        metadata: Optional metadata about the provider.
        config: The provider configuration.
        enabled: Whether the provider is enabled.
        _initialized: Whether the provider has been initialized.
        _logger: Provider-specific logger instance.
    """

    def __init__(
        self,
        name: str,
        config: Mapping[str, Any],  # pyright: ignore[reportExplicitAny]
        metadata: Mapping[str, object] | None = None
    ) -> None:
        """
        Initialize the base provider.

        Args:
            name: The name of the notification provider.
            config: The provider configuration.
            metadata: Optional metadata about the provider.
        """
        # Initialize the parent class
        super().__init__(name, metadata)

        # Store configuration
        self.config: Mapping[str, Any] = config  # pyright: ignore[reportExplicitAny]

        # Extract common configuration values
        self.enabled: bool = bool(self._get_config_value("enabled", False))

        # Initialize state
        self._initialized: bool = False

        # Create provider-specific logger
        self._logger: logging.Logger = logging.getLogger(f"{__name__}.{name}")

        # Log initialization
        self._logger.debug("Initializing %s provider", name)

    @overload
    def _get_config_value(self, key: str) -> object:
        ...

    @overload
    def _get_config_value(self, key: str, default: T) -> object | T:
        ...

    def _get_config_value(self, key: str, default: object = None) -> object:
        """
        Get a configuration value with optional default.

        Args:
            key: The configuration key to retrieve.
            default: The default value if the key is not found.

        Returns:
            The configuration value or the default.
        """
        if hasattr(self.config, 'get'):
            # Handle dict-like objects
            return self.config.get(key, default)  # type: ignore[attr-defined]
        elif hasattr(self.config, '__getitem__'):
            # Handle mapping objects
            try:
                return self.config[key]  # type: ignore[index] # pyright: ignore[reportAny]
            except KeyError:
                return default
        else:
            # Fallback for other types
            return getattr(self.config, key, default)

    def _validate_required_config(self, required_fields: list[str]) -> list[str]:
        """
        Validate that required configuration fields are present.

        Args:
            required_fields: List of required configuration field names.

        Returns:
            List of error messages for missing required fields.
        """
        errors: list[str] = []

        for field in required_fields:
            value = self._get_config_value(field)
            if not value:
                errors.append(f"{self.name.title()} {field} is required")

        return errors

    def _log_config_errors(self, errors: list[str]) -> None:
        """
        Log configuration validation errors.

        Args:
            errors: List of configuration error messages.
        """
        if errors:
            self._logger.error("Invalid %s configuration: %s", self.name, ", ".join(errors))

    def _check_enabled(self) -> bool:
        """
        Check if the provider is enabled.

        Returns:
            True if the provider is enabled, False otherwise.
        """
        if not self.enabled:
            self._logger.info("%s notifications are disabled", self.name.title())
            return False
        return True

    def _extract_raw_values(self, kwargs: dict[str, object]) -> RawValues:
        """
        Extract and validate raw values from kwargs.

        Args:
            kwargs: Keyword arguments that may contain raw_values.

        Returns:
            Extracted and validated raw values.
        """
        raw_values: RawValues = {}

        if "raw_values" not in kwargs:
            return raw_values

        raw_dict = kwargs["raw_values"]
        if not isinstance(raw_dict, dict):
            self._logger.debug("raw_values is not a dictionary, ignoring")
            return raw_values

        # Use a sentinel value to distinguish between missing keys and None values
        sentinel = object()

        # Extract and validate percent value
        try:
            percent_val = raw_dict.get("percent", sentinel)  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
            if percent_val is not sentinel and isinstance(percent_val, (int, float)):
                raw_values["percent"] = percent_val
        except (KeyError, TypeError, AttributeError):
            self._logger.debug("Error extracting percent value from raw_values")

        # Extract and validate remaining_bytes value
        try:
            bytes_val = raw_dict.get("remaining_bytes", sentinel)  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
            if bytes_val is not sentinel and isinstance(bytes_val, int):
                raw_values["remaining_bytes"] = bytes_val
        except (KeyError, TypeError, AttributeError):
            self._logger.debug("Error extracting remaining_bytes value from raw_values")

        # Extract and validate eta value
        try:
            eta_val = raw_dict.get("eta", sentinel)  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
            if eta_val is not sentinel and (eta_val is None or isinstance(eta_val, float)):
                raw_values["eta"] = eta_val
        except (KeyError, TypeError, AttributeError):
            self._logger.debug("Error extracting eta value from raw_values")

        return raw_values

    def initialize(self) -> bool:
        """
        Initialize the provider.

        This method performs provider initialization, including configuration
        validation and any setup required before sending notifications.

        Returns:
            True if initialization was successful, False otherwise.
        """
        if self._initialized:
            self._logger.debug("%s provider already initialized", self.name.title())
            return True

        self._logger.debug("Initializing %s provider", self.name.title())

        # Validate configuration
        errors = self.validate_config()
        if errors:
            self._log_config_errors(errors)
            return False

        # Perform provider-specific initialization
        try:
            if self._initialize_provider():
                self._initialized = True
                self._logger.info("%s provider initialized successfully", self.name.title())
                return True
            else:
                self._logger.error("Failed to initialize %s provider", self.name.title())
                return False
        except Exception as e:
            self._logger.error("Error initializing %s provider: %s", self.name.title(), e)
            return False

    def _initialize_provider(self) -> bool:
        """
        Provider-specific initialization logic.

        Subclasses can override this method to implement provider-specific
        initialization logic. The default implementation returns True.

        Returns:
            True if provider-specific initialization was successful, False otherwise.
        """
        return True

    def is_initialized(self) -> bool:
        """
        Check if the provider has been initialized.

        Returns:
            True if the provider is initialized, False otherwise.
        """
        return self._initialized

    def health_check(self) -> bool:
        """
        Perform a health check on the provider.

        This method can be used to verify that the provider is functioning
        correctly. The default implementation checks if the provider is
        initialized and enabled.

        Returns:
            True if the provider is healthy, False otherwise.
        """
        if not self._initialized:
            self._logger.warning("%s provider not initialized", self.name.title())
            return False

        if not self.enabled:
            self._logger.debug("%s provider disabled", self.name.title())
            return False

        return True

    @override
    def send_notification(self, message: str, **kwargs: object) -> bool:
        """
        Send a notification with common pre-processing.

        This method implements the common notification sending logic,
        including enabled checks, configuration validation, and raw values
        extraction. Subclasses should override _send_notification_impl
        to implement provider-specific sending logic.

        Args:
            message: The message to send.
            **kwargs: Additional provider-specific arguments.

        Returns:
            True if the notification was sent successfully, False otherwise.
        """
        # Check if provider is enabled
        if not self._check_enabled():
            return False

        # Validate configuration
        errors = self.validate_config()
        if errors:
            self._log_config_errors(errors)
            return False

        # Extract raw values and remove from kwargs
        kwargs_dict = dict(kwargs)
        raw_values = self._extract_raw_values(kwargs_dict)

        # Remove raw_values from kwargs to avoid conflicts
        filtered_kwargs = {k: v for k, v in kwargs_dict.items() if k != "raw_values"}

        # Call provider-specific implementation
        try:
            return self._send_notification_impl(message, raw_values, **filtered_kwargs)
        except Exception as e:
            self._logger.error("Error sending %s notification: %s", self.name, e)
            return False

    @abstractmethod
    def _send_notification_impl(
        self,
        message: str,
        raw_values: RawValues,
        **kwargs: object
    ) -> bool:
        """
        Provider-specific notification sending implementation.

        Subclasses must implement this method to provide the actual
        notification sending logic.

        Args:
            message: The message to send.
            raw_values: Extracted and validated raw values.
            **kwargs: Additional provider-specific arguments (excluding raw_values).

        Returns:
            True if the notification was sent successfully, False otherwise.
        """
        pass

    @abstractmethod
    @override
    def validate_config(self) -> list[str]:
        """
        Validate the provider configuration.

        Subclasses must implement this method to provide provider-specific
        configuration validation logic.

        Returns:
            A list of error messages. An empty list indicates a valid configuration.
        """
        pass
