"""
Tests for the Template notification provider.

This module contains tests for the Template notification provider template,
including the provider structure, configuration schema, and documentation.
These tests serve as examples for testing new notification providers.
"""

from unittest.mock import patch, MagicMock

from mover_status.notification.formatter import RawValues


class TestTemplateProviderStructure:
    """Test cases for template provider structure."""

    def test_template_provider_structure(self) -> None:
        """Test that template provider follows the correct structure and inheritance."""
        # This test will fail until we implement the template provider
        from mover_status.notification.providers.template.provider import TemplateProvider
        from mover_status.notification.providers.base_provider import BaseProvider

        # Verify inheritance hierarchy
        assert issubclass(TemplateProvider, BaseProvider)

        # Test provider can be instantiated with valid config
        config = {
            "enabled": True,
            "api_endpoint": "https://api.example.com/webhook",
            "api_key": "test_key_123",
            "message_template": "Test message: {percent}% complete"
        }

        provider = TemplateProvider("template", config)

        # Verify basic properties
        assert provider.name == "template"
        assert provider.enabled is True
        assert hasattr(provider, 'api_endpoint')
        assert hasattr(provider, 'api_key')
        assert hasattr(provider, 'message_template')

        # Verify required methods are implemented
        assert hasattr(provider, 'send_notification')
        assert hasattr(provider, 'validate_config')
        assert hasattr(provider, '_send_notification_impl')

        # Test configuration validation
        errors = provider.validate_config()
        assert isinstance(errors, list)

    def test_template_provider_inheritance_pattern(self) -> None:
        """Test that template provider demonstrates proper inheritance patterns."""
        from mover_status.notification.providers.template.provider import TemplateProvider

        # Template should demonstrate API pattern inheritance

        # Test API-based template
        config_api = {
            "enabled": True,
            "api_endpoint": "https://api.example.com/send",
            "api_key": "test_key",
            "message_template": "API message: {percent}%"
        }

        api_provider = TemplateProvider("template_api", config_api)

        # Should inherit from ApiProvider and demonstrate API pattern
        assert hasattr(api_provider, '_prepare_request_data')
        assert hasattr(api_provider, '_send_api_request')

    def test_template_provider_configuration_handling(self) -> None:
        """Test that template provider properly handles configuration."""
        from mover_status.notification.providers.template.provider import TemplateProvider

        # Test with minimal config
        minimal_config = {"enabled": False}
        provider = TemplateProvider("template", minimal_config)
        assert provider.enabled is False

        # Test with full config
        full_config = {
            "enabled": True,
            "api_endpoint": "https://api.example.com/webhook",
            "api_key": "test_key_123",
            "message_template": "Progress: {percent}% - ETA: {etc}",
            "timeout": 30,
            "retry_attempts": 3,
            "custom_headers": {"User-Agent": "MoverStatus/1.0"}
        }

        provider = TemplateProvider("template", full_config)
        assert provider.enabled is True
        assert provider.timeout == 30
        assert hasattr(provider, 'retry_attempts')


class TestTemplateConfigurationSchema:
    """Test cases for template configuration schema."""

    def test_template_configuration_schema(self) -> None:
        """Test that template configuration schema is properly defined."""
        from mover_status.notification.providers.template.config import (
            get_template_schema,
            validate_template_config,
            TEMPLATE_SCHEMA_NAME
        )

        # Test schema creation
        schema = get_template_schema()
        assert schema.name == TEMPLATE_SCHEMA_NAME
        assert len(schema.fields) > 0

        # Test schema has required fields
        field_names = list(schema.fields.keys())
        assert "enabled" in field_names
        assert "api_endpoint" in field_names
        assert "api_key" in field_names
        assert "message_template" in field_names

        # Test configuration validation
        valid_config: dict[str, object] = {
            "enabled": True,
            "api_endpoint": "https://api.example.com/webhook",
            "api_key": "test_key",
            "message_template": "Test: {percent}%"
        }

        validated_config = validate_template_config(valid_config)
        assert validated_config["enabled"] is True
        assert validated_config["api_endpoint"] == "https://api.example.com/webhook"

    def test_template_configuration_defaults(self) -> None:
        """Test that template configuration defaults are properly defined."""
        from mover_status.notification.providers.template.defaults import TEMPLATE_DEFAULTS

        # Test defaults structure
        assert isinstance(TEMPLATE_DEFAULTS, dict)
        assert "name" in TEMPLATE_DEFAULTS
        assert "enabled" in TEMPLATE_DEFAULTS
        assert TEMPLATE_DEFAULTS["name"] == "template"
        assert TEMPLATE_DEFAULTS["enabled"] is False

        # Test default values are reasonable
        assert "api_endpoint" in TEMPLATE_DEFAULTS
        assert "api_key" in TEMPLATE_DEFAULTS
        assert "message_template" in TEMPLATE_DEFAULTS

        # Test message template has placeholders
        template = TEMPLATE_DEFAULTS["message_template"]
        assert "{percent}" in template
        assert "{etc}" in template or "{eta}" in template

    def test_template_configuration_validation_errors(self) -> None:
        """Test that template configuration validation catches errors."""
        from mover_status.notification.providers.template.config import validate_template_config
        from mover_status.config.schema import SchemaValidationError

        # Test missing required fields
        invalid_config: dict[str, object] = {"enabled": True}  # Missing api_endpoint and api_key

        try:
            _ = validate_template_config(invalid_config)
            assert False, "Should have raised SchemaValidationError"
        except SchemaValidationError as e:
            assert "api_endpoint" in str(e) or "api_key" in str(e)


