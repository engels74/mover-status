"""Tests for the Configuration Validation System."""

from __future__ import annotations

import os
import pytest
from unittest.mock import patch
from typing import TYPE_CHECKING, override
from collections.abc import Mapping

from mover_status.notifications.base.config_validator import (
    ConfigValidator,
    ConfigValidationError,
    CredentialValidator,
    EnvironmentValidator,
    ValidationResult,
    ValidationSeverity,
    ValidationIssue,
)
from mover_status.notifications.base.provider import NotificationProvider
from mover_status.notifications.models.message import Message

if TYPE_CHECKING:
    pass


class MockProvider(NotificationProvider):
    """Mock provider for testing configuration validation."""
    
    def __init__(self, config: Mapping[str, object]) -> None:
        super().__init__(config)
        self.validation_calls: list[bool] = []
        
    @override
    async def send_notification(self, message: Message) -> bool:
        """Mock send notification."""
        return True
        
    @override
    def validate_config(self) -> None:
        """Mock validate config."""
        self.validation_calls.append(True)
        
    @override
    def get_provider_name(self) -> str:
        """Mock get provider name."""
        return "mock"


class TestValidationResult:
    """Test ValidationResult class."""
    
    def test_validation_result_creation(self) -> None:
        """Test creating a validation result."""
        result = ValidationResult(
            is_valid=True,
            issues=[],
            provider_name="test"
        )
        
        assert result.is_valid is True
        assert result.issues == []
        assert result.provider_name == "test"
        
    def test_validation_result_with_issues(self) -> None:
        """Test validation result with issues."""
        issue = ValidationIssue(
            field="api_key",
            message="API key is required",
            severity=ValidationSeverity.ERROR,
            code="MISSING_REQUIRED_FIELD"
        )
        
        result = ValidationResult(
            is_valid=False,
            issues=[issue],
            provider_name="test"
        )
        
        assert result.is_valid is False
        assert len(result.issues) == 1
        assert result.issues[0].field == "api_key"
        assert result.issues[0].severity == ValidationSeverity.ERROR
        
    def test_validation_result_has_errors(self) -> None:
        """Test checking if result has errors."""
        warning_issue = ValidationIssue(
            field="timeout",
            message="Timeout is high",
            severity=ValidationSeverity.WARNING,
            code="HIGH_TIMEOUT"
        )
        
        error_issue = ValidationIssue(
            field="api_key",
            message="API key is invalid",
            severity=ValidationSeverity.ERROR,
            code="INVALID_API_KEY"
        )
        
        result_with_warnings = ValidationResult(
            is_valid=True,
            issues=[warning_issue],
            provider_name="test"
        )
        
        result_with_errors = ValidationResult(
            is_valid=False,
            issues=[error_issue],
            provider_name="test"
        )
        
        assert not result_with_warnings.has_errors()
        assert result_with_errors.has_errors()



class TestCredentialValidator:
    """Test CredentialValidator class."""
    
    @pytest.mark.asyncio
    async def test_credential_validator_creation(self) -> None:
        """Test creating a credential validator."""
        async def test_func(_config: Mapping[str, object]) -> bool:
            return True
            
        validator = CredentialValidator(test_func)
        assert validator.test_function == test_func
        
    @pytest.mark.asyncio
    async def test_validate_valid_credentials(self) -> None:
        """Test validating valid credentials."""
        async def test_func(_config: Mapping[str, object]) -> bool:
            return True
            
        validator = CredentialValidator(test_func)
        config = {"api_key": "valid-key"}
        
        result = await validator.validate(config)
        
        assert result.is_valid is True
        assert len(result.issues) == 0
        
    @pytest.mark.asyncio
    async def test_validate_invalid_credentials(self) -> None:
        """Test validating invalid credentials."""
        async def test_func(_config: Mapping[str, object]) -> bool:
            return False
            
        validator = CredentialValidator(test_func)
        config = {"api_key": "invalid-key"}
        
        result = await validator.validate(config)
        
        assert result.is_valid is False
        assert len(result.issues) == 1
        assert result.issues[0].code == "CREDENTIAL_TEST_FAILED"
        
    @pytest.mark.asyncio
    async def test_validate_credentials_exception(self) -> None:
        """Test credential validation with exception."""
        async def test_func(_config: Mapping[str, object]) -> bool:
            raise ValueError("Connection failed")
            
        validator = CredentialValidator(test_func)
        config = {"api_key": "test-key"}
        
        result = await validator.validate(config)
        
        assert result.is_valid is False
        assert len(result.issues) == 1
        assert "Connection failed" in result.issues[0].message


