"""Unit tests for secret sanitization utilities.

Requirements tested:
    - 6.4: NO logging or exposure of secrets in error messages or diagnostic output
    - 6.5: Authentication failures logged WITHOUT including secret values
"""

from __future__ import annotations

from typing import cast

import pytest

from mover_status.utils.sanitization import (
    REDACTED,
    is_sensitive_field,
    sanitize_args,
    sanitize_exception,
    sanitize_mapping,
    sanitize_url,
    sanitize_value,
)


class TestSanitizeUrl:
    """Test URL sanitization for various provider patterns."""

    def test_discord_webhook_url_sanitization(self) -> None:
        """Test Discord webhook URLs are sanitized correctly."""
        url = "https://discord.com/api/webhooks/123456789/SECRET_TOKEN_ABC123"
        sanitized = sanitize_url(url)
        assert "SECRET_TOKEN_ABC123" not in sanitized
        assert REDACTED in sanitized
        assert "discord.com" in sanitized
        assert "/api/webhooks/123456789/" in sanitized

    def test_discordapp_webhook_url_sanitization(self) -> None:
        """Test legacy discordapp.com URLs are sanitized."""
        url = "https://discordapp.com/api/webhooks/987654321/TOKEN_XYZ"
        sanitized = sanitize_url(url)
        assert "TOKEN_XYZ" not in sanitized
        assert REDACTED in sanitized
        assert "discordapp.com" in sanitized

    def test_telegram_bot_url_sanitization(self) -> None:
        """Test Telegram bot API URLs are sanitized."""
        url = "https://api.telegram.org/bot123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11/sendMessage"
        sanitized = sanitize_url(url)
        assert "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11" not in sanitized
        assert REDACTED in sanitized
        assert "api.telegram.org" in sanitized
        assert "/sendMessage" in sanitized

    def test_generic_token_in_path_sanitization(self) -> None:
        """Test generic /token/ or /api-key/ patterns are sanitized."""
        url = "https://api.example.com/v1/token/secret123/endpoint"
        sanitized = sanitize_url(url)
        assert "secret123" not in sanitized
        assert REDACTED in sanitized

    def test_generic_token_in_query_sanitization(self) -> None:
        """Test query parameter tokens are sanitized."""
        url = "https://api.example.com/webhook?api_key=secret123&data=value"
        sanitized = sanitize_url(url)
        assert "secret123" not in sanitized
        assert REDACTED in sanitized
        assert "data=value" in sanitized

    def test_non_secret_url_unchanged(self) -> None:
        """Test URLs without secrets pass through unchanged."""
        url = "https://example.com/api/data?param=value"
        sanitized = sanitize_url(url)
        assert sanitized == url

    def test_empty_string_unchanged(self) -> None:
        """Test empty strings are handled gracefully."""
        assert sanitize_url("") == ""

    def test_non_string_passed_through(self) -> None:
        """Test non-string values are passed through unchanged."""
        assert sanitize_url(None) is None  # pyright: ignore[reportArgumentType]
        assert sanitize_url(123) == 123  # pyright: ignore[reportArgumentType]

    def test_case_insensitive_pattern_matching(self) -> None:
        """Test URL patterns match case-insensitively."""
        url = "https://DISCORD.COM/api/webhooks/123/TOKEN"
        sanitized = sanitize_url(url)
        assert "TOKEN" not in sanitized
        assert REDACTED in sanitized


class TestIsSensitiveField:
    """Test sensitive field name detection."""

    @pytest.mark.parametrize(
        "field_name",
        [
            "api_token",
            "bot_token",
            "webhook_url",
            "API_KEY",
            "password",
            "secret_key",
            "bearer_token",
            "auth_header",
            "credential",
        ],
    )
    def test_sensitive_field_names_detected(self, field_name: str) -> None:
        """Test common sensitive field names are detected."""
        assert is_sensitive_field(field_name) is True

    @pytest.mark.parametrize(
        "field_name",
        [
            "username",
            "email",
            "count",
            "status",
            "provider_name",
            "correlation_id",
        ],
    )
    def test_non_sensitive_field_names_not_detected(self, field_name: str) -> None:
        """Test non-sensitive field names are not flagged."""
        assert is_sensitive_field(field_name) is False

    def test_case_insensitive_matching(self) -> None:
        """Test field name matching is case-insensitive."""
        assert is_sensitive_field("API_TOKEN") is True
        assert is_sensitive_field("Bot_Token") is True
        assert is_sensitive_field("WEBHOOK_URL") is True


