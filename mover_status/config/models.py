"""
Configuration model classes for the Mover Status Monitor.

This module contains the MoverStatusConfig class, which represents the complete
configuration structure and provides methods for converting between dictionary
and class representations.
"""

from collections.abc import Mapping
from typing import final, cast

from mover_status.config.types import (
    ConfigSections,
    NotificationConfig,
    MonitoringConfig,
    MessagesConfig,
    PathsConfig,
    DebugConfig,
)


@final
class MoverStatusConfig:
    """
    Configuration class for the Mover Status Monitor.

    This class represents the complete configuration structure and provides
    methods for converting between dictionary and class representations.

    This class is decorated with @final to avoid the need for type annotations
    on instance attributes, as they are guaranteed to be set in __init__.
    """

    def __init__(
        self,
        notification: NotificationConfig,
        monitoring: MonitoringConfig,
        messages: MessagesConfig,
        paths: PathsConfig,
        debug: DebugConfig
    ) -> None:
        """
        Initialize the MoverStatusConfig.

        Args:
            notification: Notification configuration
            monitoring: Monitoring configuration
            messages: Messages configuration
            paths: Paths configuration
            debug: Debug configuration
        """
        self._data: ConfigSections = {
            "notification": notification,
            "monitoring": monitoring,
            "messages": messages,
            "paths": paths,
            "debug": debug
        }

    def __getitem__(self, key: str) -> NotificationConfig | MonitoringConfig | MessagesConfig | PathsConfig | DebugConfig:
        """
        Get a configuration section by key.

        Args:
            key: The section key to get

        Returns:
            The configuration section

        Raises:
            KeyError: If the key does not exist
        """
        if key not in self._data:
            raise KeyError(f"Unknown configuration section: {key}")

        if key == "notification":
            return self._data["notification"]
        elif key == "monitoring":
            return self._data["monitoring"]
        elif key == "messages":
            return self._data["messages"]
        elif key == "paths":
            return self._data["paths"]
        elif key == "debug":
            return self._data["debug"]
        else:
            # This should never happen due to the check above
            raise KeyError(f"Unknown configuration section: {key}")

    def __contains__(self, key: str) -> bool:
        """
        Check if a configuration section exists.

        Args:
            key: The section key to check

        Returns:
            True if the section exists, False otherwise
        """
        return key in self._data

    def get_nested_value(self, path: str) -> object:
        """
        Get a nested configuration value using dot notation.

        This method provides type-safe access to nested configuration values.

        Args:
            path: The path to the configuration value using dot notation
                 (e.g., "notification.providers.telegram.enabled")

        Returns:
            The configuration value at the specified path. The return type depends on the path:
            - For paths ending with ".enabled_providers": list[str]
            - For paths ending with ".telegram" or ".discord": dict[str, object]
            - For other paths: str, int, bool, list, dict, or None

        Raises:
            KeyError: If any part of the path does not exist
        """
        if not path:
            raise KeyError("Empty path")

        parts = path.split(".")
        section = parts[0]

        # Get the top-level section
        if section not in self._data:
            raise KeyError(f"Unknown configuration section: {section}")

        # Start with the section value
        if section == "notification":
            section_data = self._data["notification"]
        elif section == "monitoring":
            section_data = self._data["monitoring"]
        elif section == "messages":
            section_data = self._data["messages"]
        elif section == "paths":
            section_data = self._data["paths"]
        elif section == "debug":
            section_data = self._data["debug"]
        else:
            # This should never happen due to the check above
            raise KeyError(f"Unknown configuration section: {section}")

        # TypedDict is structurally compatible with dict, but we need to cast to satisfy the type checker
        current_dict = cast(dict[str, object], cast(object, section_data))

        # Navigate through the nested keys
        for i in range(1, len(parts)):
            key = parts[i]
            if not isinstance(current_dict, dict):  # pyright: ignore[reportUnnecessaryIsInstance]
                raise KeyError(f"Cannot access '{key}' in '{'.'.join(parts[:i])}': not a dictionary")

            if key not in current_dict:
                raise KeyError(f"Key '{key}' not found in '{'.'.join(parts[:i])}'")

            value = current_dict[key]
            if i == len(parts) - 1:
                # We've reached the final key, return the value
                return value

            # Continue traversing if we're not at the final key
            if not isinstance(value, dict):
                raise KeyError(f"Cannot access '{parts[i+1]}' in '{'.'.join(parts[:i+1])}': not a dictionary")

            current_dict = cast(dict[str, object], value)

        # This should never happen due to the loop structure
        return cast(object, current_dict)

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "MoverStatusConfig":
        """
        Create a MoverStatusConfig instance from a dictionary.

        Args:
            data: Dictionary containing configuration data

        Returns:
            A new MoverStatusConfig instance
        """
        # Create a copy to avoid modifying the original
        config_data = dict(data)

        # Ensure all required sections exist
        for section in ["notification", "monitoring", "messages", "paths", "debug"]:
            if section not in config_data:
                config_data[section] = {}

        # Cast the dictionary sections to their appropriate types
        notification = cast(NotificationConfig, config_data.get("notification", {}))
        monitoring = cast(MonitoringConfig, config_data.get("monitoring", {}))
        messages = cast(MessagesConfig, config_data.get("messages", {}))
        paths = cast(PathsConfig, config_data.get("paths", {}))
        debug = cast(DebugConfig, config_data.get("debug", {}))

        return cls(
            notification=notification,
            monitoring=monitoring,
            messages=messages,
            paths=paths,
            debug=debug,
        )

    def to_dict(self) -> ConfigSections:
        """
        Convert the MoverStatusConfig to a dictionary.

        Returns:
            Dictionary representation of the configuration
        """
        return self._data.copy()
