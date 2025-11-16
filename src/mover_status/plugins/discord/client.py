"""Discord webhook API client with provider-specific error handling.

This module implements the Discord-specific API client required by
Requirements 9.1–9.4:
- Self-contained client that POSTs to the Discord webhook endpoint
- Discord-aware error parsing for actionable diagnostics
- Rate limit handling using Discord's `retry_after` semantics
- Isolation from other providers by living entirely within the Discord plugin
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Final

from mover_status.plugins.discord.config import DiscordConfig
from mover_status.types import HTTPClient, Response

__all__ = [
    "DiscordAPIClient",
    "DiscordAPIError",
    "DiscordRateLimitError",
]

_SUCCESS_STATUSES: Final[tuple[int, ...]] = (200, 201, 202, 204)
_DEFAULT_ALLOWED_MENTIONS: Final[dict[str, list[str]]] = {"parse": []}
_DEFAULT_RATE_LIMIT_DELAY: Final[float] = 1.0


class DiscordAPIError(RuntimeError):
    """Base exception for Discord API failures."""

    def __init__(
        self,
        message: str,
        *,
        status: int,
        code: int | None = None,
        retry_after: float | None = None,
    ) -> None:
        super().__init__(message)
        self.status: int = status
        self.code: int | None = code
        self.retry_after: float | None = retry_after


class DiscordRateLimitError(DiscordAPIError):
    """Raised when Discord responds with a rate limit error."""

    def __init__(self, *, retry_after: float, message: str, is_global: bool) -> None:
        super().__init__(
            message,
            status=429,
            retry_after=retry_after,
        )
        self.is_global: bool = is_global


@dataclass(slots=True)
class DiscordAPIClient:
    """HTTP client wrapper for interacting with Discord webhooks."""

    config: DiscordConfig
    http_client: HTTPClient
    request_timeout: float = 10.0
    max_attempts: int = 3
    max_backoff_seconds: float = 15.0
    rate_limit_padding: float = 0.25
    rate_limit_cap: float = 30.0
    _logger: logging.Logger = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.request_timeout <= 0:
            msg = "request_timeout must be positive"
            raise ValueError(msg)
        if self.max_attempts < 1:
            msg = "max_attempts must be at least 1"
            raise ValueError(msg)
        if self.max_backoff_seconds <= 0:
            msg = "max_backoff_seconds must be positive"
            raise ValueError(msg)
        if self.rate_limit_cap <= 0:
            msg = "rate_limit_cap must be positive"
            raise ValueError(msg)
        self._logger = logging.getLogger(__name__)

    async def send_webhook(
        self,
        *,
        embeds: Sequence[Mapping[str, object]],
        content: str | None = None,
        allowed_mentions: Mapping[str, object] | None = None,
        username: str | None = None,
    ) -> Response:
        """Send a webhook payload with embeds to Discord."""
        payload = self._build_payload(
            embeds=embeds,
            content=content,
            allowed_mentions=allowed_mentions,
            username=username,
        )
        return await self._dispatch(payload)

    async def _dispatch(self, payload: Mapping[str, object]) -> Response:
        """Execute webhook POST with retry, rate limiting, and error parsing."""
        last_error: DiscordAPIError | None = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                response = await self.http_client.post(
                    self.config.webhook_url,
                    payload,
                    timeout=self.request_timeout,
                )
            except TimeoutError as exc:
                last_error = DiscordAPIError(
                    "Discord webhook request timed out",
                    status=408,
                )
                if attempt >= self.max_attempts:
                    raise last_error from exc
                await self._sleep_with_backoff(attempt)
                continue
            except Exception as exc:  # pragma: no cover - defensive
                last_error = DiscordAPIError(
                    "Unexpected error while delivering Discord webhook",
                    status=0,
                )
                if attempt >= self.max_attempts:
                    raise last_error from exc
                await self._sleep_with_backoff(attempt)
                continue

            if response.status in _SUCCESS_STATUSES:
                self._logger.debug(
                    "Discord webhook delivered (status=%d, attempt=%d)",
                    response.status,
                    attempt,
                )
                return response

            if response.status == 429:
                rate_limit_error = await self._handle_rate_limit(response, attempt)
                last_error = rate_limit_error
                continue

            if 500 <= response.status < 600:
                last_error = DiscordAPIError(
                    f"Discord server error ({response.status})",
                    status=response.status,
                )
                if attempt >= self.max_attempts:
                    raise last_error
                await self._sleep_with_backoff(attempt)
                continue

            # Any remaining non-success status is treated as a client error
            raise self._build_api_error(response)

        if last_error is not None:
            raise last_error
        msg = "Discord webhook delivery failed without a recorded error"
        raise DiscordAPIError(msg, status=0)

    async def _handle_rate_limit(self, response: Response, attempt: int) -> DiscordRateLimitError:
        """Handle Discord rate limit responses by delaying and retrying."""
        body = self._copy_body(response.body)
        retry_after = self._coerce_float(body.get("retry_after"))
        is_global = bool(body.get("global", False))

        if retry_after is None:
            retry_after = self._parse_retry_after_header(response.headers) or _DEFAULT_RATE_LIMIT_DELAY

        retry_after += self.rate_limit_padding
        retry_after = min(max(retry_after, _DEFAULT_RATE_LIMIT_DELAY), self.rate_limit_cap)

        message = self._extract_message(body) or "Discord rate limit reached"
        error = DiscordRateLimitError(
            retry_after=retry_after,
            message=message,
            is_global=is_global,
        )

        self._logger.warning(
            "Discord rate limit encountered (global=%s, retry_after=%.2fs, attempt=%d/%d)",
            is_global,
            retry_after,
            attempt,
            self.max_attempts,
        )

        if attempt >= self.max_attempts:
            return error

        await asyncio.sleep(retry_after)
        return error

    def _build_api_error(self, response: Response) -> DiscordAPIError:
        """Create a DiscordAPIError from a non-successful response."""
        body = self._copy_body(response.body)
        message = self._extract_message(body) or f"Discord API responded with {response.status}"
        code = self._extract_error_code(body)
        details = self._format_error_details(body.get("errors"))

        if details:
            message = f"{message}: {details}"

        return DiscordAPIError(message, status=response.status, code=code)

    def _build_payload(
        self,
        *,
        embeds: Sequence[Mapping[str, object]],
        content: str | None,
        allowed_mentions: Mapping[str, object] | None,
        username: str | None,
    ) -> dict[str, object]:
        """Assemble the JSON body sent to the webhook endpoint."""
        embed_payload = [dict(embed) for embed in embeds if embed]
        normalized_content = content.strip() if content else ""

        if not embed_payload and not normalized_content:
            msg = "Discord webhook payload requires at least one embed or content message"
            raise ValueError(msg)

        payload: dict[str, object] = {}
        if normalized_content:
            payload["content"] = normalized_content
        if embed_payload:
            payload["embeds"] = embed_payload

        mentions = dict(allowed_mentions) if allowed_mentions else dict(_DEFAULT_ALLOWED_MENTIONS)
        payload["allowed_mentions"] = mentions

        username_override = username or self.config.username
        if username_override:
            payload["username"] = username_override

        return payload

    def _copy_body(self, body: Mapping[str, object] | None) -> dict[str, object]:
        """Create a shallow copy of the JSON body for safe access."""
        if not body:
            return {}
        return dict(body)

    def _extract_message(self, body: Mapping[str, object]) -> str | None:
        """Extract top-level Discord error message."""
        message = body.get("message")
        return message if isinstance(message, str) else None

    def _extract_error_code(self, body: Mapping[str, object]) -> int | None:
        """Extract Discord-specific error code when present."""
        code = body.get("code")
        if isinstance(code, int):
            return code
        if isinstance(code, str) and code.isdigit():
            return int(code)
        return None

    def _format_error_details(self, details: object) -> str | None:
        """Serialize nested Discord error structures into a readable string."""
        if details is None:
            return None
        try:
            return json.dumps(details, separators=(",", ":"), ensure_ascii=False)
        except (TypeError, ValueError):
            return str(details)

    def _parse_retry_after_header(self, headers: Mapping[str, str]) -> float | None:
        """Parse Retry-After header value when Discord omits JSON retry data."""
        retry_after_value = headers.get("Retry-After") or headers.get("retry-after")
        if not retry_after_value:
            return None
        try:
            return float(retry_after_value)
        except ValueError:
            self._logger.debug("Discord Retry-After header had unexpected format: %s", retry_after_value)
            return None

    def _coerce_float(self, value: object) -> float | None:
        """Convert arbitrary values to float when feasible."""
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                return None
        return None

    async def _sleep_with_backoff(self, attempt: int) -> None:
        """Sleep using exponential backoff constrained by configured maximum."""
        backoff: float = 2.0 ** (attempt - 1)
        delay: float = min(backoff, self.max_backoff_seconds)
        await asyncio.sleep(delay)
