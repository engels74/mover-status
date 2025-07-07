"""Discord webhook client for sending notifications."""

from __future__ import annotations

import logging
from typing import TypedDict, override

import httpx
from pydantic import BaseModel, Field, field_validator

from .error_handling import (
    AdvancedRateLimiter,
    DiscordErrorClassifier,
    WebhookValidator,
    with_discord_error_handling,
)

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
        
        # Validate webhook URL using enhanced validator
        WebhookValidator.validate_webhook_url(webhook_url)
        
        # Use advanced rate limiter (Discord allows 30 requests per minute per webhook)
        self._rate_limiter: AdvancedRateLimiter = AdvancedRateLimiter(
            max_requests=30,
            time_window=60.0,
            burst_limit=5,
            adaptive_delay=True,
        )
    
    def get_rate_limit_stats(self) -> dict[str, object]:
        """Get rate limiter statistics.
        
        Returns:
            Dictionary with rate limiter statistics
        """
        return self._rate_limiter.get_stats()
    
    @with_discord_error_handling(
        max_attempts=3,
        backoff_factor=2.0,
        max_backoff=60.0,
        jitter=True,
        respect_retry_after=True,
    )
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
            
        Raises:
            DiscordApiError: If there's an error sending the message
        """
        # Build payload
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
        
        # Validate payload before sending
        WebhookValidator.validate_embed_payload(payload)
        
        # Apply rate limiting
        await self._rate_limiter.acquire()
        
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
                else:
                    # Convert HTTP error to Discord API error
                    discord_error = DiscordErrorClassifier.classify_http_error(response)
                    logger.error(f"Discord webhook request failed: {discord_error}")
                    raise discord_error
                    
        except httpx.HTTPStatusError as e:
            # Convert HTTP status errors to Discord API errors
            discord_error = DiscordErrorClassifier.classify_http_error(e.response)
            logger.error(f"Discord webhook HTTP error: {discord_error}")
            raise discord_error
            
        except (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError) as e:
            # Convert network errors to Discord API errors
            discord_error = DiscordErrorClassifier.classify_network_error(e)
            logger.error(f"Discord webhook network error: {discord_error}")
            raise discord_error
    
    @override
    def __repr__(self) -> str:
        """String representation of the client."""
        return f"DiscordWebhookClient(webhook_url='{self.webhook_url[:50]}...')"