class TestEnvironmentValidator:
    """Test EnvironmentValidator class."""
    
    def test_environment_validator_creation(self) -> None:
        """Test creating an environment validator."""
        env_mapping = {"API_KEY": "api_key", "TIMEOUT": "timeout"}
        validator = EnvironmentValidator(env_mapping)
        assert validator.env_mapping == env_mapping
        
    def test_validate_with_env_vars(self) -> None:
        """Test validation with environment variables."""
        env_mapping = {"TEST_API_KEY": "api_key", "TEST_TIMEOUT": "timeout"}
        validator = EnvironmentValidator(env_mapping)

        with patch.dict(os.environ, {"TEST_API_KEY": "env-key", "TEST_TIMEOUT": "60"}):
            config: dict[str, object] = {}
            result = validator.validate(config)

            assert result.is_valid is True
            # Should have INFO issues for using environment variables
            assert len(result.issues) == 2
            assert all(issue.severity == ValidationSeverity.INFO for issue in result.issues)
            assert all(issue.code == "USING_ENV_VAR" for issue in result.issues)
            
    def test_validate_missing_env_vars(self) -> None:
        """Test validation with missing environment variables."""
        env_mapping = {"MISSING_API_KEY": "api_key"}
        validator = EnvironmentValidator(env_mapping)

        config: dict[str, object] = {}
        result = validator.validate(config)
        
        assert result.is_valid is False
        assert len(result.issues) == 1
        assert result.issues[0].code == "MISSING_ENV_VAR"


class TestConfigValidator:
    """Test ConfigValidator class."""
    
    def test_config_validator_creation(self) -> None:
        """Test creating a config validator."""
        validator = ConfigValidator("test-provider")
        assert validator.provider_name == "test-provider"
        assert len(validator.credential_validators) == 0
        assert len(validator.environment_validators) == 0
        
    def test_add_credential_validator(self) -> None:
        """Test adding a credential validator."""
        validator = ConfigValidator("test-provider")
        
        async def test_func(_config: Mapping[str, object]) -> bool:
            return True
            
        validator.add_credential_validator(test_func)
        
        assert len(validator.credential_validators) == 1
        
    def test_add_environment_validator(self) -> None:
        """Test adding an environment validator."""
        validator = ConfigValidator("test-provider")
        env_mapping = {"API_KEY": "api_key"}
        
        validator.add_environment_validator(env_mapping)
        
        assert len(validator.environment_validators) == 1
        
    @pytest.mark.asyncio
    async def test_validate_config_success(self) -> None:
        """Test successful configuration validation."""
        validator = ConfigValidator("test-provider")

        # Add credential validator
        async def test_func(_config: Mapping[str, object]) -> bool:
            return True

        validator.add_credential_validator(test_func)

        config: dict[str, object] = {"api_key": "valid-key"}
        result = await validator.validate(config)
        
        assert result.is_valid is True
        assert len(result.issues) == 0
        
    @pytest.mark.asyncio
    async def test_validate_config_failure(self) -> None:
        """Test failed configuration validation."""
        validator = ConfigValidator("test-provider")

        # Add credential validator that will fail
        async def test_func(_config: Mapping[str, object]) -> bool:
            return False

        validator.add_credential_validator(test_func)

        config: dict[str, object] = {"api_key": "invalid-key"}
        result = await validator.validate(config)
        
        assert result.is_valid is False
        assert len(result.issues) >= 1

    def test_validation_result_get_error_summary(self) -> None:
        """Test getting error summary from validation result."""
        # Test with no errors
        result_no_errors = ValidationResult(
            is_valid=True,
            issues=[],
            provider_name="test"
        )
        assert result_no_errors.get_error_summary() == "No errors found"

        # Test with errors
        error_issue = ValidationIssue(
            field="api_key",
            message="API key is required",
            severity=ValidationSeverity.ERROR,
            code="MISSING_REQUIRED_FIELD"
        )

        result_with_errors = ValidationResult(
            is_valid=False,
            issues=[error_issue],
            provider_name="test"
        )

        summary = result_with_errors.get_error_summary()
        assert "Found 1 error(s)" in summary
        assert "API key is required" in summary

    def test_config_validation_error(self) -> None:
        """Test ConfigValidationError exception."""
        issue = ValidationIssue(
            field="api_key",
            message="API key is required",
            severity=ValidationSeverity.ERROR,
            code="MISSING_REQUIRED_FIELD"
        )

        result = ValidationResult(
            is_valid=False,
            issues=[issue],
            provider_name="test"
        )

        error = ConfigValidationError("Validation failed", result)
        assert str(error) == "Validation failed"
        assert error.result == result


    @pytest.mark.asyncio
    async def test_validate_config_with_environment_validator(self) -> None:
        """Test configuration validation with environment validator."""
        validator = ConfigValidator("test-provider")

        # Add environment validator
        env_mapping = {"TEST_API_KEY": "api_key"}
        validator.add_environment_validator(env_mapping)

        config: dict[str, object] = {}
        result = await validator.validate(config)

        # Should fail because environment variable is missing
        assert result.is_valid is False
        assert len(result.issues) >= 1
        assert any(issue.code == "MISSING_ENV_VAR" for issue in result.issues)
