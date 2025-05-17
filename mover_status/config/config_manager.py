"""
Configuration manager for the Mover Status Monitor.

This module provides the ConfigManager class, which is responsible for loading,
validating, and saving configuration data for the application. It standardizes
on YAML as the configuration format and provides a clean interface for accessing
configuration values throughout the application.
"""

import os
import yaml
from typing import Dict, Any, Optional, cast, List

from mover_status.config.default_config import DEFAULT_CONFIG
from mover_status.notification.providers.telegram.defaults import TELEGRAM_DEFAULTS
from mover_status.notification.providers.discord.defaults import DISCORD_DEFAULTS
from mover_status.config.validation_error import ValidationError


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

    def __init__(self, config_path: Optional[str] = None) -> None:
        """
        Initialize the ConfigManager.

        Args:
            config_path: Optional path to a configuration file. If not provided,
                         will use default configuration values.
        """
        self.config_path = config_path
        self.config = self.get_default_config()

    @staticmethod
    def get_default_config() -> Dict[str, Any]:
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
        default_config["notification"]["providers"]["telegram"] = {
            k: v for k, v in TELEGRAM_DEFAULTS.items() if k != "name" and k != "enabled"
        }

        # Add Discord provider defaults
        default_config["notification"]["providers"]["discord"] = {
            k: v for k, v in DISCORD_DEFAULTS.items() if k != "name" and k != "enabled"
        }

        return default_config

    def load(self, config_path: Optional[str] = None) -> Dict[str, Any]:
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
                user_config = yaml.safe_load(f)

            # If the file is empty or not a dictionary, use the default config
            if user_config is None or not isinstance(user_config, dict):
                self.config = self.get_default_config()
                # Validate the default configuration
                self.validate_config()
                return self.config

            # Merge with defaults
            self.config = self._merge_with_defaults(cast(Dict[str, Any], user_config))

            # Validate the merged configuration
            self.validate_config()

            return self.config

        except yaml.YAMLError as e:
            # If the YAML is invalid, raise a ValueError
            raise ValueError(f"Invalid YAML in configuration file: {e}")

    def _merge_with_defaults(self, user_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Merge user configuration with default configuration.

        Args:
            user_config: The user configuration dictionary.

        Returns:
            The merged configuration dictionary.
        """
        # Start with a deep copy of the default config
        merged_config = self.get_default_config()

        # Recursively merge the user config into the default config
        self._merge_dicts(merged_config, user_config)

        return merged_config

    def _merge_dicts(self, target: Dict[str, Any], source: Dict[str, Any]) -> None:
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
                self._merge_dicts(target[key], cast(Dict[str, Any], value))
            else:
                # Otherwise, just overwrite the value
                target[key] = value

    def save(self, config_path: Optional[str] = None) -> None:
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
            yaml.dump(self.config, f, default_flow_style=False)

    def get(self, key: Optional[str], default: Any = None) -> Any:
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

        # Split the key by dots to handle nested keys
        keys = key.split(".")

        # Start with the full config
        current_dict: Dict[str, Any] = self.config

        # Traverse the config dictionary
        for i, k in enumerate(keys):
            # If the key doesn't exist, return the default
            if k not in current_dict:
                return default

            # If this is the last key, return the value
            if i == len(keys) - 1:
                return current_dict[k]

            # Otherwise, move to the next level
            current_dict = cast(Dict[str, Any], current_dict[k])

        # This should never be reached, but return the last value just in case
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
        errors: List[str] = []

        # Validate required fields
        errors.extend(self._validate_required_fields())

        # Validate field types
        errors.extend(self._validate_field_types())

        # Validate field values
        errors.extend(self._validate_field_values())

        # If there are any errors, raise a ValidationError
        if errors:
            raise ValidationError("Configuration validation failed:", errors)

    def _validate_required_fields(self) -> List[str]:
        """
        Validate that all required fields are present in the configuration.

        Returns:
            A list of error messages for missing required fields.
        """
        errors: List[str] = []

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

    def _validate_field_types(self) -> List[str]:
        """
        Validate that all fields have the correct type.

        Returns:
            A list of error messages for fields with incorrect types.
        """
        errors: List[str] = []

        # Check notification section field types
        if "notification" in self.config and isinstance(self.config["notification"], dict):
            notification = self.config["notification"]

            # Check notification_increment type
            if "notification_increment" in notification and not isinstance(notification["notification_increment"], int):
                errors.append("Field notification.notification_increment must be an integer")

            # Check enabled_providers type
            if "enabled_providers" in notification and not isinstance(notification["enabled_providers"], list):
                errors.append("Field notification.enabled_providers must be a list")

            # Check provider-specific field types
            if "providers" in notification and isinstance(notification["providers"], dict):
                providers = notification["providers"]

                # Check Telegram provider field types
                if "telegram" in providers and isinstance(providers["telegram"], dict):
                    telegram = providers["telegram"]
                    if "enabled" in telegram and not isinstance(telegram["enabled"], bool):
                        errors.append("Field notification.providers.telegram.enabled must be a boolean")
                    if "bot_token" in telegram and not isinstance(telegram["bot_token"], str):
                        errors.append("Field notification.providers.telegram.bot_token must be a string")
                    if "chat_id" in telegram and not isinstance(telegram["chat_id"], str):
                        errors.append("Field notification.providers.telegram.chat_id must be a string")

                # Check Discord provider field types
                if "discord" in providers and isinstance(providers["discord"], dict):
                    discord = providers["discord"]
                    if "enabled" in discord and not isinstance(discord["enabled"], bool):
                        errors.append("Field notification.providers.discord.enabled must be a boolean")
                    if "webhook_url" in discord and not isinstance(discord["webhook_url"], str):
                        errors.append("Field notification.providers.discord.webhook_url must be a string")
                    if "username" in discord and not isinstance(discord["username"], str):
                        errors.append("Field notification.providers.discord.username must be a string")

        # Check monitoring section field types
        if "monitoring" in self.config and isinstance(self.config["monitoring"], dict):
            monitoring = self.config["monitoring"]
            if "mover_executable" in monitoring and not isinstance(monitoring["mover_executable"], str):
                errors.append("Field monitoring.mover_executable must be a string")
            if "cache_directory" in monitoring and not isinstance(monitoring["cache_directory"], str):
                errors.append("Field monitoring.cache_directory must be a string")
            if "poll_interval" in monitoring and not isinstance(monitoring["poll_interval"], int):
                errors.append("Field monitoring.poll_interval must be an integer")

        # Check debug section field types
        if "debug" in self.config and isinstance(self.config["debug"], dict):
            debug = self.config["debug"]
            if "dry_run" in debug and not isinstance(debug["dry_run"], bool):
                errors.append("Field debug.dry_run must be a boolean")
            if "enable_debug" in debug and not isinstance(debug["enable_debug"], bool):
                errors.append("Field debug.enable_debug must be a boolean")

        return errors

    def _validate_field_values(self) -> List[str]:
        """
        Validate that all field values are valid.

        Returns:
            A list of error messages for fields with invalid values.
        """
        errors: List[str] = []

        # Check notification section field values
        if "notification" in self.config and isinstance(self.config["notification"], dict):
            notification = self.config["notification"]

            # Check notification_increment value
            if (
                "notification_increment" in notification
                and isinstance(notification["notification_increment"], int)
                and notification["notification_increment"] <= 0
            ):
                errors.append("Field notification.notification_increment must be positive")

            # Check enabled_providers value
            if "enabled_providers" in notification and isinstance(notification["enabled_providers"], list):
                valid_providers = ["telegram", "discord"]
                for provider in notification["enabled_providers"]:
                    if provider not in valid_providers:
                        errors.append(f"Invalid provider in notification.enabled_providers: {provider}")

            # Check provider-specific field values
            if "providers" in notification and isinstance(notification["providers"], dict):
                providers = notification["providers"]

                # Check Telegram provider field values
                if "telegram" in providers and isinstance(providers["telegram"], dict):
                    telegram = providers["telegram"]
                    if (
                        "enabled" in telegram
                        and telegram["enabled"] is True
                        and "bot_token" in telegram
                        and isinstance(telegram["bot_token"], str)
                        and not telegram["bot_token"]
                    ):
                        errors.append("Field notification.providers.telegram.bot_token cannot be empty when enabled")
                    if (
                        "enabled" in telegram
                        and telegram["enabled"] is True
                        and "chat_id" in telegram
                        and isinstance(telegram["chat_id"], str)
                        and not telegram["chat_id"]
                    ):
                        errors.append("Field notification.providers.telegram.chat_id cannot be empty when enabled")

                # Check Discord provider field values
                if "discord" in providers and isinstance(providers["discord"], dict):
                    discord = providers["discord"]
                    if (
                        "enabled" in discord
                        and discord["enabled"] is True
                        and "webhook_url" in discord
                        and isinstance(discord["webhook_url"], str)
                        and not discord["webhook_url"]
                    ):
                        errors.append("Field notification.providers.discord.webhook_url cannot be empty when enabled")

        # Check monitoring section field values
        if "monitoring" in self.config and isinstance(self.config["monitoring"], dict):
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
