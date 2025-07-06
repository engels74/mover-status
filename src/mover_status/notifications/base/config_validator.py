"""Configuration validation system for notification providers."""

from __future__ import annotations

import os
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field as dataclass_field
from enum import Enum
from typing import TYPE_CHECKING, override

import jsonschema
from jsonschema import ValidationError as JsonSchemaValidationError

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Mapping

logger = logging.getLogger(__name__)


class ValidationSeverity(Enum):
    """Severity levels for validation issues."""
    
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class ValidationIssue:
    """Represents a validation issue found during configuration validation."""
    
    field: str
    message: str
    severity: ValidationSeverity
    code: str
    details: dict[str, object] = dataclass_field(default_factory=dict)
    
    @override
    def __str__(self) -> str:
        """String representation of the validation issue."""
        return f"[{self.severity.value.upper()}] {self.field}: {self.message} ({self.code})"


@dataclass
class ValidationResult:
    """Result of configuration validation."""
    
    is_valid: bool
    issues: list[ValidationIssue]
    provider_name: str
    
    def has_errors(self) -> bool:
        """Check if the result contains any error-level issues."""
        return any(issue.severity == ValidationSeverity.ERROR for issue in self.issues)
    
    def get_error_summary(self) -> str:
        """Get a summary of all errors."""
        errors = [issue for issue in self.issues if issue.severity == ValidationSeverity.ERROR]
        if not errors:
            return "No errors found"
        
        return f"Found {len(errors)} error(s): " + "; ".join(str(error) for error in errors)


class ConfigValidationError(Exception):
    """Exception raised when configuration validation fails."""
    
    def __init__(self, message: str, result: ValidationResult) -> None:
        """Initialize the exception.
        
        Args:
            message: Error message
            result: Validation result containing details
        """
        super().__init__(message)
        self.result: ValidationResult = result


class BaseValidator(ABC):
    """Abstract base class for configuration validators."""
    
    @abstractmethod
    def validate(self, config: Mapping[str, object]) -> ValidationResult | Awaitable[ValidationResult]:
        """Validate configuration.
        
        Args:
            config: Configuration to validate
            
        Returns:
            Validation result (may be async)
        """
        ...


class SchemaValidator(BaseValidator):
    """JSON Schema-based configuration validator."""
    
    def __init__(self, schema: Mapping[str, object]) -> None:
        """Initialize the schema validator.

        Args:
            schema: JSON schema for validation
        """
        self.schema: dict[str, object] = dict(schema)

    @override
    def validate(self, config: Mapping[str, object]) -> ValidationResult:
        """Validate configuration against JSON schema.
        
        Args:
            config: Configuration to validate
            
        Returns:
            Validation result
        """
        issues: list[ValidationIssue] = []
        
        try:
            jsonschema.validate(dict(config), self.schema)
        except JsonSchemaValidationError as e:
            # Convert JSON schema validation errors to our format
            field_path = ".".join(str(part) for part in e.absolute_path) if e.absolute_path else "root"
            
            issue = ValidationIssue(
                field=field_path,
                message=e.message,
                severity=ValidationSeverity.ERROR,
                code="SCHEMA_VALIDATION_ERROR",
                details={
                    "schema_path": list(e.schema_path),
                    "failed_value": e.instance,
                }
            )
            issues.append(issue)
            
        except Exception as e:
            # Handle other validation errors
            issue = ValidationIssue(
                field="root",
                message=f"Schema validation failed: {e}",
                severity=ValidationSeverity.ERROR,
                code="SCHEMA_VALIDATION_EXCEPTION",
                details={"exception_type": type(e).__name__}
            )
            issues.append(issue)
        
        return ValidationResult(
            is_valid=len(issues) == 0,
            issues=issues,
            provider_name="schema"
        )


class CredentialValidator(BaseValidator):
    """Validator for testing credentials by making actual API calls."""
    
    def __init__(self, test_function: Callable[[Mapping[str, object]], Awaitable[bool]]) -> None:
        """Initialize the credential validator.
        
        Args:
            test_function: Async function that tests credentials
        """
        self.test_function: Callable[[Mapping[str, object]], Awaitable[bool]] = test_function

    @override
    async def validate(self, config: Mapping[str, object]) -> ValidationResult:
        """Validate credentials by testing them.
        
        Args:
            config: Configuration containing credentials
            
        Returns:
            Validation result
        """
        issues: list[ValidationIssue] = []
        
        try:
            is_valid = await self.test_function(config)
            
            if not is_valid:
                issue = ValidationIssue(
                    field="credentials",
                    message="Credential test failed - authentication unsuccessful",
                    severity=ValidationSeverity.ERROR,
                    code="CREDENTIAL_TEST_FAILED"
                )
                issues.append(issue)
                
        except Exception as e:
            issue = ValidationIssue(
                field="credentials",
                message=f"Credential test failed with exception: {e}",
                severity=ValidationSeverity.ERROR,
                code="CREDENTIAL_TEST_EXCEPTION",
                details={"exception_type": type(e).__name__}
            )
            issues.append(issue)
        
        return ValidationResult(
            is_valid=len(issues) == 0,
            issues=issues,
            provider_name="credentials"
        )