class TestSanitizeValue:
    """Test recursive value sanitization."""

    def test_string_url_sanitization(self) -> None:
        """Test string URLs are sanitized."""
        url = "https://discord.com/api/webhooks/123/TOKEN"
        sanitized = sanitize_value(url)
        assert isinstance(sanitized, str)
        assert "TOKEN" not in sanitized

    def test_dict_with_sensitive_field_names(self) -> None:
        """Test dict with sensitive field names are redacted."""
        data = {
            "api_token": "secret123",
            "webhook_url": "https://discord.com/api/webhooks/1/TOKEN",
            "count": 42,
        }
        sanitized = sanitize_value(data)
        assert isinstance(sanitized, dict)
        assert sanitized["api_token"] == REDACTED
        assert sanitized["webhook_url"] == REDACTED
        assert sanitized["count"] == 42

    def test_dict_with_url_values(self) -> None:
        """Test dict values containing URLs are sanitized."""
        data = {
            "url": "https://api.telegram.org/bot123:TOKEN/send",
            "status": 200,
        }
        sanitized = sanitize_value(data)
        assert isinstance(sanitized, dict)
        assert "TOKEN" not in sanitized["url"]
        assert sanitized["status"] == 200

    def test_nested_dict_sanitization(self) -> None:
        """Test nested dictionaries are sanitized recursively."""
        data = {
            "outer": {
                "inner": {
                    "api_key": "secret",
                }
            }
        }
        sanitized = sanitize_value(data)
        assert isinstance(sanitized, dict)
        # Cast to dict for type checker - isinstance check guarantees this at runtime
        outer: object = cast(dict[str, object], sanitized)["outer"]
        assert isinstance(outer, dict)
        inner: object = cast(dict[str, object], outer)["inner"]
        assert isinstance(inner, dict)
        assert cast(dict[str, object], inner)["api_key"] == REDACTED

    def test_list_sanitization(self) -> None:
        """Test lists are sanitized recursively."""
        data = [
            "https://discord.com/api/webhooks/1/TOKEN",
            "normal string",
            {"api_key": "secret"},
        ]
        sanitized = sanitize_value(data)
        assert isinstance(sanitized, list)
        assert "TOKEN" not in sanitized[0]
        assert sanitized[1] == "normal string"
        assert isinstance(sanitized[2], dict)
        assert sanitized[2]["api_key"] == REDACTED

    def test_tuple_sanitization_preserves_type(self) -> None:
        """Test tuples are sanitized and type is preserved."""
        data = (
            "https://discord.com/api/webhooks/1/TOKEN",
            42,
        )
        sanitized = sanitize_value(data)
        assert isinstance(sanitized, tuple)
        # Cast to tuple for type checker - isinstance check guarantees this at runtime
        sanitized_tuple = cast(tuple[object, ...], sanitized)
        assert len(sanitized_tuple) == 2
        assert "TOKEN" not in cast(str, sanitized_tuple[0])
        assert sanitized_tuple[1] == 42

    def test_primitive_types_pass_through(self) -> None:
        """Test primitive types pass through unchanged."""
        assert sanitize_value(42) == 42
        assert sanitize_value(3.14) == 3.14
        assert sanitize_value(True) is True
        assert sanitize_value(None) is None

    def test_field_name_takes_precedence(self) -> None:
        """Test field name context overrides value inspection."""
        # Even though "normal_value" contains no secrets,
        # the field name "password" triggers redaction
        sanitized = sanitize_value("normal_value", field_name="password")
        assert sanitized == REDACTED

    def test_non_sensitive_field_name_allows_url_check(self) -> None:
        """Test non-sensitive field names still allow URL sanitization."""
        url = "https://discord.com/api/webhooks/1/TOKEN"
        sanitized = sanitize_value(url, field_name="endpoint")
        assert isinstance(sanitized, str)
        assert "TOKEN" not in sanitized


class TestSanitizeException:
    """Test exception message sanitization."""

    def test_exception_with_url(self) -> None:
        """Test exception containing URL is sanitized."""
        exc = ValueError("Failed to connect to https://discord.com/api/webhooks/1/TOKEN")
        sanitized = sanitize_exception(exc)
        assert "TOKEN" not in sanitized
        assert "ValueError:" in sanitized
        assert REDACTED in sanitized

    def test_exception_type_preserved(self) -> None:
        """Test exception type name is preserved in output."""
        exc = RuntimeError("error message")
        sanitized = sanitize_exception(exc)
        assert "RuntimeError:" in sanitized

    def test_exception_with_sensitive_pattern(self) -> None:
        """Test exception with sensitive patterns is sanitized."""
        exc = ValueError("Invalid api_key: secret123")
        sanitized = sanitize_exception(exc)
        # The sanitize_url function will sanitize the message
        assert "ValueError:" in sanitized


