"""
Unit tests for the config/providers/base.py module.

Tests provider configuration components:
- RateLimitSettings
- ApiSettings
- BaseProviderSettings
- Validation logic
"""

import pytest
from pydantic import ValidationError

from config.constants import MessagePriority, Templates
from config.providers.base import (
    ApiSettings,
    BaseProviderSettings, 
    RateLimitSettings
)


# --- RateLimitSettings Tests ---

def test_rate_limit_settings_defaults():
    """Test default values for RateLimitSettings."""
    settings = RateLimitSettings()
    
    assert settings.rate_limit == 30
    assert settings.rate_period == 60
    assert settings.retry_attempts == 3  # Assuming API.DEFAULT_RETRIES is 3
    assert settings.retry_delay == 5     # Assuming API.DEFAULT_RETRY_DELAY is 5


def test_rate_limit_settings_custom():
    """Test custom values for RateLimitSettings."""
    settings = RateLimitSettings(
        rate_limit=45,
        rate_period=120,
        retry_attempts=2,
        retry_delay=10
    )
    
    assert settings.rate_limit == 45
    assert settings.rate_period == 120
    assert settings.retry_attempts == 2
    assert settings.retry_delay == 10


def test_rate_limit_settings_validation():
    """Test validation constraints on RateLimitSettings."""
    # Test minimum values
    with pytest.raises(ValidationError):
        RateLimitSettings(rate_limit=0)  # Below minimum 1
    
    with pytest.raises(ValidationError):
        RateLimitSettings(rate_period=29)  # Below minimum 30
    
    with pytest.raises(ValidationError):
        RateLimitSettings(retry_attempts=0)  # Below minimum 1
    
    with pytest.raises(ValidationError):
        RateLimitSettings(retry_delay=0)  # Below minimum 1
    
    # Test maximum values
    with pytest.raises(ValidationError):
        RateLimitSettings(rate_limit=61)  # Above maximum 60
    
    with pytest.raises(ValidationError):
        RateLimitSettings(rate_period=3601)  # Above maximum 3600
    
    with pytest.raises(ValidationError):
        RateLimitSettings(retry_attempts=6)  # Above maximum 5
    
    with pytest.raises(ValidationError):
        RateLimitSettings(retry_delay=31)  # Above maximum 30


def test_rate_limit_settings_frozen():
    """Test that RateLimitSettings is immutable (frozen)."""
    settings = RateLimitSettings()
    
    with pytest.raises(ValidationError):
        settings.rate_limit = 20  # Should be immutable


# --- ApiSettings Tests ---

def test_api_settings_defaults():
    """Test default values for ApiSettings."""
    settings = ApiSettings()
    
    assert settings.timeout == 30  # Assuming API.DEFAULT_TIMEOUT is 30
    assert settings.base_url is None
    assert settings.headers == {}


def test_api_settings_custom():
    """Test custom values for ApiSettings."""
    settings = ApiSettings(
        timeout=60,
        base_url="https://api.example.com",
        headers={"User-Agent": "TestAgent", "X-API-Key": "123456"}
    )
    
    assert settings.timeout == 60
    assert settings.base_url == "https://api.example.com"
    assert settings.headers == {"User-Agent": "TestAgent", "X-API-Key": "123456"}


def test_api_settings_validation():
    """Test validation constraints on ApiSettings."""
    # Test minimum values
    with pytest.raises(ValidationError):
        ApiSettings(timeout=0)  # Below minimum 1
    
    # Test maximum values
    with pytest.raises(ValidationError):
        ApiSettings(timeout=301)  # Above maximum 300
    
    # Test URL pattern validation
    with pytest.raises(ValidationError):
        ApiSettings(base_url="not-a-url")  # Missing http/https
    
    with pytest.raises(ValidationError):
        ApiSettings(base_url="ftp://example.com")  # Not http/https


def test_api_settings_header_validation():
    """Test header validation in ApiSettings."""
    # Valid headers
    valid_settings = ApiSettings(
        headers={
            "User-Agent": "TestAgent",
            "Content-Type": "application/json",
            "X-Custom-Header": "value"
        }
    )
    assert len(valid_settings.headers) == 3
    
    # Invalid header names
    with pytest.raises(ValueError, match="Invalid header names"):
        ApiSettings(headers={"": "Empty key not allowed"})
    
    # Test non-printable characters in header name
    with pytest.raises(ValueError):
        ApiSettings(headers={"Header\0Name": "Contains null character"})


def test_api_settings_frozen():
    """Test that ApiSettings is immutable (frozen)."""
    settings = ApiSettings()
    
    with pytest.raises(ValidationError):
        settings.timeout = 60  # Should be immutable


