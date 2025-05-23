"""
Validation methods for the ConfigManager class.

This module contains the validation logic that was extracted from the original
config_manager.py file to keep the manager.py file focused on core functionality.

Note: isinstance checks in this module are intentional for validating user-provided
configuration data that may not conform to TypedDict types at runtime.
"""
# pyright: reportUnnecessaryIsInstance=false

from typing import cast, TYPE_CHECKING

from mover_status.config.types import (
    NotificationConfig, MonitoringConfig, DebugConfig
)
from mover_status.config.validation_error import ValidationError

if TYPE_CHECKING:
    from mover_status.config.models import MoverStatusConfig


class ConfigManagerValidationMixin:
    """
    Mixin class containing validation methods for ConfigManager.

    This class provides validation functionality that can be mixed into
    the ConfigManager class to keep the main manager file focused.
    """

    # Type annotation for the config attribute that will be provided by the ConfigManager
    # This is a mixin class, so the config attribute is provided by the class that uses this mixin
    config: "MoverStatusConfig"  # pyright: ignore[reportUninitializedInstanceVariable]

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
            # Get the notification section and cast it to the correct type
            notification = cast(NotificationConfig, self.config["notification"])

            if "notification_increment" not in notification:
                errors.append("Missing required field: notification.notification_increment")
            if "enabled_providers" not in notification:
                errors.append("Missing required field: notification.enabled_providers")

            # Check provider-specific required fields
            if "providers" in notification:
                # Get the providers section
                providers = notification["providers"]

                # Check Telegram provider required fields
                if "telegram" in providers:
                    # Get the telegram section
                    telegram = providers["telegram"]

                    if "enabled" in telegram and telegram["enabled"]:
                        if "bot_token" not in telegram or not telegram["bot_token"]:
                            errors.append("Missing required field: notification.providers.telegram.bot_token")
                        if "chat_id" not in telegram or not telegram["chat_id"]:
                            errors.append("Missing required field: notification.providers.telegram.chat_id")

                # Check Discord provider required fields
                if "discord" in providers:
                    # Get the discord section
                    discord = providers["discord"]

                    if "enabled" in discord and discord["enabled"]:
                        if "webhook_url" not in discord or not discord["webhook_url"]:
                            errors.append("Missing required field: notification.providers.discord.webhook_url")

        # Check monitoring section required fields
        if "monitoring" in self.config:
            # Cast to the correct type
            monitoring = cast(MonitoringConfig, self.config["monitoring"])

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
            # Cast to the correct type
            notification = cast(NotificationConfig, self.config["notification"])

            # Check notification_increment type - validate user-provided data
            if "notification_increment" in notification and not isinstance(notification["notification_increment"], int):
                errors.append("Field notification.notification_increment must be an integer")

            # Check enabled_providers type
            if "enabled_providers" in notification:
                if not isinstance(notification["enabled_providers"], list):
                    errors.append("Field notification.enabled_providers must be a list")

            # Check provider-specific field types
            if "providers" in notification:
                # Get the providers section
                providers = notification["providers"]

                # Check Telegram provider field types
                if "telegram" in providers:
                    # Get the telegram section
                    telegram = providers["telegram"]
                    if "enabled" in telegram and not isinstance(telegram["enabled"], bool):
                        errors.append("Field notification.providers.telegram.enabled must be a boolean")
                    if "bot_token" in telegram and not isinstance(telegram["bot_token"], str):
                        errors.append("Field notification.providers.telegram.bot_token must be a string")
                    if "chat_id" in telegram and not isinstance(telegram["chat_id"], str):
                        errors.append("Field notification.providers.telegram.chat_id must be a string")

                # Check Discord provider field types
                if "discord" in providers:
                    # Get the discord section
                    discord = providers["discord"]
                    if "enabled" in discord and not isinstance(discord["enabled"], bool):
                        errors.append("Field notification.providers.discord.enabled must be a boolean")
                    if "webhook_url" in discord and not isinstance(discord["webhook_url"], str):
                        errors.append("Field notification.providers.discord.webhook_url must be a string")
                    if "username" in discord and not isinstance(discord["username"], str):
                        errors.append("Field notification.providers.discord.username must be a string")

        # Check monitoring section field types
        if "monitoring" in self.config:
            # Cast to the correct type
            monitoring = cast(MonitoringConfig, self.config["monitoring"])

            if "mover_executable" in monitoring and not isinstance(monitoring["mover_executable"], str):
                errors.append("Field monitoring.mover_executable must be a string")
            if "cache_directory" in monitoring and not isinstance(monitoring["cache_directory"], str):
                errors.append("Field monitoring.cache_directory must be a string")
            if "poll_interval" in monitoring and not isinstance(monitoring["poll_interval"], int):
                errors.append("Field monitoring.poll_interval must be an integer")

        # Check debug section field types
        if "debug" in self.config:
            # Cast to the correct type
            debug = cast(DebugConfig, self.config["debug"])

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
            # Cast to the correct type
            notification = cast(NotificationConfig, self.config["notification"])

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
                # Get the providers section
                providers = notification["providers"]

                # Check Telegram provider field values
                if "telegram" in providers:
                    # Get the telegram section
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
                    # Get the discord section
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
            # Cast to the correct type
            monitoring = cast(MonitoringConfig, self.config["monitoring"])

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