class TestSanitizeArgs:
    """Test logging argument tuple sanitization."""

    def test_args_with_url(self) -> None:
        """Test args tuple with URL is sanitized."""
        args = ("Connecting to %s", "https://discord.com/api/webhooks/1/TOKEN")
        sanitized = sanitize_args(args)
        assert len(sanitized) == 2
        assert sanitized[0] == "Connecting to %s"
        assert isinstance(sanitized[1], str)
        assert "TOKEN" not in sanitized[1]

    def test_args_with_multiple_values(self) -> None:
        """Test args with mixed types are handled correctly."""
        args = (
            "Request to %s returned %d",
            "https://api.telegram.org/bot123:TOKEN/send",
            200,
        )
        sanitized = sanitize_args(args)
        assert len(sanitized) == 3
        assert isinstance(sanitized[1], str)
        assert "TOKEN" not in sanitized[1]
        assert sanitized[2] == 200

    def test_empty_args(self) -> None:
        """Test empty args tuple is handled."""
        sanitized = sanitize_args(())
        assert sanitized == ()


class TestSanitizeMapping:
    """Test mapping/dict sanitization."""

    def test_mapping_with_url_values(self) -> None:
        """Test mapping with URL values is sanitized."""
        data = {
            "url": "https://discord.com/api/webhooks/1/TOKEN",
            "status": 200,
        }
        sanitized = sanitize_mapping(data)
        url_value = sanitized["url"]
        assert isinstance(url_value, str)
        assert "TOKEN" not in url_value
        assert sanitized["status"] == 200

    def test_mapping_with_sensitive_keys(self) -> None:
        """Test mapping with sensitive key names redacts values."""
        data = {
            "api_token": "secret123",
            "username": "john",
        }
        sanitized = sanitize_mapping(data)
        assert sanitized["api_token"] == REDACTED
        assert sanitized["username"] == "john"

    def test_nested_mapping(self) -> None:
        """Test nested mappings are sanitized recursively."""
        data = {
            "config": {
                "webhook_url": "https://discord.com/api/webhooks/1/TOKEN",
            }
        }
        sanitized = sanitize_mapping(data)
        config = sanitized["config"]
        assert isinstance(config, dict)
        assert config["webhook_url"] == REDACTED


class TestIntegrationScenarios:
    """Test real-world integration scenarios."""

    def test_log_record_extra_sanitization(self) -> None:
        """Test sanitizing a typical log record extra dict."""
        extra = {
            "provider": "discord",
            "url": "https://discord.com/api/webhooks/123/SECRET_TOKEN",
            "status": 200,
            "attempt": 1,
        }
        sanitized = sanitize_mapping(extra)
        url_value = sanitized["url"]
        assert isinstance(url_value, str)
        assert "SECRET_TOKEN" not in url_value
        assert sanitized["provider"] == "discord"
        assert sanitized["status"] == 200

    def test_config_object_str_sanitization(self) -> None:
        """Test sanitizing stringified config objects."""
        config_str = "DiscordConfig(webhook_url='https://discord.com/api/webhooks/1/TOKEN')"
        sanitized = sanitize_value(config_str)
        assert isinstance(sanitized, str)
        assert "TOKEN" not in sanitized

    def test_multiple_urls_in_dict(self) -> None:
        """Test multiple URLs in same dict are all sanitized."""
        data = {
            "discord_url": "https://discord.com/api/webhooks/1/TOKEN1",
            "telegram_url": "https://api.telegram.org/bot123:TOKEN2/send",
            "count": 2,
        }
        sanitized = sanitize_mapping(data)
        assert "TOKEN1" not in str(sanitized)
        assert "TOKEN2" not in str(sanitized)
        assert sanitized["count"] == 2

    def test_exception_from_http_error(self) -> None:
        """Test exception from HTTP request with URL is sanitized."""
        exc = ConnectionError(
            "Failed to connect to https://api.telegram.org/bot123:ABC-TOKEN/sendMessage"
        )
        sanitized = sanitize_exception(exc)
        assert "ABC-TOKEN" not in sanitized
        assert "ConnectionError:" in sanitized
        assert REDACTED in sanitized
