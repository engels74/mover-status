"""Property-based tests for sanitization invariants using Hypothesis.

These tests verify universal properties that should hold for all inputs to
sanitization functions, catching edge cases that example-based tests might miss.

Requirements tested:
    - 6.4: NO logging or exposure of secrets in error messages or diagnostic output
    - 6.5: Authentication failures logged WITHOUT including secret values
"""

from __future__ import annotations

from hypothesis import given, strategies as st

from mover_status.utils.sanitization import (
    REDACTED,
    sanitize_args,
    sanitize_exception,
    sanitize_mapping,
    sanitize_url,
    sanitize_value,
)


# Custom strategies for generating test data
@st.composite
def discord_webhook_url(draw: st.DrawFn) -> str:
    """Generate Discord webhook URLs with random tokens."""
    webhook_id = draw(st.integers(min_value=1, max_value=999999999999999999))
    token = draw(st.text(alphabet=st.characters(min_codepoint=65, max_codepoint=122), min_size=10, max_size=100))
    return f"https://discord.com/api/webhooks/{webhook_id}/{token}"


@st.composite
def telegram_bot_url(draw: st.DrawFn) -> str:
    """Generate Telegram bot API URLs with random tokens."""
    bot_id = draw(st.integers(min_value=1, max_value=9999999999))
    # Generate token with alphanumeric characters, hyphens, and underscores
    token = draw(st.text(alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_", min_size=35, max_size=50))
    method = draw(st.sampled_from(["sendMessage", "getMe", "sendPhoto"]))
    return f"https://api.telegram.org/bot{bot_id}:{token}/{method}"


class TestSanitizeUrlInvariants:
    """Property-based tests for URL sanitization invariants."""

    @given(discord_webhook_url())
    def test_discord_webhook_token_always_redacted(self, url: str) -> None:
        """Property: Discord webhook tokens are always redacted."""
        sanitized = sanitize_url(url)

        # Extract original token from URL
        parts = url.split("/")
        if len(parts) >= 6:
            original_token = parts[-1]
            # Token should not appear in sanitized output
            assert original_token not in sanitized
            # REDACTED marker should be present
            assert REDACTED in sanitized

    @given(telegram_bot_url())
    def test_telegram_bot_token_always_redacted(self, url: str) -> None:
        """Property: Telegram bot tokens are always redacted."""
        sanitized = sanitize_url(url)

        # Extract token from URL (format: /bot<ID>:<TOKEN>/method)
        if "/bot" in url:
            bot_part = url.split("/bot")[1].split("/")[0]
            if ":" in bot_part:
                token = bot_part.split(":")[1]
                # Token should not appear in sanitized output
                assert token not in sanitized
                # REDACTED marker should be present
                assert REDACTED in sanitized

    @given(st.text())
    def test_sanitize_url_never_crashes(self, url: str) -> None:
        """Property: sanitize_url never raises exceptions."""
        # Should handle any string input without crashing
        _ = sanitize_url(url)

    @given(st.text())
    def test_sanitize_url_returns_string(self, url: str) -> None:
        """Property: sanitize_url always returns a string for string input."""
        result = sanitize_url(url)
        assert isinstance(result, str)

    @given(st.text(alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd")), min_size=0, max_size=1000))
    def test_sanitize_url_idempotent_for_safe_urls(self, safe_text: str) -> None:
        """Property: Sanitizing safe URLs is idempotent."""
        # For URLs without webhook patterns, sanitization should not change them
        # (unless they match generic patterns)
        url = f"https://example.com/{safe_text}"
        first = sanitize_url(url)
        second = sanitize_url(first)
        # Sanitizing twice should give same result
        assert first == second


class TestSanitizeValueInvariants:
    """Property-based tests for value sanitization invariants."""

    @given(st.integers())
    def test_integers_pass_through(self, value: int) -> None:
        """Property: Integer values pass through unchanged."""
        assert sanitize_value(value) == value

    @given(st.floats(allow_nan=False, allow_infinity=False))
    def test_floats_pass_through(self, value: float) -> None:
        """Property: Float values pass through unchanged."""
        assert sanitize_value(value) == value

    @given(st.booleans())
    def test_booleans_pass_through(self, value: bool) -> None:
        """Property: Boolean values pass through unchanged."""
        assert sanitize_value(value) is value

    @given(st.none())
    def test_none_passes_through(self, value: None) -> None:
        """Property: None values pass through unchanged."""
        assert sanitize_value(value) is None

    @given(st.lists(st.integers()))
    def test_list_length_preserved(self, values: list[int]) -> None:
        """Property: List length is preserved after sanitization."""
        sanitized = sanitize_value(values)
        assert isinstance(sanitized, list)
        assert len(sanitized) == len(values)

    @given(st.dictionaries(st.text(min_size=1), st.integers()))
    def test_dict_keys_preserved(self, data: dict[str, int]) -> None:
        """Property: Dictionary keys are preserved after sanitization."""
        sanitized = sanitize_value(data)
        assert isinstance(sanitized, dict)
        assert set(sanitized.keys()) == set(data.keys())

    @given(st.tuples(st.integers(), st.text()))
    def test_tuple_type_preserved(self, data: tuple[int, str]) -> None:
        """Property: Tuple type is preserved after sanitization."""
        sanitized = sanitize_value(data)
        assert isinstance(sanitized, tuple)
        assert len(sanitized) == len(data)

    @given(st.recursive(
        st.integers() | st.text() | st.booleans() | st.none(),
        lambda children: st.lists(children) | st.dictionaries(st.text(min_size=1), children),
        max_leaves=20,
    ))
    def test_sanitize_never_crashes(self, data: object) -> None:
        """Property: sanitize_value never crashes on any recursive data structure."""
        # Should handle deeply nested structures without crashing
        _ = sanitize_value(data)

    @given(st.text())
    def test_sensitive_field_name_triggers_redaction(self, value: str) -> None:
        """Property: Sensitive field names always trigger redaction."""
        result = sanitize_value(value, field_name="api_token")
        assert result == REDACTED

        result = sanitize_value(value, field_name="password")
        assert result == REDACTED

        result = sanitize_value(value, field_name="webhook_url")
        assert result == REDACTED


class TestSanitizeArgsInvariants:
    """Property-based tests for args sanitization invariants."""

    @given(st.tuples(*[st.text() for _ in range(5)]))
    def test_args_length_preserved(self, args: tuple[str, ...]) -> None:
        """Property: Argument tuple length is preserved."""
        sanitized = sanitize_args(args)
        assert len(sanitized) == len(args)

    @given(st.tuples(st.integers(), st.floats(allow_nan=False), st.booleans()))
    def test_primitive_args_types_preserved(self, args: tuple[int, float, bool]) -> None:
        """Property: Primitive types in args are preserved."""
        sanitized = sanitize_args(args)
        assert isinstance(sanitized[0], int)
        assert isinstance(sanitized[1], float)
        assert isinstance(sanitized[2], bool)

    @given(st.tuples(*[st.one_of(st.integers(), st.text(), st.booleans()) for _ in range(10)]))
    def test_sanitize_args_never_crashes(self, args: tuple[object, ...]) -> None:
        """Property: sanitize_args never crashes."""
        _ = sanitize_args(args)


class TestSanitizeMappingInvariants:
    """Property-based tests for mapping sanitization invariants."""

    @given(st.dictionaries(st.text(min_size=1), st.integers()))
    def test_non_sensitive_mapping_values_preserved(self, data: dict[str, int]) -> None:
        """Property: Non-sensitive mappings with primitives preserve values."""
        # Filter out any keys that might be sensitive
        safe_data = {k: v for k, v in data.items() if not any(
            pattern in k.lower()
            for pattern in ["token", "key", "secret", "password", "auth", "webhook"]
        )}

        sanitized = sanitize_mapping(safe_data)
        # Values should be preserved for non-sensitive keys with primitive values
        for key, value in safe_data.items():
            assert sanitized.get(key) == value

    @given(st.dictionaries(st.text(min_size=1), st.text()))
    def test_sanitize_mapping_keys_preserved(self, data: dict[str, str]) -> None:
        """Property: Mapping keys are always preserved."""
        sanitized = sanitize_mapping(data)
        assert set(sanitized.keys()) == set(data.keys())

    @given(st.dictionaries(st.text(min_size=1), st.one_of(st.integers(), st.text(), st.lists(st.integers()))))
    def test_sanitize_mapping_never_crashes(self, data: dict[str, object]) -> None:
        """Property: sanitize_mapping never crashes."""
        _ = sanitize_mapping(data)


class TestSanitizeExceptionInvariants:
    """Property-based tests for exception sanitization invariants."""

    @given(st.text())
    def test_exception_type_in_output(self, message: str) -> None:
        """Property: Exception type name always appears in sanitized output."""
        exc = ValueError(message)
        sanitized = sanitize_exception(exc)
        assert "ValueError:" in sanitized

    @given(st.text())
    def test_runtime_error_type_preserved(self, message: str) -> None:
        """Property: RuntimeError type is identified in output."""
        exc = RuntimeError(message)
        sanitized = sanitize_exception(exc)
        assert "RuntimeError:" in sanitized

    @given(st.text())
    def test_sanitize_exception_never_crashes(self, message: str) -> None:
        """Property: sanitize_exception never crashes."""
        exc = Exception(message)
        _ = sanitize_exception(exc)

    @given(st.text())
    def test_sanitize_exception_returns_string(self, message: str) -> None:
        """Property: sanitize_exception always returns a string."""
        exc = Exception(message)
        result = sanitize_exception(exc)
        assert isinstance(result, str)


class TestSecurityInvariants:
    """Critical security properties that must always hold."""

    @given(discord_webhook_url())
    def test_discord_token_never_in_output(self, url: str) -> None:
        """Security invariant: Discord tokens NEVER appear in any sanitized output."""
        # Extract token
        parts = url.split("/")
        if len(parts) >= 6:
            token = parts[-1]

            # Test all sanitization functions
            assert token not in sanitize_url(url)
            assert token not in str(sanitize_value(url))
            assert token not in str(sanitize_value({"url": url}))
            assert token not in str(sanitize_args((url,)))

    @given(telegram_bot_url())
    def test_telegram_token_never_in_output(self, url: str) -> None:
        """Security invariant: Telegram tokens NEVER appear in any sanitized output."""
        # Extract token
        if "/bot" in url:
            bot_part = url.split("/bot")[1].split("/")[0]
            if ":" in bot_part:
                token = bot_part.split(":")[1]

                # Test all sanitization functions
                assert token not in sanitize_url(url)
                assert token not in str(sanitize_value(url))
                assert token not in str(sanitize_value({"endpoint": url}))
                assert token not in str(sanitize_args((url,)))

    @given(st.dictionaries(
        st.sampled_from(["api_token", "bot_token", "webhook_url", "api_key", "password"]),
        st.text(min_size=10),
    ))
    def test_sensitive_values_always_redacted(self, data: dict[str, str]) -> None:
        """Security invariant: Values for sensitive field names are ALWAYS redacted."""
        sanitized = sanitize_mapping(data)
        for key in data:
            # All sensitive field values should be redacted
            assert sanitized[key] == REDACTED

    @given(st.text(min_size=10))
    def test_password_field_always_redacted(self, password: str) -> None:
        """Security invariant: Password field is ALWAYS redacted."""
        result = sanitize_value(password, field_name="password")
        assert result == REDACTED
        assert password not in str(result)
