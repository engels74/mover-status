"""
Configuration manager for the Mover Status Monitor.

This module provides the ConfigManager class, which is responsible for loading,
validating, and saving configuration data for the application. It standardizes
on YAML as the configuration format and provides a clean interface for accessing
configuration values throughout the application.
"""

# pyright: reportUnnecessaryIsInstance=false
# The above directive is necessary because this module performs runtime type validation
# of user-provided configuration data, which requires isinstance checks even when
# the static type system can determine the types.

import os
from collections.abc import Mapping
import yaml
from typing import TypedDict, final, cast, TypeVar

from mover_status.config.default_config import DEFAULT_CONFIG
from mover_status.notification.providers.telegram.defaults import TELEGRAM_DEFAULTS
from mover_status.notification.providers.discord.defaults import DISCORD_DEFAULTS
from mover_status.config.validation_error import ValidationError

# Type variables for generic dictionary operations
T = TypeVar('T')
K = TypeVar('K', bound=str)
V = TypeVar('V')

# Type definitions for configuration structure
class TelegramConfig(TypedDict):
    """Telegram notification provider configuration."""
    enabled: bool
    bot_token: str
    chat_id: str
    message_template: str
    parse_mode: str
    disable_notification: bool


class DiscordConfig(TypedDict):
    """Discord notification provider configuration."""
    enabled: bool
    webhook_url: str
    username: str
    message_template: str
    use_embeds: bool
    embed_title: str
    embed_colors: dict[str, int]


class ProvidersConfig(TypedDict):
    """Container for all notification provider configurations."""
    telegram: TelegramConfig
    discord: DiscordConfig


class NotificationConfig(TypedDict):
    """Notification settings configuration."""
    notification_increment: int
    enabled_providers: list[str]
    providers: ProvidersConfig


class MonitoringConfig(TypedDict):
    """Monitoring settings configuration."""
    mover_executable: str
    cache_directory: str
    poll_interval: int


class MessagesConfig(TypedDict):
    """Message templates configuration."""
    completion: str


class PathsConfig(TypedDict):
    """Path settings configuration."""
    exclude: list[str]


class DebugConfig(TypedDict):
    """Debug settings configuration."""
    dry_run: bool
    enable_debug: bool


# Define a type for the complete configuration structure
class ConfigSections(TypedDict):
    """Complete configuration structure with all sections."""
    notification: NotificationConfig
    monitoring: MonitoringConfig
    messages: MessagesConfig
    paths: PathsConfig
    debug: DebugConfig


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
            The configuration value at the specified path

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
            if not isinstance(current_dict, dict):
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


