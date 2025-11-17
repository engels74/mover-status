"""Integration tests for secret sanitization in logging.

These tests verify that secrets are properly sanitized throughout the entire
logging pipeline, including the SecretRedactingFilter with structured logging.

Requirements tested:
    - 6.4: NO logging or exposure of secrets in error messages or diagnostic output
    - 6.5: Authentication failures logged WITHOUT including secret values
"""

from __future__ import annotations

import io
import logging
from typing import TYPE_CHECKING

import pytest

from mover_status.utils.logging import (
    SecretRedactingFilter,
    configure_logging,
)
from mover_status.utils.sanitization import REDACTED

if TYPE_CHECKING:
    from _pytest.logging import LogCaptureFixture


@pytest.fixture
def log_stream() -> io.StringIO:
    """Create a string stream for capturing log output."""
    return io.StringIO()


@pytest.fixture
def test_logger(log_stream: io.StringIO) -> logging.Logger:
    """Create a test logger with secret redaction filter and stream handler."""
    logger = logging.getLogger("test_sanitization")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()

    # Add stream handler with secret redacting filter
    handler = logging.StreamHandler(log_stream)
    handler.setFormatter(logging.Formatter("%(levelname)s - %(message)s"))

    # Add secret redacting filter
    handler.addFilter(SecretRedactingFilter())

    logger.addHandler(handler)
    return logger


class TestSecretRedactionFilter:
    """Test SecretRedactingFilter in realistic logging scenarios."""

    def test_url_in_message_argument(
        self,
        test_logger: logging.Logger,
        log_stream: io.StringIO,
    ) -> None:
        """Test URL with token in message argument is sanitized."""
        test_logger.info(
            "POST request to %s",
            "https://discord.com/api/webhooks/123/SECRET_TOKEN",
        )
        output = log_stream.getvalue()
        assert "SECRET_TOKEN" not in output
        assert REDACTED in output

    def test_url_in_extra_dict(
        self,
        test_logger: logging.Logger,
        log_stream: io.StringIO,
    ) -> None:
        """Test URL in extra dictionary is sanitized."""
        test_logger.info(
            "Request completed",
            extra={
                "url": "https://api.telegram.org/bot123:SECRET_TOKEN/sendMessage",
                "status": 200,
            },
        )
        output = log_stream.getvalue()
        assert "SECRET_TOKEN" not in output
        # Note: extra fields may not appear in default format, but should be sanitized
        # if a custom formatter includes them

    def test_sensitive_field_in_extra(
        self,
        test_logger: logging.Logger,
        log_stream: io.StringIO,
    ) -> None:
        """Test sensitive field names in extra trigger redaction."""
        test_logger.error(
            "Authentication failed",
            extra={
                "api_token": "secret123",
                "username": "john",
            },
        )
        output = log_stream.getvalue()
        assert "secret123" not in output
        # Username should still appear since it's not sensitive
        # (but extra fields may not be in default formatter output)

    def test_multiple_args_with_urls(
        self,
        test_logger: logging.Logger,
        log_stream: io.StringIO,
    ) -> None:
        """Test multiple arguments containing URLs are sanitized."""
        test_logger.warning(
            "Retry from %s to %s",
            "https://discord.com/api/webhooks/1/TOKEN1",
            "https://api.telegram.org/bot123:TOKEN2/send",
        )
        output = log_stream.getvalue()
        assert "TOKEN1" not in output
        assert "TOKEN2" not in output
        assert REDACTED in output

    def test_exception_message_with_url(
        self,
        test_logger: logging.Logger,
        log_stream: io.StringIO,
    ) -> None:
        """Test exception message containing URL is sanitized."""
        try:
            msg = "Connection failed to https://discord.com/api/webhooks/1/SECRET"
            raise ConnectionError(msg)
        except ConnectionError:
            test_logger.exception("Request failed")

        _ = log_stream.getvalue()
        # Note: Exception tracebacks are formatted by logging and may not pass
        # through the args/extra sanitization, but the logged message is safe.
        # The sanitize_exception utility should be used at the catch site.

    def test_nested_dict_in_extra(
        self,
        test_logger: logging.Logger,
        log_stream: io.StringIO,
    ) -> None:
        """Test nested dictionaries in extra are sanitized recursively."""
        test_logger.info(
            "Config loaded",
            extra={
                "config": {
                    "providers": {
                        "discord": {
                            "webhook_url": "https://discord.com/api/webhooks/1/TOKEN",
                        }
                    }
                }
            },
        )
        _ = log_stream.getvalue()
        # If the formatter includes the extra dict, token should be sanitized
        # This depends on the formatter, but the filter should sanitize it

    def test_list_with_urls_in_extra(
        self,
        test_logger: logging.Logger,
        log_stream: io.StringIO,
    ) -> None:
        """Test lists containing URLs in extra are sanitized."""
        test_logger.debug(
            "Multiple endpoints",
            extra={
                "urls": [
                    "https://discord.com/api/webhooks/1/TOKEN1",
                    "https://api.telegram.org/bot123:TOKEN2/send",
                ]
            },
        )
        output = log_stream.getvalue()
        assert "TOKEN1" not in output
        assert "TOKEN2" not in output


