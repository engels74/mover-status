"""Discord webhook client for sending notifications."""

from __future__ import annotations

import asyncio
import logging
from typing import TypedDict, override
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)


class DiscordEmbed(BaseModel):
    """Discord embed structure."""
    
    title: str | None = Field(None, max_length=256)
    description: str | None = Field(None, max_length=4096)
    url: str | None = None
    timestamp: str | None = None
    color: int | None = None
    footer: dict[str, str] | None = None
    image: dict[str, str] | None = None
    thumbnail: dict[str, str] | None = None
    author: dict[str, str] | None = None
    fields: list[dict[str, str | bool]] = Field(default_factory=list, max_length=25)
    
    @field_validator("fields")
    @classmethod
    def validate_fields(cls, v: list[dict[str, str | bool]]) -> list[dict[str, str | bool]]:
        """Validate embed fields."""
        for field in v:
            if "name" not in field or "value" not in field:
                raise ValueError("Each field must have 'name' and 'value'")
            if len(str(field["name"])) > 256:
                raise ValueError("Field name cannot exceed 256 characters")
            if len(str(field["value"])) > 1024:
                raise ValueError("Field value cannot exceed 1024 characters")
        return v


class WebhookPayload(TypedDict, total=False):
    """Discord webhook payload structure."""
    
    content: str
    username: str
    avatar_url: str
    embeds: list[dict[str, object]]


class DiscordWebhookClient:
    """Discord webhook client for sending messages."""
    
    def __init__(
        self,
        webhook_url: str,
        username: str | None = None,
        avatar_url: str | None = None,
        timeout: float = 30.0,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ) -> None:
        """Initialize Discord webhook client.
        
        Args:
            webhook_url: Discord webhook URL
            username: Bot username for messages
            avatar_url: Bot avatar URL
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
            retry_delay: Base delay between retries in seconds
        """
        self.webhook_url: str = webhook_url
        self.username: str | None = username
        self.avatar_url: str | None = avatar_url
        self.timeout: float = timeout
        self.max_retries: int = max_retries
        self.retry_delay: float = retry_delay
        
        self._validate_webhook_url()
        
        # Rate limiting (Discord allows 30 requests per minute per webhook)
        self._rate_limit_window: float = 60.0  # 1 minute
        self._rate_limit_max: int = 30
        self._rate_limit_timestamps: list[float] = []
        self._rate_limit_lock: asyncio.Lock = asyncio.Lock()
    
    def _validate_webhook_url(self) -> None:
        """Validate the webhook URL format."""
        parsed = urlparse(self.webhook_url)
        
        if not parsed.scheme in ("http", "https"):
            raise ValueError("Webhook URL must use HTTP or HTTPS")
        
        if not parsed.netloc.endswith(("discord.com", "discordapp.com")):
            raise ValueError("Webhook URL must be a Discord webhook")
        
        if not parsed.path.startswith("/api/webhooks/"):
            raise ValueError("Invalid Discord webhook URL format")
    
    async def _check_rate_limit(self) -> None:
        """Check and enforce rate limits."""
        import time
        
        async with self._rate_limit_lock:
            current_time = time.time()
            
            # Remove timestamps older than the window
            self._rate_limit_timestamps = [
                ts for ts in self._rate_limit_timestamps
                if current_time - ts < self._rate_limit_window
            ]
            
            # Check if we're at the limit
            if len(self._rate_limit_timestamps) >= self._rate_limit_max:
                oldest_timestamp = min(self._rate_limit_timestamps)
                wait_time = self._rate_limit_window - (current_time - oldest_timestamp)
                
                if wait_time > 0:
                    logger.warning(
                        f"Rate limit reached for Discord webhook. Waiting {wait_time:.1f} seconds"
                    )
                    await asyncio.sleep(wait_time)
            
            # Add current timestamp
            self._rate_limit_timestamps.append(current_time)
    
    async def send_message(
        self,
        content: str | None = None,
        embeds: list[DiscordEmbed] | None = None,
        username: str | None = None,
        avatar_url: str | None = None,
    ) -> bool:
        """Send a message to the Discord webhook.
        
        Args:
            content: Message content (up to 2000 characters)
            embeds: List of embeds to include
            username: Override bot username
            avatar_url: Override bot avatar URL
            
        Returns:
            True if message was sent successfully, False otherwise
        """
        if not content and not embeds:
            raise ValueError("Either content or embeds must be provided")
        
        if content and len(content) > 2000:
            raise ValueError("Message content cannot exceed 2000 characters")
        
        if embeds and len(embeds) > 10:
            raise ValueError("Cannot send more than 10 embeds")
        
        payload: WebhookPayload = {}
        
        if content:
            payload["content"] = content
        
        if embeds:
            payload["embeds"] = [embed.model_dump(exclude_none=True) for embed in embeds]
        
        effective_username = username or self.username
        if effective_username:
            payload["username"] = effective_username
        
        effective_avatar_url = avatar_url or self.avatar_url
        if effective_avatar_url:
            payload["avatar_url"] = effective_avatar_url
        
        await self._check_rate_limit()
        
        for attempt in range(self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        self.webhook_url,
                        json=payload,
                        headers={"Content-Type": "application/json"},
                    )
                    
                    if response.status_code == 204:
                        logger.debug("Discord webhook message sent successfully")
                        return True
                    elif response.status_code == 429:
                        # Rate limited by Discord
                        retry_after_str = response.headers.get("Retry-After", "1")  # pyright: ignore[reportAny]
                        retry_after = float(retry_after_str)  # pyright: ignore[reportAny]
                        logger.warning(
                            f"Discord webhook rate limited. Retrying after {retry_after} seconds"
                        )
                        await asyncio.sleep(retry_after)
                        continue
                    else:
                        logger.error(
                            f"Discord webhook request failed with status {response.status_code}: {response.text}"
                        )
                        
                        # Don't retry on client errors (4xx)
                        if 400 <= response.status_code < 500:
                            return False
                        
                        if attempt < self.max_retries:
                            wait_time = self.retry_delay * (2 ** attempt)  # pyright: ignore[reportAny]
                            logger.debug(f"Retrying in {wait_time} seconds...")
                            await asyncio.sleep(wait_time)  # pyright: ignore[reportAny]
                        else:
                            return False
                            
            except (httpx.TimeoutException, httpx.ConnectError) as e:
                logger.error(f"Discord webhook connection error: {e}")
                
                if attempt < self.max_retries:
                    wait_time_conn = self.retry_delay * (2 ** attempt)  # pyright: ignore[reportAny]
                    logger.debug(f"Retrying in {wait_time_conn} seconds...")
                    await asyncio.sleep(wait_time_conn)  # pyright: ignore[reportAny]
                else:
                    return False
            
            except Exception as e:
                logger.error(f"Unexpected error sending Discord webhook: {e}")
                return False
        
        return False
    
    @override
    def __repr__(self) -> str:
        """String representation of the client."""
        return f"DiscordWebhookClient(webhook_url='{self.webhook_url[:50]}...')"