"""Configuration merging functionality for combining multiple configuration sources."""

from __future__ import annotations

import copy
from typing import Any

# Type aliases for better clarity
ConfigDict = dict[str, Any]  # pyright: ignore[reportExplicitAny] # Config systems need flexible types
ConfigValue = str | int | float | bool | list[Any] | dict[str, Any] | None  # pyright: ignore[reportExplicitAny] # Config systems need flexible types


class ConfigMergeError(Exception):
    """Exception raised during configuration merging operations."""
    
    def __init__(self, message: str, config_path: str = "") -> None:
        """Initialize ConfigMergeError.
        
        Args:
            message: Error message
            config_path: Path to the configuration field that caused the error
        """
        super().__init__(message)
        self.config_path: str = config_path


class ConfigMerger:
    """Configuration merger that combines multiple configuration sources with precedence rules."""
    
    def __init__(self, track_sources: bool = False) -> None:
        """Initialize ConfigMerger.
        
        Args:
            track_sources: Whether to track source information for audit trail
        """
        self._track_sources: bool = track_sources
        self._audit_trail: dict[str, str] = {} if track_sources else {}
    
    def merge(self, base: object, override: object) -> ConfigDict:
        """Merge two configuration dictionaries with override precedence.
        
        Args:
            base: Base configuration dictionary
            override: Override configuration dictionary (takes precedence)
            
        Returns:
            Merged configuration dictionary
            
        Raises:
            ConfigMergeError: If merge operation fails
        """
        if not isinstance(base, dict):
            raise ConfigMergeError("Base configuration must be a dictionary")
        if not isinstance(override, dict):
            raise ConfigMergeError("Override configuration must be a dictionary")
        
        # Deep copy to avoid modifying original dictionaries
        result = copy.deepcopy(base)
        
        # Record base sources in audit trail
        if self._track_sources:
            self._record_sources(result, "base", "")
        
        # Merge override configuration
        self._deep_merge(result, override, "override", "")
        
        return result
    
    def merge_multiple(self, sources: list[object]) -> ConfigDict:
        """Merge multiple configuration sources with left-to-right precedence.
        
        Args:
            sources: List of configuration dictionaries (later sources take precedence)
            
        Returns:
            Merged configuration dictionary
        """
        if not sources:
            return {}
        
        # Validate first source
        if not isinstance(sources[0], dict):
            raise ConfigMergeError("Source 0 must be a dictionary")
        
        if len(sources) == 1:
            result = copy.deepcopy(sources[0])
            if self._track_sources:
                self._record_sources(result, "source_0", "")
            return result
        
        # Start with first source
        result = copy.deepcopy(sources[0])
        if self._track_sources:
            self._record_sources(result, "source_0", "")
        
        # Merge remaining sources
        for i, source in enumerate(sources[1:], 1):
            if not isinstance(source, dict):
                raise ConfigMergeError(f"Source {i} must be a dictionary")
            
            self._deep_merge(result, source, f"source_{i}", "")
        
        return result
    
    def _deep_merge(self, target: ConfigDict, source: ConfigDict, source_name: str, path: str) -> None:
        """Recursively merge source dictionary into target dictionary.
        
        Args:
            target: Target dictionary to merge into
            source: Source dictionary to merge from
            source_name: Name of the source for audit trail
            path: Current path in the configuration hierarchy
        """
        for key, value in source.items():
            current_path = f"{path}.{key}" if path else key
            
            if key not in target:
                # New key, add it
                target[key] = copy.deepcopy(value)
                if self._track_sources:
                    self._audit_trail[current_path] = source_name
            elif isinstance(target[key], dict) and isinstance(value, dict):
                # Both are dictionaries, merge recursively
                self._deep_merge(target[key], value, source_name, current_path)
            else:
                # Override existing value (including lists and other types)
                target[key] = copy.deepcopy(value)
                if self._track_sources:
                    self._audit_trail[current_path] = source_name
    
    def _record_sources(self, config: ConfigDict, source_name: str, path: str) -> None:
        """Record source information for all keys in a configuration dictionary.
        
        Args:
            config: Configuration dictionary
            source_name: Name of the source
            path: Current path in the configuration hierarchy
        """
        for key, value in config.items():
            current_path = f"{path}.{key}" if path else key
            self._audit_trail[current_path] = source_name
            
            if isinstance(value, dict):
                self._record_sources(value, source_name, current_path)
    
    def get_audit_trail(self) -> dict[str, str]:
        """Get audit trail information showing which source provided each configuration value.
        
        Returns:
            Dictionary mapping configuration paths to source names
        """
        return self._audit_trail.copy()
    
    def clear_audit_trail(self) -> None:
        """Clear the audit trail information."""
        self._audit_trail.clear()