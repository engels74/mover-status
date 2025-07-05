"""Comprehensive error handling for the configuration system."""

from __future__ import annotations

import logging
from typing import Any, cast

from pydantic import ValidationError

logger = logging.getLogger(__name__)


class ConfigError(Exception):
    """Base exception for all configuration-related errors."""
    
    def __init__(self, message: str, context: dict[str, Any] | None = None) -> None:  # pyright: ignore[reportAny] # Flexible config error context
        """Initialize ConfigError.
        
        Args:
            message: Error message
            context: Additional context information for debugging
        """
        super().__init__(message)
        self.context: dict[str, Any] = context or {}  # pyright: ignore[reportAny] # Flexible config error context


class ConfigLoadError(ConfigError):
    """Exception raised when configuration loading fails."""
    
    def __init__(
        self,
        message: str,
        file_path: str | None = None,
        context: dict[str, Any] | None = None,  # pyright: ignore[reportAny] # Flexible config error context
    ) -> None:
        """Initialize ConfigLoadError.
        
        Args:
            message: Error message
            file_path: Path to the configuration file that failed to load
            context: Additional context information
        """
        # Build context with file path if provided
        full_context = context or {}
        if file_path is not None:
            full_context["file_path"] = file_path
            
        super().__init__(message, full_context)
        self.file_path: str | None = file_path


class EnvLoadError(ConfigError):
    """Exception raised when environment variable loading fails."""
    
    def __init__(
        self,
        message: str,
        env_var: str | None = None,
        context: dict[str, Any] | None = None,  # pyright: ignore[reportAny] # Flexible config error context
    ) -> None:
        """Initialize EnvLoadError.
        
        Args:
            message: Error message
            env_var: Environment variable name that caused the error
            context: Additional context information
        """
        # Build context with environment variable if provided
        full_context = context or {}
        if env_var is not None:
            full_context["env_var"] = env_var
            
        super().__init__(message, full_context)
        self.env_var: str | None = env_var


class ConfigMergeError(ConfigError):
    """Exception raised during configuration merging operations."""
    
    def __init__(
        self,
        message: str,
        config_path: str = "",
        context: dict[str, Any] | None = None,  # pyright: ignore[reportAny] # Flexible config error context
    ) -> None:
        """Initialize ConfigMergeError.
        
        Args:
            message: Error message
            config_path: Path to the configuration field that caused the error
            context: Additional context information
        """
        # Build context with configuration path if provided
        full_context = context or {}
        if config_path:
            full_context["config_path"] = config_path
            
        super().__init__(message, full_context)
        self.config_path: str = config_path


class ConfigValidationError(ConfigError):
    """Exception raised when configuration validation fails."""
    
    def __init__(
        self,
        message: str,
        pydantic_error: ValidationError | None = None,
        context: dict[str, Any] | None = None,  # pyright: ignore[reportAny] # Flexible config error context
    ) -> None:
        """Initialize ConfigValidationError.
        
        Args:
            message: Error message
            pydantic_error: Original Pydantic ValidationError
            context: Additional context information
        """
        # Build context with validation error details if provided
        full_context = context or {}
        if pydantic_error is not None:
            full_context["validation_errors"] = self._format_validation_errors(pydantic_error)
            
        super().__init__(message, full_context)
        self.pydantic_error: ValidationError | None = pydantic_error
    
    def _format_validation_errors(self, error: ValidationError) -> list[dict[str, Any]]:  # pyright: ignore[reportAny] # Flexible error formatting
        """Format Pydantic validation errors for better readability.
        
        Args:
            error: Pydantic ValidationError
            
        Returns:
            List of formatted error dictionaries
        """
        formatted_errors: list[dict[str, Any]] = []  # pyright: ignore[reportAny] # Flexible error formatting
        for err in error.errors():
            formatted_errors.append({
                "field": ".".join(str(loc) for loc in err["loc"]),
                "message": err["msg"],
                "type": err["type"],
                "input": err.get("input"),
            })
        return formatted_errors


def get_error_context(
    file_path: str | None = None,
    env_var: str | None = None,
    config_path: str | None = None,
    **additional_info: Any,  # pyright: ignore[reportAny] # Flexible additional context
) -> dict[str, Any]:  # pyright: ignore[reportAny] # Flexible error context
    """Build error context dictionary from provided information.
    
    Args:
        file_path: Path to configuration file
        env_var: Environment variable name
        config_path: Configuration field path
        **additional_info: Additional context information
        
    Returns:
        Dictionary containing error context
    """
    context: dict[str, Any] = {}  # pyright: ignore[reportAny] # Flexible error context
    
    if file_path is not None:
        context["file_path"] = file_path
    if env_var is not None:
        context["env_var"] = env_var
    if config_path is not None:
        context["config_path"] = config_path
        
    # Add any additional information
    context.update(additional_info)
    
    return context


def handle_config_error(error: Exception, operation: str) -> ConfigError:
    """Handle and wrap configuration errors with consistent error types.
    
    Args:
        error: Original exception
        operation: Description of the operation that failed
        
    Returns:
        Wrapped ConfigError instance
    """
    # Log the original error for debugging
    logger.debug(f"Configuration error during {operation}: {error}", exc_info=True)
    
    # Return known configuration errors as-is
    if isinstance(error, ConfigError):
        return error
    
    # Wrap Pydantic validation errors
    if isinstance(error, ValidationError):
        return ConfigValidationError(
            f"Configuration validation failed during {operation}",
            pydantic_error=error,
        )
    
    # Wrap other exceptions as generic ConfigError
    wrapped_error = ConfigError(
        f"Configuration error during {operation}: {error}",
        context={"operation": operation, "original_error_type": type(error).__name__},
    )
    wrapped_error.__cause__ = error
    return wrapped_error


def log_config_error(error: ConfigError, level: int = logging.WARNING) -> None:
    """Log configuration error with appropriate context.
    
    Args:
        error: Configuration error to log
        level: Logging level (default: WARNING)
    """
    # Build log message with context
    message = str(error)
    if error.context:
        context_str = ", ".join(f"{k}={v}" for k, v in error.context.items())  # pyright: ignore[reportAny] # Flexible context values
        message = f"{message} (context: {context_str})"
    
    logger.log(level, message, exc_info=True)


def suggest_config_fix(error: ConfigError) -> str | None:
    """Suggest potential fixes for configuration errors.
    
    Args:
        error: Configuration error
        
    Returns:
        Suggested fix or None if no suggestion available
    """
    # Suggestions for file loading errors
    if isinstance(error, ConfigLoadError):
        if error.file_path:
            return f"Check that the file exists and is readable: {error.file_path}"
        return "Check that the configuration file exists and is readable"
    
    # Suggestions for environment variable errors
    if isinstance(error, EnvLoadError):
        if error.env_var:
            return f"Check the format and value of environment variable: {error.env_var}"
        return "Check the format and values of environment variables"
    
    # Suggestions for validation errors
    if isinstance(error, ConfigValidationError) and error.pydantic_error:
        error_count = len(error.pydantic_error.errors())
        if error_count == 1:
            err = error.pydantic_error.errors()[0]
            field_path = ".".join(str(loc) for loc in err["loc"])
            return f"Fix validation error in field '{field_path}': {err['msg']}"
        return f"Fix {error_count} validation errors in the configuration"
    
    # Suggestions for merge errors
    if isinstance(error, ConfigMergeError):
        if error.config_path:
            return f"Check for type conflicts in configuration path: {error.config_path}"
        return "Check for type conflicts between configuration sources"
    
    return None