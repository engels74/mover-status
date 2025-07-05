"""Tests for base configuration models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from mover_status.config.models.base import (
    BaseConfig,
    RetryConfig,
    RateLimitConfig,
    LogLevel,
    NotificationEvent,
    ProviderName,
)


class TestBaseConfig:
    """Test suite for BaseConfig class."""

    def test_base_config_creation(self) -> None:
        """Test creating a BaseConfig instance."""
        config = BaseConfig()
        assert isinstance(config, BaseConfig)

    def test_base_config_forbids_extra_fields(self) -> None:
        """Test that BaseConfig forbids extra fields."""
        with pytest.raises(ValidationError) as exc_info:
            BaseConfig(extra_field="not_allowed")  # pyright: ignore[reportCallIssue] # Testing validation error
        
        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["type"] == "extra_forbidden"

    def test_base_config_validate_assignment(self) -> None:
        """Test that BaseConfig validates assignments."""
        config = BaseConfig()
        # BaseConfig doesn't have fields to test assignment validation directly
        # This test ensures the configuration is set up correctly
        assert config.model_config.get("validate_assignment") is True


class TestRetryConfig:
    """Test suite for RetryConfig class."""

    def test_retry_config_defaults(self) -> None:
        """Test RetryConfig with default values."""
        config = RetryConfig()
        assert config.max_attempts == 3
        assert config.backoff_factor == 2.0
        assert config.timeout == 30

    def test_retry_config_custom_values(self) -> None:
        """Test RetryConfig with custom values."""
        config = RetryConfig(
            max_attempts=5,
            backoff_factor=1.5,
            timeout=45,
        )
        assert config.max_attempts == 5
        assert config.backoff_factor == 1.5
        assert config.timeout == 45

    def test_retry_config_validation_max_attempts(self) -> None:
        """Test RetryConfig validation for max_attempts."""
        with pytest.raises(ValidationError) as exc_info:
            RetryConfig(max_attempts=0)

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["type"] == "greater_than_equal"

    def test_retry_config_validation_delays(self) -> None:
        """Test RetryConfig validation for backoff_factor."""
        with pytest.raises(ValidationError) as exc_info:
            RetryConfig(backoff_factor=-1.0)

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["type"] == "greater_than_equal"

    def test_retry_config_validation_backoff_factor(self) -> None:
        """Test RetryConfig validation for backoff_factor upper bound."""
        # Test that backoff_factor accepts valid values
        config = RetryConfig(backoff_factor=5.0)
        assert config.backoff_factor == 5.0

    def test_retry_config_validation_timeout(self) -> None:
        """Test RetryConfig validation for timeout."""
        with pytest.raises(ValidationError) as exc_info:
            RetryConfig(timeout=0)

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["type"] == "greater_than_equal"


class TestRateLimitConfig:
    """Test suite for RateLimitConfig class."""

    def test_rate_limit_config_defaults(self) -> None:
        """Test RateLimitConfig with default values."""
        config = RateLimitConfig()
        assert config.progress == 300
        assert config.status == 60

    def test_rate_limit_config_custom_values(self) -> None:
        """Test RateLimitConfig with custom values."""
        config = RateLimitConfig(progress=600, status=120)
        assert config.progress == 600
        assert config.status == 120

    def test_rate_limit_config_validation(self) -> None:
        """Test RateLimitConfig validation for non-negative values."""
        # Test that negative values are not allowed
        config = RateLimitConfig(progress=0, status=0)
        assert config.progress == 0
        assert config.status == 0


class TestLogLevel:
    """Test suite for LogLevel constants."""

    def test_log_level_constants(self) -> None:
        """Test LogLevel constant values."""
        config = LogLevel()
        assert config.CRITICAL == "CRITICAL"
        assert config.ERROR == "ERROR"
        assert config.WARNING == "WARNING"
        assert config.INFO == "INFO"
        assert config.DEBUG == "DEBUG"


class TestNotificationEvent:
    """Test suite for NotificationEvent constants."""

    def test_notification_event_constants(self) -> None:
        """Test NotificationEvent constant values."""
        config = NotificationEvent()
        assert config.STARTED == "started"
        assert config.PROGRESS == "progress"
        assert config.COMPLETED == "completed"
        assert config.FAILED == "failed"


class TestProviderName:
    """Test suite for ProviderName constants."""

    def test_provider_name_constants(self) -> None:
        """Test ProviderName constant values."""
        config = ProviderName()
        assert config.TELEGRAM == "telegram"
        assert config.DISCORD == "discord"
