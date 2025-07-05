"""Tests for comprehensive configuration error handling."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from mover_status.config.exceptions import (
    ConfigError,
    ConfigLoadError,
    ConfigMergeError,
    ConfigValidationError,
    EnvLoadError,
    get_error_context,
    handle_config_error,
)


class TestConfigError:
    """Test ConfigError base exception class."""
    
    def test_config_error_creation(self) -> None:
        """Test ConfigError can be created with message and context."""
        error = ConfigError("Test error", context={"field": "test"})
        assert str(error) == "Test error"
        assert error.context == {"field": "test"}
        
    def test_config_error_no_context(self) -> None:
        """Test ConfigError can be created without context."""
        error = ConfigError("Test error")
        assert str(error) == "Test error"
        assert error.context == {}
        
    def test_config_error_chaining(self) -> None:
        """Test ConfigError can chain exceptions."""
        cause = ValueError("Original error")
        error = ConfigError("Wrapper error", context={"cause": "ValueError"})
        error.__cause__ = cause
        
        assert str(error) == "Wrapper error"
        assert error.__cause__ is cause


class TestConfigLoadError:
    """Test ConfigLoadError for file loading issues."""
    
    def test_config_load_error_with_file_path(self) -> None:
        """Test ConfigLoadError includes file path in context."""
        error = ConfigLoadError("Failed to load", file_path="/path/to/config.yaml")
        assert "Failed to load" in str(error)
        assert error.file_path == "/path/to/config.yaml"
        assert error.context["file_path"] == "/path/to/config.yaml"
        
    def test_config_load_error_without_file_path(self) -> None:
        """Test ConfigLoadError works without file path."""
        error = ConfigLoadError("Failed to load")
        assert str(error) == "Failed to load"
        assert error.file_path is None
        assert error.context.get("file_path") is None


class TestEnvLoadError:
    """Test EnvLoadError for environment variable issues."""
    
    def test_env_load_error_with_var_name(self) -> None:
        """Test EnvLoadError includes environment variable name."""
        error = EnvLoadError("Invalid value", env_var="MOVER_STATUS_TIMEOUT")
        assert "Invalid value" in str(error)
        assert error.env_var == "MOVER_STATUS_TIMEOUT"
        assert error.context["env_var"] == "MOVER_STATUS_TIMEOUT"
        
    def test_env_load_error_without_var_name(self) -> None:
        """Test EnvLoadError works without environment variable name."""
        error = EnvLoadError("Generic error")
        assert str(error) == "Generic error"
        assert error.env_var is None
        assert error.context.get("env_var") is None


class TestConfigMergeError:
    """Test ConfigMergeError for configuration merging issues."""
    
    def test_config_merge_error_with_config_path(self) -> None:
        """Test ConfigMergeError includes configuration path."""
        error = ConfigMergeError("Merge conflict", config_path="database.timeout")
        assert "Merge conflict" in str(error)
        assert error.config_path == "database.timeout"
        assert error.context["config_path"] == "database.timeout"
        
    def test_config_merge_error_without_config_path(self) -> None:
        """Test ConfigMergeError works without configuration path."""
        error = ConfigMergeError("Generic merge error")
        assert str(error) == "Generic merge error"
        assert error.config_path == ""
        assert error.context.get("config_path") is None


class TestConfigValidationError:
    """Test ConfigValidationError for Pydantic validation issues."""
    
    def test_config_validation_error_with_pydantic_error(self) -> None:
        """Test ConfigValidationError wraps Pydantic ValidationError."""
        # Create a simple test to verify the error handling system works
        try:
            from pydantic import BaseModel, Field
            
            class TestModel(BaseModel):
                required_field: str = Field(...)
                
            # This will raise a ValidationError
            TestModel()
        except ValidationError as pydantic_error:
            error = ConfigValidationError("Validation failed", pydantic_error=pydantic_error)
            assert "Validation failed" in str(error)
            assert error.pydantic_error is pydantic_error
            assert error.context["validation_errors"] is not None
        
    def test_config_validation_error_without_pydantic_error(self) -> None:
        """Test ConfigValidationError works without Pydantic error."""
        error = ConfigValidationError("Custom validation error")
        assert str(error) == "Custom validation error"
        assert error.pydantic_error is None
        assert error.context.get("validation_errors") is None


class TestErrorUtilities:
    """Test error handling utility functions."""
    
    def test_get_error_context_with_all_fields(self) -> None:
        """Test get_error_context includes all provided fields."""
        context = get_error_context(
            file_path="/config.yaml",
            env_var="TEST_VAR",
            config_path="nested.field",
            additional_info="Extra context",
        )
        
        assert context["file_path"] == "/config.yaml"
        assert context["env_var"] == "TEST_VAR"
        assert context["config_path"] == "nested.field"
        assert context["additional_info"] == "Extra context"
        
    def test_get_error_context_with_partial_fields(self) -> None:
        """Test get_error_context only includes non-None fields."""
        context = get_error_context(
            file_path="/config.yaml",
            env_var=None,
            config_path="nested.field",
        )
        
        assert context["file_path"] == "/config.yaml"
        assert context["config_path"] == "nested.field"
        assert "env_var" not in context
        
    def test_get_error_context_empty(self) -> None:
        """Test get_error_context returns empty dict when no fields provided."""
        context = get_error_context()
        assert context == {}
        
    def test_handle_config_error_with_known_error(self) -> None:
        """Test handle_config_error handles known configuration errors."""
        original_error = ConfigLoadError("File not found")
        
        handled = handle_config_error(original_error, "Loading configuration")
        
        assert isinstance(handled, ConfigLoadError)
        assert handled is original_error
        
    def test_handle_config_error_with_unknown_error(self) -> None:
        """Test handle_config_error wraps unknown errors."""
        original_error = ValueError("Unknown error")
        
        handled = handle_config_error(original_error, "Loading configuration")
        
        assert isinstance(handled, ConfigError)
        assert "Loading configuration" in str(handled)
        assert handled.__cause__ is original_error
        
    def test_handle_config_error_with_pydantic_validation_error(self) -> None:
        """Test handle_config_error handles Pydantic ValidationError."""
        # Create a simple test to verify the error handling system works
        try:
            from pydantic import BaseModel, Field
            
            class TestModel(BaseModel):
                required_field: str = Field(...)
                
            # This will raise a ValidationError
            TestModel()
        except ValidationError as pydantic_error:
            handled = handle_config_error(pydantic_error, "Validating configuration")
            
            assert isinstance(handled, ConfigValidationError)
            assert "Validating configuration" in str(handled)
            assert handled.pydantic_error is pydantic_error