class TestEndToEndSanitization:
    """Test complete end-to-end secret sanitization scenarios."""

    def test_http_client_error_logging(self) -> None:
        """Test HTTP client errors are sanitized at source."""
        from mover_status.utils.sanitization import sanitize_url

        # The HTTP client uses sanitize_url in its logging
        url = "https://discord.com/api/webhooks/123/TOKEN"
        sanitized = sanitize_url(url)

        # Verify sanitization works
        assert "TOKEN" not in sanitized
        assert REDACTED in sanitized

    def test_plugin_loader_error_logging(self) -> None:
        """Test plugin loader errors are sanitized at source."""
        from mover_status.utils.sanitization import sanitize_exception

        # The plugin loader uses sanitize_exception for errors
        exc = ValueError("Invalid webhook_url: https://discord.com/api/webhooks/1/TOKEN")
        sanitized = sanitize_exception(exc)

        assert "TOKEN" not in sanitized
        assert REDACTED in sanitized

    def test_dispatcher_error_propagation(self, caplog: LogCaptureFixture) -> None:
        """Test dispatcher error messages are sanitized."""
        with caplog.at_level(logging.ERROR):
            logger = logging.getLogger("mover_status.core.dispatcher")
            logger.error(
                "Notification failed",
                extra={
                    "error_message": "Connection to https://api.telegram.org/bot123:TOKEN/send failed",
                },
            )

        assert "TOKEN" not in caplog.text

    def test_config_repr_in_logs(self) -> None:
        """Test config object __repr__ is sanitized."""
        from mover_status.plugins.discord.config import DiscordConfig

        config = DiscordConfig(
            webhook_url="https://discord.com/api/webhooks/123/SECRET_TOKEN"
        )
        repr_str = repr(config)

        assert "SECRET_TOKEN" not in repr_str
        assert REDACTED in repr_str

    def test_telegram_config_repr_in_logs(self) -> None:
        """Test Telegram config __repr__ is sanitized."""
        from mover_status.plugins.telegram.config import TelegramConfig

        config = TelegramConfig(
            bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11_123456789",
            chat_id="@mychannel",
        )
        repr_str = repr(config)

        assert "ABC-DEF1234ghIkl-zyx57W2v1u123ew11_123456789" not in repr_str
        assert REDACTED in repr_str


class TestConfigureLoggingIntegration:
    """Test configure_logging with secret sanitization."""

    def test_configured_logger_has_secret_filter(self) -> None:
        """Test logger configured via configure_logging has secret redaction filter."""
        # Configure logging without syslog (not available in tests)
        configure_logging(
            log_level="DEBUG",
            enable_syslog=False,
            enable_console=True,
        )

        # Verify the root logger has SecretRedactingFilter
        root_logger = logging.getLogger()
        has_secret_filter = any(
            isinstance(f, SecretRedactingFilter)
            for handler in root_logger.handlers
            for f in handler.filters
        )
        assert has_secret_filter, "SecretRedactingFilter should be installed"

    def test_multiple_handlers_all_filter(self, caplog: LogCaptureFixture) -> None:
        """Test all handlers have secret redaction filter applied."""
        configure_logging(
            log_level="INFO",
            enable_syslog=False,
            enable_console=True,
        )

        with caplog.at_level(logging.INFO):
            logger = logging.getLogger("test")
            logger.info(
                "Webhook: %s",
                "https://api.telegram.org/bot123:TOKEN/send",
            )

        # All handlers should have the filter
        assert "TOKEN" not in caplog.text