class EnvironmentValidator(BaseValidator):
    """Validator for environment variable configuration."""
    
    def __init__(self, env_mapping: dict[str, str]) -> None:
        """Initialize the environment validator.
        
        Args:
            env_mapping: Mapping from environment variable names to config keys
        """
        self.env_mapping: dict[str, str] = env_mapping

    @override
    def validate(self, config: Mapping[str, object]) -> ValidationResult:
        """Validate environment variable configuration.
        
        Args:
            config: Configuration to validate
            
        Returns:
            Validation result
        """
        issues: list[ValidationIssue] = []
        
        for env_var, config_key in self.env_mapping.items():
            env_value = os.environ.get(env_var)
            config_value = config.get(config_key)
            
            # Check if environment variable is available when config value is missing
            if config_value is None and env_value is None:
                issue = ValidationIssue(
                    field=config_key,
                    message=f"Neither config value nor environment variable {env_var} is set",
                    severity=ValidationSeverity.ERROR,
                    code="MISSING_ENV_VAR",
                    details={"env_var": env_var}
                )
                issues.append(issue)
            elif env_value is not None and config_value is None:
                # Environment variable is available - this is good
                issue = ValidationIssue(
                    field=config_key,
                    message=f"Using environment variable {env_var} for configuration",
                    severity=ValidationSeverity.INFO,
                    code="USING_ENV_VAR",
                    details={"env_var": env_var}
                )
                issues.append(issue)
        
        return ValidationResult(
            is_valid=not any(issue.severity == ValidationSeverity.ERROR for issue in issues),
            issues=issues,
            provider_name="environment"
        )


class ConfigValidator:
    """Main configuration validator that orchestrates multiple validation strategies."""
    
    def __init__(self, provider_name: str) -> None:
        """Initialize the config validator.
        
        Args:
            provider_name: Name of the provider being validated
        """
        self.provider_name: str = provider_name
        self.schema_validators: list[SchemaValidator] = []
        self.credential_validators: list[CredentialValidator] = []
        self.environment_validators: list[EnvironmentValidator] = []
        
    def add_schema_validator(self, schema: Mapping[str, object]) -> None:
        """Add a JSON schema validator.

        Args:
            schema: JSON schema for validation
        """
        self.schema_validators.append(SchemaValidator(schema))
        
    def add_credential_validator(
        self, 
        test_function: Callable[[Mapping[str, object]], Awaitable[bool]]
    ) -> None:
        """Add a credential validator.
        
        Args:
            test_function: Function to test credentials
        """
        self.credential_validators.append(CredentialValidator(test_function))
        
    def add_environment_validator(self, env_mapping: dict[str, str]) -> None:
        """Add an environment variable validator.
        
        Args:
            env_mapping: Mapping from environment variables to config keys
        """
        self.environment_validators.append(EnvironmentValidator(env_mapping))
        
    async def validate(self, config: Mapping[str, object]) -> ValidationResult:
        """Validate configuration using all registered validators.
        
        Args:
            config: Configuration to validate
            
        Returns:
            Combined validation result
        """
        all_issues: list[ValidationIssue] = []
        
        # Run schema validators
        for validator in self.schema_validators:
            result = validator.validate(config)
            all_issues.extend(result.issues)
            
        # Run environment validators
        for validator in self.environment_validators:
            result = validator.validate(config)
            all_issues.extend(result.issues)
            
        # Run credential validators (async)
        for validator in self.credential_validators:
            result = await validator.validate(config)
            all_issues.extend(result.issues)
        
        # Determine overall validity
        has_errors = any(issue.severity == ValidationSeverity.ERROR for issue in all_issues)
        
        final_result = ValidationResult(
            is_valid=not has_errors,
            issues=all_issues,
            provider_name=self.provider_name
        )
        
        # Log validation results
        if has_errors:
            logger.warning("Configuration validation failed for %s: %s", 
                         self.provider_name, final_result.get_error_summary())
        else:
            logger.info("Configuration validation passed for %s", self.provider_name)
            
        return final_result