class TestTemplateDocumentation:
    """Test cases for template documentation."""

    def test_template_documentation(self) -> None:
        """Test that template has comprehensive documentation."""
        from mover_status.notification.providers.template import provider
        from mover_status.notification.providers.template import formatter
        from mover_status.notification.providers.template import config
        from mover_status.notification.providers.template import defaults

        # Test module docstrings exist
        assert provider.__doc__ is not None
        assert formatter.__doc__ is not None
        assert config.__doc__ is not None
        assert defaults.__doc__ is not None

        # Test class docstrings
        from mover_status.notification.providers.template.provider import TemplateProvider
        assert TemplateProvider.__doc__ is not None
        assert "template" in TemplateProvider.__doc__.lower()

    def test_template_examples_and_usage(self) -> None:
        """Test that template includes usage examples."""
        from mover_status.notification.providers.template.provider import TemplateProvider

        # Test that the template can be used as an example
        example_config = {
            "enabled": True,
            "api_endpoint": "https://api.example.com/webhook",
            "api_key": "your_api_key_here",
            "message_template": "Mover Progress: {percent}% complete. ETA: {etc}"
        }

        provider = TemplateProvider("example", example_config)

        # Test that it can handle a mock notification
        with patch('requests.post') as mock_post:
            mock_response = MagicMock()
            mock_response.raise_for_status.return_value = None  # pyright: ignore[reportAny]
            mock_post.return_value = mock_response

            raw_values: RawValues = {
                "percent": 75,
                "eta": 1234567890.0,
                "remaining_bytes": 1024 * 1024 * 500,  # 500MB
            }

            result = provider.send_notification("Test message", raw_values=raw_values)
            assert isinstance(result, bool)

    def test_template_formatter_functions(self) -> None:
        """Test that template formatter functions are documented and functional."""
        from mover_status.notification.providers.template.formatter import (
            format_template_message,
            format_template_eta
        )

        # Test formatter functions exist and are callable
        assert callable(format_template_message)
        assert callable(format_template_eta)

        # Test basic formatting functionality
        raw_values: RawValues = {
            "percent": 50,
            "eta": 1234567890.0,
            "remaining_bytes": 1024 * 1024 * 100,
        }

        template = "Progress: {percent}% - ETA: {etc}"
        formatted = format_template_message(template, raw_values)
        assert "50%" in formatted
        assert "ETA:" in formatted


class TestTemplateProviderIntegration:
    """Test cases for template provider integration with the system."""

    def test_template_provider_registration(self) -> None:
        """Test that template provider can be registered with the system."""
        from mover_status.notification.providers.template import TemplateProvider
        from mover_status.notification.registry import ProviderRegistry

        # Test provider can be registered
        registry = ProviderRegistry()

        # Create a template provider instance with metadata
        config = {
            "enabled": True,
            "api_endpoint": "https://api.example.com/webhook",
            "api_key": "test_key"
        }

        metadata = {
            "version": "1.0.0",
            "description": "Template notification provider for development reference",
            "author": "MoverStatus Team"
        }

        provider_instance = TemplateProvider("template", config, metadata)

        # Register the provider instance
        registry.register_provider("template", provider_instance)

        # Verify registration
        providers = registry.get_registered_providers()
        assert "template" in providers
        assert isinstance(providers["template"], TemplateProvider)
        assert providers["template"].name == "template"