class ConfigManager:
    """
    Manages configuration loading, validation, and saving for the Mover Status Monitor.

    This class handles:
    - Loading configuration from YAML files
    - Merging with default configuration values
    - Validating configuration structure and values
    - Saving configuration to YAML files
    - Providing access to configuration values
    """

    def __init__(self, config_path: str | None = None) -> None:
        """
        Initialize the ConfigManager.

        Args:
            config_path: Optional path to a configuration file. If not provided,
                         will use default configuration values.
        """
        self.config_path: str | None = config_path
        self.config: MoverStatusConfig = self.get_default_config()

    @staticmethod
    def get_default_config() -> MoverStatusConfig:
        """
        Get the default configuration by merging core defaults with provider defaults.

        Returns:
            The default configuration dictionary.
        """
        # Start with a deep copy of the core default config
        default_config = DEFAULT_CONFIG.copy()

        # Create providers section if it doesn't exist
        if "providers" not in default_config["notification"]:
            default_config["notification"]["providers"] = {}

        # Add Telegram provider defaults
        telegram_defaults: dict[str, object] = {}
        for k, item_value in TELEGRAM_DEFAULTS.items():
            if k != "name" and k != "enabled":
                # We know the value is a valid configuration value
                telegram_defaults[k] = cast(object, item_value)
        default_config["notification"]["providers"]["telegram"] = telegram_defaults

        # Add Discord provider defaults
        discord_defaults: dict[str, object] = {}
        for k, item_value in DISCORD_DEFAULTS.items():
            if k != "name" and k != "enabled":
                # We know the value is a valid configuration value
                discord_defaults[k] = cast(object, item_value)
        default_config["notification"]["providers"]["discord"] = discord_defaults

        # Convert the dictionary to a MoverStatusConfig object
        return MoverStatusConfig.from_dict(default_config)

    def load(self, config_path: str | None = None) -> MoverStatusConfig:
        """
        Load configuration from a YAML file and merge with defaults.

        Args:
            config_path: Path to the configuration file. If not provided,
                         will use the path provided during initialization.

        Returns:
            The merged configuration dictionary.

        Raises:
            ValueError: If the configuration file is invalid.
            ValidationError: If the configuration fails validation.
        """
        # Use the provided path or fall back to the instance path
        path = config_path or self.config_path

        # If no path is provided, just use the default config
        if path is None:
            self.config = self.get_default_config()
            # Validate the default configuration
            self.validate_config()
            return self.config

        # Check if the file exists
        if not os.path.exists(path):
            # If the file doesn't exist, use the default config
            self.config = self.get_default_config()
            # Validate the default configuration
            self.validate_config()
            return self.config

        try:
            # Load the YAML file
            with open(path, "r") as f:
                # yaml.safe_load returns Any, but we know it's a dictionary or None
                user_config_raw = yaml.safe_load(f)  # pyright: ignore[reportAny]

            # If the file is empty or not a dictionary, use the default config
            if user_config_raw is None or not isinstance(user_config_raw, dict):
                self.config = self.get_default_config()
                # Validate the default configuration
                self.validate_config()
                return self.config

            # Convert to a properly typed dictionary
            user_config = cast(Mapping[str, object], user_config_raw)

            # Merge with defaults
            self.config = self.merge_with_defaults(user_config)

            # Validate the merged configuration
            self.validate_config()

            return self.config

        except yaml.YAMLError as e:
            # If the YAML is invalid, raise a ValueError
            raise ValueError(f"Invalid YAML in configuration file: {e}")

    def merge_with_defaults(self, user_config: Mapping[str, object]) -> MoverStatusConfig:
        """
        Merge user configuration with default configuration.

        Args:
            user_config: The user configuration dictionary.

        Returns:
            The merged configuration dictionary.
        """
        # Start with a deep copy of the default config
        default_config = dict(self.get_default_config().to_dict())

        # Recursively merge the user config into the default config
        self._merge_dicts(default_config, user_config)

        # Convert the merged dictionary to a MoverStatusConfig object
        return MoverStatusConfig.from_dict(default_config)

    def _merge_dicts(self, target: dict[str, object], source: Mapping[str, object]) -> None:
        """
        Recursively merge source dictionary into target dictionary.

        Args:
            target: The target dictionary to merge into.
            source: The source dictionary to merge from.
        """
        for key, value in source.items():
            # If the value is a dictionary and the key exists in the target
            # and the target value is also a dictionary, recursively merge
            if (
                isinstance(value, dict)
                and key in target
                and isinstance(target[key], dict)
            ):
                self._merge_dicts(cast(dict[str, object], target[key]), cast(Mapping[str, object], value))
            else:
                # Otherwise, just overwrite the value
                target[key] = value

    def save(self, config_path: str | None = None) -> None:
        """
        Save the current configuration to a YAML file.

        Args:
            config_path: Path to save the configuration file. If not provided,
                         will use the path provided during initialization.

        Raises:
            ValueError: If no path is provided and no path was provided during initialization.
            PermissionError: If the file cannot be written due to permissions.
            IOError: If there is an error writing the file.
        """
        # Use the provided path or fall back to the instance path
        path = config_path or self.config_path

        # If no path is provided, raise an error
        if path is None:
            raise ValueError("No configuration path provided")

        # Save the configuration to the file
        with open(path, "w") as f:
            yaml.dump(self.config.to_dict(), f, default_flow_style=False)

    def get(self, key: str | None, default: object = None) -> object:
        """
        Get a configuration value by key.

        Args:
            key: The configuration key to get. Can use dot notation for nested keys.
            default: The default value to return if the key does not exist.

        Returns:
            The configuration value, or the default if the key does not exist.
        """
        # If the key is None or empty, return the default
        if key is None or key == "":
            return default

        try:
            # Use the get_nested_value method from MoverStatusConfig
            return self.config.get_nested_value(key)
        except KeyError:
            # If the key doesn't exist, return the default
            return default

    def validate_config(self) -> None:
        """
        Validate the configuration.

        This method checks that:
        - All required fields are present
        - All fields have the correct type
        - All field values are valid

        Raises:
            ValidationError: If the configuration is invalid.
        """
        errors: list[str] = []

        # Validate required fields
        errors.extend(self._validate_required_fields())

        # Validate field types
        errors.extend(self._validate_field_types())

        # Validate field values
        errors.extend(self._validate_field_values())

        # If there are any errors, raise a ValidationError
        if errors:
            raise ValidationError("Configuration validation failed:", errors)

    def _validate_required_fields(self) -> list[str]:
        """
        Validate that all required fields are present in the configuration.

        Returns:
            A list of error messages for missing required fields.
        """
        errors: list[str] = []

        # Check top-level required sections
        required_sections = ["notification", "monitoring", "messages", "paths", "debug"]
        for section in required_sections:
            if section not in self.config:
                errors.append(f"Missing required section: {section}")

        # Check notification section required fields
        if "notification" in self.config:
            notification = self.config["notification"]
            if "notification_increment" not in notification:
                errors.append("Missing required field: notification.notification_increment")
            if "enabled_providers" not in notification:
                errors.append("Missing required field: notification.enabled_providers")

            # Check provider-specific required fields
            if "providers" in notification:
                providers = notification["providers"]

                # Check Telegram provider required fields
                if "telegram" in providers:
                    telegram = providers["telegram"]
                    if "enabled" in telegram and telegram["enabled"]:
                        if "bot_token" not in telegram or not telegram["bot_token"]:
                            errors.append("Missing required field: notification.providers.telegram.bot_token")
                        if "chat_id" not in telegram or not telegram["chat_id"]:
                            errors.append("Missing required field: notification.providers.telegram.chat_id")

                # Check Discord provider required fields
                if "discord" in providers:
                    discord = providers["discord"]
                    if "enabled" in discord and discord["enabled"]:
                        if "webhook_url" not in discord or not discord["webhook_url"]:
                            errors.append("Missing required field: notification.providers.discord.webhook_url")

        # Check monitoring section required fields
        if "monitoring" in self.config:
            monitoring = self.config["monitoring"]
            if "mover_executable" not in monitoring:
                errors.append("Missing required field: monitoring.mover_executable")
            if "cache_directory" not in monitoring:
                errors.append("Missing required field: monitoring.cache_directory")
            if "poll_interval" not in monitoring:
                errors.append("Missing required field: monitoring.poll_interval")

        return errors

    def _validate_field_types(self) -> list[str]:
        """
        Validate that all fields have the correct type.

        Returns:
            A list of error messages for fields with incorrect types.
        """
        errors: list[str] = []

        # Check notification section field types
        if "notification" in self.config:
            notification = self.config["notification"]

            # Check notification_increment type
            if "notification_increment" in notification and not isinstance(notification["notification_increment"], int):
                errors.append("Field notification.notification_increment must be an integer")

            # Check enabled_providers type
            if "enabled_providers" in notification and not isinstance(notification["enabled_providers"], list):
                errors.append("Field notification.enabled_providers must be a list")

            # Check provider-specific field types
            if "providers" in notification:
                providers = notification["providers"]

                # Check Telegram provider field types
                if "telegram" in providers:
                    telegram = providers["telegram"]
                    if "enabled" in telegram and not isinstance(telegram["enabled"], bool):
                        errors.append("Field notification.providers.telegram.enabled must be a boolean")
                    if "bot_token" in telegram and not isinstance(telegram["bot_token"], str):
                        errors.append("Field notification.providers.telegram.bot_token must be a string")
                    if "chat_id" in telegram and not isinstance(telegram["chat_id"], str):
                        errors.append("Field notification.providers.telegram.chat_id must be a string")

                # Check Discord provider field types
                if "discord" in providers:
                    discord = providers["discord"]
                    if "enabled" in discord and not isinstance(discord["enabled"], bool):
                        errors.append("Field notification.providers.discord.enabled must be a boolean")
                    if "webhook_url" in discord and not isinstance(discord["webhook_url"], str):
                        errors.append("Field notification.providers.discord.webhook_url must be a string")
                    if "username" in discord and not isinstance(discord["username"], str):
                        errors.append("Field notification.providers.discord.username must be a string")

        # Check monitoring section field types
        if "monitoring" in self.config:
            monitoring = self.config["monitoring"]
            if "mover_executable" in monitoring and not isinstance(monitoring["mover_executable"], str):
                errors.append("Field monitoring.mover_executable must be a string")
            if "cache_directory" in monitoring and not isinstance(monitoring["cache_directory"], str):
                errors.append("Field monitoring.cache_directory must be a string")
            if "poll_interval" in monitoring and not isinstance(monitoring["poll_interval"], int):
                errors.append("Field monitoring.poll_interval must be an integer")

        # Check debug section field types
        if "debug" in self.config:
            debug = self.config["debug"]
            if "dry_run" in debug and not isinstance(debug["dry_run"], bool):
                errors.append("Field debug.dry_run must be a boolean")
            if "enable_debug" in debug and not isinstance(debug["enable_debug"], bool):
                errors.append("Field debug.enable_debug must be a boolean")

        return errors

    def _validate_field_values(self) -> list[str]:
        """
        Validate that all field values are valid.

        Returns:
            A list of error messages for fields with invalid values.
        """
        errors: list[str] = []

        # Check notification section field values
        if "notification" in self.config:
            notification = self.config["notification"]

            # Check notification_increment value
            if (
                "notification_increment" in notification
                and isinstance(notification["notification_increment"], int)
                and notification["notification_increment"] <= 0
            ):
                errors.append("Field notification.notification_increment must be positive")

            # Check enabled_providers value
            if "enabled_providers" in notification:
                valid_providers = ["telegram", "discord"]
                for provider in notification["enabled_providers"]:
                    if provider not in valid_providers:
                        errors.append(f"Invalid provider in notification.enabled_providers: {provider}")

            # Check provider-specific field values
            if "providers" in notification:
                providers = notification["providers"]

                # Check Telegram provider field values
                if "telegram" in providers:
                    telegram = providers["telegram"]
                    if (
                        "enabled" in telegram
                        and telegram["enabled"] is True
                        and "bot_token" in telegram
                        and not telegram["bot_token"]
                    ):
                        errors.append("Field notification.providers.telegram.bot_token cannot be empty when enabled")
                    if (
                        "enabled" in telegram
                        and telegram["enabled"] is True
                        and "chat_id" in telegram
                        and not telegram["chat_id"]
                    ):
                        errors.append("Field notification.providers.telegram.chat_id cannot be empty when enabled")

                # Check Discord provider field values
                if "discord" in providers:
                    discord = providers["discord"]
                    if (
                        "enabled" in discord
                        and discord["enabled"] is True
                        and "webhook_url" in discord
                        and not discord["webhook_url"]
                    ):
                        errors.append("Field notification.providers.discord.webhook_url cannot be empty when enabled")

        # Check monitoring section field values
        if "monitoring" in self.config:
            monitoring = self.config["monitoring"]

            # Check poll_interval value
            if (
                "poll_interval" in monitoring
                and isinstance(monitoring["poll_interval"], int)
                and monitoring["poll_interval"] <= 0
            ):
                errors.append("Field monitoring.poll_interval must be positive")

            # Check mover_executable value
            if (
                "mover_executable" in monitoring
                and isinstance(monitoring["mover_executable"], str)
                and not monitoring["mover_executable"].startswith("/")
            ):
                errors.append("Field monitoring.mover_executable must be an absolute path")

            # Check cache_directory value
            if (
                "cache_directory" in monitoring
                and isinstance(monitoring["cache_directory"], str)
                and not monitoring["cache_directory"].startswith("/")
            ):
                errors.append("Field monitoring.cache_directory must be an absolute path")

        return errors