# --- BaseProviderSettings Tests ---

def test_base_provider_settings_defaults():
    """Test default values for BaseProviderSettings."""
    settings = BaseProviderSettings()
    
    assert settings.enabled is False
    assert settings.color_enabled is True
    assert isinstance(settings.rate_limit, RateLimitSettings)
    assert isinstance(settings.api_settings, ApiSettings)
    assert settings.message_template == Templates.DEFAULT_MESSAGE
    assert settings.message_priority == MessagePriority.NORMAL
    assert settings.notification_increment == 25  # Assumed default
    assert settings.tags == set()


def test_base_provider_settings_custom():
    """Test custom values for BaseProviderSettings."""
    # The message_template must contain at least one of the required placeholders
    # The validator checks extracted placeholders without curly braces
    settings = BaseProviderSettings(
        enabled=True,
        color_enabled=False,
        rate_limit=RateLimitSettings(rate_limit=50),
        api_settings=ApiSettings(timeout=45),
        # Use the default template which is guaranteed to be valid
        message_template=Templates.DEFAULT_MESSAGE,
        message_priority=MessagePriority.HIGH,
        notification_increment=10,
        tags={"status", "test", "mover"}
    )
    
    assert settings.enabled is True
    assert settings.color_enabled is False
    assert settings.rate_limit.rate_limit == 50
    assert settings.api_settings.timeout == 45
    assert settings.message_template == Templates.DEFAULT_MESSAGE
    assert settings.message_priority == MessagePriority.HIGH
    assert settings.notification_increment == 10
    assert settings.tags == {"status", "test", "mover"}


def test_base_provider_settings_template_validation():
    """Test message template validation in BaseProviderSettings."""
    # Use Templates.DEFAULT_MESSAGE as a reference for valid format
    assert "{percent}" in Templates.DEFAULT_MESSAGE
    assert "{remaining_data}" in Templates.DEFAULT_MESSAGE
    assert "{etc}" in Templates.DEFAULT_MESSAGE
    
    # Valid template with required placeholder
    valid_settings = BaseProviderSettings(
        message_template="Progress: {percent}% completed"
    )
    assert "percent" in BaseProviderSettings._extract_placeholders(valid_settings.message_template)
    
    # Valid template with different required placeholder
    valid_settings2 = BaseProviderSettings(
        message_template="Remaining: {remaining_data}"
    )
    assert "remaining_data" in BaseProviderSettings._extract_placeholders(valid_settings2.message_template)
    
    # Valid template with etc placeholder only
    valid_settings3 = BaseProviderSettings(
        message_template="Status update: {etc}"
    )
    assert "etc" in BaseProviderSettings._extract_placeholders(valid_settings3.message_template)
    
    # Invalid template with no required placeholders
    with pytest.raises(ValueError, match="Template must contain at least one of:"):
        BaseProviderSettings(message_template="No placeholders here")


def test_base_provider_settings_tags_validation():
    """Test tags validation in BaseProviderSettings."""
    # Tags are normalized (stripped, lowercased)
    settings = BaseProviderSettings(
        tags={"  Tag1  ", "TAG2", " tag3"}
    )
    assert settings.tags == {"tag1", "tag2", "tag3"}
    
    # Empty tags are removed
    settings = BaseProviderSettings(
        tags={"tag1", "", "  ", "tag2"}
    )
    assert settings.tags == {"tag1", "tag2"}


def test_base_provider_settings_to_provider_config():
    """Test conversion to provider configuration dictionary."""
    settings = BaseProviderSettings(
        enabled=True,
        color_enabled=False,
        message_priority=MessagePriority.HIGH,
        tags={"tag1", "tag2"}
    )
    
    config = settings.to_provider_config()
    
    assert config["enabled"] is True
    # Note that color_enabled might not be in the output
    assert "rate_limit" in config
    assert "api_settings" in config
    assert config["message_priority"] == "high"  # Enum converted to string
    assert sorted(config["tags"]) == ["tag1", "tag2"]  # Tags sorted


def test_base_provider_settings_extract_placeholders():
    """Test placeholder extraction from template string."""
    placeholders = BaseProviderSettings._extract_placeholders(
        "Template with {var1} and {var2} and {var3}"
    )
    assert placeholders == ["var1", "var2", "var3"]
    
    # Test with no placeholders
    placeholders = BaseProviderSettings._extract_placeholders(
        "Template with no placeholders"
    )
    assert placeholders == []
    
    # Test with repeated placeholders
    placeholders = BaseProviderSettings._extract_placeholders(
        "{var1} appears twice: {var1}"
    )
    assert placeholders == ["var1", "var1"] 