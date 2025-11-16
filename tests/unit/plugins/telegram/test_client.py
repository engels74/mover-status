"""Tests for the Telegram API client."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal, cast

import pytest

from mover_status.plugins.telegram.client import (
    TelegramAPIClient,
    TelegramAPIError,
    TelegramBotBlockedError,
    TelegramChatNotFoundError,
)
from mover_status.plugins.telegram.config import TelegramConfig
from mover_status.types.models import Response
from mover_status.types.protocols import HTTPClient


def _make_telegram_config(
    *,
    bot_token: str = "123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi",
    chat_id: str = "@moverstatus",
    parse_mode: Literal["HTML", "Markdown", "MarkdownV2"] | None = "HTML",
    message_thread_id: int | None = None,
    disable_notification: bool = False,
) -> TelegramConfig:
    """Factory for consistent Telegram configuration objects."""
    return TelegramConfig(
        bot_token=bot_token,
        chat_id=chat_id,
        parse_mode=parse_mode,
        message_thread_id=message_thread_id,
        disable_notification=disable_notification,
    )


def _success_response() -> Response:
    """Create a default successful Telegram API response."""
    return Response(
        status=200,
        body={"ok": True, "result": {"message_id": 100}},
        headers={},
    )


class FakeHTTPClient:
    """Fake HTTP client that captures request metadata."""

    def __init__(
        self,
        *,
        response: Response | None = None,
        exception: BaseException | None = None,
    ) -> None:
        self._response: Response = response or _success_response()
        self._exception: BaseException | None = exception
        self.last_url: str | None = None
        self.last_payload: Mapping[str, object] | None = None
        self.last_timeout: float | None = None

    async def post(
        self,
        url: str,
        payload: Mapping[str, object],
        *,
        timeout: float,
    ) -> Response:
        self.last_url = url
        self.last_payload = payload
        self.last_timeout = timeout
        if self._exception is not None:
            raise self._exception
        return self._response

    async def post_with_retry(
        self,
        _url: str,
        _payload: Mapping[str, object],
    ) -> Response:
        raise NotImplementedError  # Not required for tests


def _build_http_client(
    *,
    response: Response | None = None,
    exception: BaseException | None = None,
) -> tuple[HTTPClient, FakeHTTPClient]:
    """Return tuple of HTTPClient Protocol instance and underlying mock."""
    mock = FakeHTTPClient(response=response, exception=exception)
    protocol = cast(HTTPClient, cast(object, mock))
    return protocol, mock


class TestTelegramAPIClientInitialization:
    """Initialization behavior for TelegramAPIClient."""

    def test_rejects_non_positive_timeout(self) -> None:
        """Client validates timeout configuration."""
        config = _make_telegram_config()
        http_client, _ = _build_http_client()

        with pytest.raises(ValueError, match="request_timeout must be positive"):
            _ = TelegramAPIClient(
                config=config,
                http_client=http_client,
                request_timeout=0.0,
            )

    def test_rejects_empty_base_url(self) -> None:
        """Client validates base URL configuration."""
        config = _make_telegram_config()
        http_client, _ = _build_http_client()

        with pytest.raises(ValueError, match="api_base_url must not be empty"):
            _ = TelegramAPIClient(
                config=config,
                http_client=http_client,
                api_base_url="",
            )


class TestSendMessage:
    """send_message behavior for TelegramAPIClient."""

    @pytest.mark.asyncio
    async def test_successful_delivery_uses_config_defaults(self) -> None:
        """Client includes configuration defaults in payload."""
        config = _make_telegram_config(disable_notification=True)
        http_client, mock = _build_http_client(response=_success_response())
        client = TelegramAPIClient(config=config, http_client=http_client)

        response = await client.send_message(text="Mover update")

        assert response.status == 200
        assert mock.last_timeout == client.request_timeout
        assert mock.last_payload is not None
        assert mock.last_payload["chat_id"] == config.chat_id
        assert mock.last_payload["text"] == "Mover update"
        assert mock.last_payload["parse_mode"] == cast(str, config.parse_mode)
        assert mock.last_payload["disable_notification"] is True

    @pytest.mark.asyncio
    async def test_override_optional_fields(self) -> None:
        """Keyword overrides take precedence over configuration values."""
        config = _make_telegram_config(message_thread_id=10, disable_notification=False)
        http_client, mock = _build_http_client(response=_success_response())
        client = TelegramAPIClient(config=config, http_client=http_client)

        _ = await client.send_message(
            text="Mover update",
            parse_mode="MarkdownV2",
            disable_notification=True,
            message_thread_id=555,
        )

        assert mock.last_payload is not None
        assert mock.last_payload["parse_mode"] == "MarkdownV2"
        assert mock.last_payload["disable_notification"] is True
        assert mock.last_payload["message_thread_id"] == 555

    @pytest.mark.asyncio
    async def test_uses_configured_thread_id_when_not_overridden(self) -> None:
        """Thread ID from config is forwarded when override absent."""
        config = _make_telegram_config(message_thread_id=42)
        http_client, mock = _build_http_client(response=_success_response())
        client = TelegramAPIClient(config=config, http_client=http_client)

        _ = await client.send_message(text="Mover update")

        assert mock.last_payload is not None
        assert mock.last_payload["message_thread_id"] == 42

    @pytest.mark.asyncio
    async def test_rejects_empty_text(self) -> None:
        """Blank messages are rejected locally."""
        config = _make_telegram_config()
        http_client, _ = _build_http_client()
        client = TelegramAPIClient(config=config, http_client=http_client)

        with pytest.raises(ValueError, match="text must contain"):
            _ = await client.send_message(text="   ")

    @pytest.mark.asyncio
    async def test_non_200_status_raises_api_error(self) -> None:
        """HTTP errors raise TelegramAPIError with status context."""
        response = Response(status=500, body={}, headers={})
        config = _make_telegram_config()
        http_client, _ = _build_http_client(response=response)
        client = TelegramAPIClient(config=config, http_client=http_client)

        with pytest.raises(TelegramAPIError, match="HTTP 500") as exc_info:
            _ = await client.send_message(text="Mover update")

        assert exc_info.value.status == 500

    @pytest.mark.asyncio
    async def test_invalid_chat_error_is_specialized(self) -> None:
        """chat_id errors map to TelegramChatNotFoundError."""
        response = Response(
            status=200,
            body={
                "ok": False,
                "error_code": 400,
                "description": "Bad Request: chat not found",
            },
            headers={},
        )
        config = _make_telegram_config()
        http_client, _ = _build_http_client(response=response)
        client = TelegramAPIClient(config=config, http_client=http_client)

        with pytest.raises(TelegramChatNotFoundError) as exc_info:
            _ = await client.send_message(text="Mover update")

        assert exc_info.value.error_code == 400

    @pytest.mark.asyncio
    async def test_bot_blocked_error_is_specialized(self) -> None:
        """Bot blocked responses raise TelegramBotBlockedError."""
        response = Response(
            status=403,
            body={
                "ok": False,
                "error_code": 403,
                "description": "Forbidden: bot was blocked by the user",
            },
            headers={},
        )
        config = _make_telegram_config()
        http_client, _ = _build_http_client(response=response)
        client = TelegramAPIClient(config=config, http_client=http_client)

        with pytest.raises(TelegramBotBlockedError) as exc_info:
            _ = await client.send_message(text="Mover update")

        assert exc_info.value.status == 403

    @pytest.mark.asyncio
    async def test_timeout_errors_are_wrapped(self) -> None:
        """Timeout errors are converted into TelegramAPIError."""
        config = _make_telegram_config()
        http_client, _ = _build_http_client(exception=TimeoutError())
        client = TelegramAPIClient(config=config, http_client=http_client)

        with pytest.raises(TelegramAPIError, match="timed out") as exc_info:
            _ = await client.send_message(text="Mover update")

        assert exc_info.value.status == 408
