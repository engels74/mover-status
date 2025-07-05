"""YAML configuration loader."""

from __future__ import annotations

from pathlib import Path

import yaml


class ConfigLoadError(Exception):
    """Exception raised when configuration loading fails."""
    
    def __init__(self, message: str) -> None:
        """Initialize ConfigLoadError with a descriptive message."""
        super().__init__(message)
        self.message: str = message


class YamlLoader:
    """Loader for YAML configuration files."""
    
    def __init__(self) -> None:
        """Initialize YamlLoader."""
        pass
    
    def load(self, path: Path) -> dict[str, object]:
        """Load configuration from a YAML file.
        
        Args:
            path: Path to the YAML configuration file
            
        Returns:
            Parsed configuration as a dictionary
            
        Raises:
            ConfigLoadError: If the file cannot be loaded or parsed
        """
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = yaml.safe_load(f)  # pyright: ignore[reportAny] # yaml.safe_load returns Any
                # Handle empty files or files with null content
                if isinstance(content, dict):
                    return content  # pyright: ignore[reportUnknownVariableType] # content is dict after isinstance check
                return {}
        except Exception as e:
            raise ConfigLoadError(f"Failed to load {path}: {e}") from e