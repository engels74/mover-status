"""Environment variable configuration loader."""

from __future__ import annotations

import json
import os
from typing import cast

from ..exceptions import EnvLoadError


class EnvLoader:
    """Environment variable loader with support for nested structures and type conversion."""

    def __init__(
        self,
        prefix: str = "MOVER_STATUS_",
        separator: str = "_",
        convert_types: bool = False,
        mappings: dict[str, str] | None = None,
    ) -> None:
        """Initialize EnvLoader.
        
        Args:
            prefix: Prefix for environment variables to load
            separator: Separator for nested field names (default: "_")
            convert_types: Whether to attempt automatic type conversion
            mappings: Custom mappings from env var names to config paths
        """
        self.prefix: str = prefix
        self.separator: str = separator
        self.convert_types: bool = convert_types
        self.mappings: dict[str, str] = mappings or {}

    def load(self) -> dict[str, object]:
        """Load configuration from environment variables.
        
        Returns:
            Dictionary containing the loaded configuration
            
        Raises:
            EnvLoadError: If there are errors processing environment variables
        """
        config: dict[str, object] = {}
        
        # Process custom mappings first
        for env_var, config_path in self.mappings.items():
            if env_var in os.environ:
                value = os.environ[env_var]
                if self.convert_types:
                    value = self._convert_value(value, env_var)
                self._set_nested_value(config, config_path, value)
        
        # Process prefix-based environment variables
        for env_var, raw_value in os.environ.items():
            if not env_var.startswith(self.prefix):
                continue
                
            # Skip if already processed via custom mapping
            if env_var in self.mappings:
                continue
                
            # Remove prefix and convert to config path
            config_key = env_var[len(self.prefix):]
            if not config_key:
                continue
                
            # Convert to lowercase and handle separators
            config_path = config_key.lower()
            
            # If we have double underscores, use them for nesting and preserve single underscores
            # Otherwise, use the traditional behavior where single underscores become dots
            if "__" in config_path:
                # New behavior: __ for nesting, _ preserved for field names like bot_token
                config_path = config_path.replace("__", ".")
            else:
                # Traditional behavior: _ becomes . for nesting
                if self.separator != ".":
                    config_path = config_path.replace(self.separator, ".")
            
            # Convert value if type conversion is enabled
            value: object = raw_value
            if self.convert_types:
                value = self._convert_value(raw_value, env_var)
            
            self._set_nested_value(config, config_path, value)
        
        return config

    def _convert_value(self, value: str, env_var: str) -> object:
        """Convert string value to appropriate Python type.
        
        Args:
            value: String value to convert
            env_var: Environment variable name (for error reporting)
            
        Returns:
            Converted value
            
        Raises:
            EnvLoadError: If JSON parsing fails
        """
        if not value:
            return value
            
        # Try boolean conversion first
        bool_value = self._try_bool_conversion(value)
        if bool_value is not None:
            return bool_value
            
        # Try numeric conversion
        numeric_value = self._try_numeric_conversion(value)
        if numeric_value is not None:
            return numeric_value
            
        # Try JSON parsing for complex types
        if value.startswith(('[', '{')):
            try:
                return cast(object, json.loads(value))
            except json.JSONDecodeError as e:
                raise EnvLoadError(
                    f"Failed to parse JSON for {env_var}: {e}",
                    env_var
                ) from e
                
        # Return as string if no conversion applies
        return value

    def _try_bool_conversion(self, value: str) -> bool | None:
        """Try to convert string to boolean.
        
        Args:
            value: String value to convert
            
        Returns:
            Boolean value or None if not a boolean
        """
        lower_value = value.lower()
        if lower_value in ("true", "1", "yes", "on"):
            return True
        elif lower_value in ("false", "0", "no", "off"):
            return False
        return None

    def _try_numeric_conversion(self, value: str) -> int | float | None:
        """Try to convert string to numeric value.
        
        Args:
            value: String value to convert
            
        Returns:
            Numeric value or None if not numeric
        """
        try:
            # Try int first
            if '.' not in value and 'e' not in value.lower():
                return int(value)
            # Try float
            return float(value)
        except ValueError:
            return None

    def _set_nested_value(self, config: dict[str, object], path: str, value: object) -> None:
        """Set a value in a nested dictionary using dot notation.
        
        Args:
            config: Dictionary to modify
            path: Dot-separated path to the value
            value: Value to set
        """
        keys = path.split(".")
        current: dict[str, object] = config
        
        # Navigate to the parent of the final key
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            elif not isinstance(current[key], dict):
                # Convert to dict if it's not already
                current[key] = {}
            # We know this is a dict due to the if conditions above
            current = current[key]  # pyright: ignore[reportAssignmentType]
        
        # Set the final value
        final_key = keys[-1]
        current[final_key] = value