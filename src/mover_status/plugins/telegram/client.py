"""Telegram Bot API client with provider-specific error handling.

Responsibilities (Requirements 9.1–9.4):
- Encapsulate Telegram HTTP interactions inside the Telegram plugin
- Implement sendMessage POST requests with provider-specific payloads
- Parse Telegram error responses for actionable diagnostics
- Translate domain errors (invalid chat, bot blocked) into explicit exceptions
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Final, cast

from mover_status.plugins.telegram.config import TelegramConfig
from mover_status.types import HTTPClient, Response

__all__ = [
    "TelegramAPIClient",
    "TelegramAPIError",
    "TelegramChatNotFoundError",
    "TelegramBotBlockedError",
]

_TELEGRAM_API_BASE_URL: Final[str] = "https://api.telegram.org"
_SEND_MESSAGE_METHOD: Final[str] = "sendMessage"
_CHAT_NOT_FOUND_MARKERS: Final[tuple[str, ...]] = (
    "chat not found",
    "chat_id is empty",
    "chat_id is invalid",
    "chat_id invalid",
    "channel_private",
)
_BOT_BLOCKED_MARKERS: Final[tuple[str, ...]] = (
    "bot was blocked by the user",
    "forbidden: bot was blocked",
    "bot was kicked",
)


class TelegramAPIError(RuntimeError):
    """Base exception for Telegram API failures."""

    def __init__(
        self,
        message: str,
        *,
        status: int,
        error_code: int | None = None,
        retry_after: float | None = None,
    ) -> None:
        super().__init__(message)
        self.status: int = status
        self.error_code: int | None = error_code
        self.retry_after: float | None = retry_after


class TelegramChatNotFoundError(TelegramAPIError):
    """Raised when Telegram reports that the chat_id/username is invalid."""


class TelegramBotBlockedError(TelegramAPIError):
    """Raised when Telegram reports the bot is blocked by the chat."""


@dataclass(slots=True)
class TelegramAPIClient:
    """HTTP client wrapper for Telegram Bot API sendMessage calls."""

    config: TelegramConfig
    http_client: HTTPClient
    request_timeout: float = 10.0
    api_base_url: str = _TELEGRAM_API_BASE_URL
    _logger: logging.Logger = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.request_timeout <= 0:
            msg = "request_timeout must be positive"
            raise ValueError(msg)
        if not self.api_base_url:
            msg = "api_base_url must not be empty"
            raise ValueError(msg)
        self._logger = logging.getLogger(__name__)

    async def send_message(
        self,
        *,
        text: str,
        parse_mode: str | None = None,
        disable_notification: bool | None = None,
        message_thread_id: int | None = None,
    ) -> Response:
        """Send a Telegram message to the configured chat."""
        if not text.strip():
            msg = "text must contain at least one non-whitespace character"
            raise ValueError(msg)

        payload = self._build_payload(
            text=text,
            parse_mode=parse_mode,
            disable_notification=disable_notification,
            message_thread_id=message_thread_id,
        )

        try:
            response = await self.http_client.post(
                self._build_endpoint(),
                payload,
                timeout=self.request_timeout,
            )
        except TimeoutError as exc:
            raise TelegramAPIError(
                "Telegram sendMessage request timed out",
                status=408,
            ) from exc
        except Exception as exc:  # pragma: no cover - defensive
            raise TelegramAPIError(
                f"Unexpected Telegram API error: {type(exc).__name__}",
                status=0,
            ) from exc

        return self._handle_response(response)

    def _build_payload(
        self,
        *,
        text: str,
        parse_mode: str | None,
        disable_notification: bool | None,
        message_thread_id: int | None,
    ) -> dict[str, object]:
        """Construct payload for the sendMessage request."""
        payload: dict[str, object] = {
            "chat_id": self.config.chat_id,
            "text": text,
            "disable_notification": (
                disable_notification if disable_notification is not None else self.config.disable_notification
            ),
        }

        resolved_parse_mode = parse_mode if parse_mode is not None else self.config.parse_mode
        if resolved_parse_mode:
            payload["parse_mode"] = resolved_parse_mode

        resolved_thread_id = message_thread_id if message_thread_id is not None else self.config.message_thread_id
        if resolved_thread_id is not None:
            payload["message_thread_id"] = resolved_thread_id

        return payload

    def _build_endpoint(self) -> str:
        """Construct the sendMessage endpoint URL."""
        base = self.api_base_url.rstrip("/")
        return f"{base}/bot{self.config.bot_token}/{_SEND_MESSAGE_METHOD}"

    def _handle_response(self, response: Response) -> Response:
        """Validate Telegram response and raise on errors."""
        if response.status != 200:
            raise self._build_api_error(response)

        if self._is_ok(response.body):
            return response

        raise self._build_api_error(response)

    def _is_ok(self, body: Mapping[str, object]) -> bool:
        """Determine whether Telegram response body indicates success."""
        ok_flag = body.get("ok")
        if isinstance(ok_flag, bool):
            return ok_flag
        if isinstance(ok_flag, str):
            return ok_flag.lower() == "true"
        return False

    def _build_api_error(self, response: Response) -> TelegramAPIError:
        """Create TelegramAPIError with parsed context."""
        body: Mapping[str, object] = response.body
        description = self._coerce_str(body.get("description"))
        error_code = self._coerce_int(body.get("error_code"))
        parameters = self._extract_mapping(body.get("parameters"))
        retry_after = self._coerce_float(parameters.get("retry_after")) if parameters else None

        message = description or f"Telegram API responded with HTTP {response.status}"

        return self._map_description_to_error(
            message=message,
            status=response.status,
            error_code=error_code,
            retry_after=retry_after,
        )

    def _map_description_to_error(
        self,
        *,
        message: str,
        status: int,
        error_code: int | None,
        retry_after: float | None,
    ) -> TelegramAPIError:
        """Map Telegram error descriptions to specific exception subclasses."""
        normalized = message.lower()
        if any(marker in normalized for marker in _CHAT_NOT_FOUND_MARKERS):
            return TelegramChatNotFoundError(
                message,
                status=status,
                error_code=error_code,
                retry_after=retry_after,
            )
        if any(marker in normalized for marker in _BOT_BLOCKED_MARKERS):
            return TelegramBotBlockedError(
                message,
                status=status,
                error_code=error_code,
                retry_after=retry_after,
            )
        return TelegramAPIError(
            message,
            status=status,
            error_code=error_code,
            retry_after=retry_after,
        )

    def _coerce_str(self, value: object) -> str | None:
        """Convert arbitrary value to string if possible."""
        if isinstance(value, str):
            return value
        return None

    def _coerce_int(self, value: object) -> int | None:
        """Convert arbitrary value to int if possible."""
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str):
            try:
                return int(value)
            except ValueError:
                return None
        return None

    def _coerce_float(self, value: object) -> float | None:
        """Convert arbitrary value to float if possible."""
        if isinstance(value, bool):
            return float(value)
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                return None
        return None

    def _extract_mapping(self, value: object) -> Mapping[str, object] | None:
        """Return mapping if the value is Mapping-like."""
        if isinstance(value, Mapping):
            return cast(Mapping[str, object], value)
        return None
