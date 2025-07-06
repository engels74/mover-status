"""Message models for notification system."""

from __future__ import annotations

from typing import Literal, override

from pydantic import BaseModel, Field


class Message(BaseModel):
    """Base message model for notifications."""
    
    title: str = Field(
        ...,
        description="The title or subject of the notification",
        min_length=1,
        max_length=200
    )
    
    content: str = Field(
        ...,
        description="The main content or body of the notification",
        min_length=1,
        max_length=4000
    )
    
    priority: Literal["low", "normal", "high", "urgent"] = Field(
        default="normal",
        description="The priority level of the notification"
    )
    
    tags: list[str] = Field(
        default_factory=list,
        description="Optional tags for categorizing notifications"
    )
    
    metadata: dict[str, str] = Field(
        default_factory=dict,
        description="Additional metadata for the notification"
    )
    
    @override
    def __str__(self) -> str:
        """String representation of the message."""
        return f"Message(title='{self.title}', priority='{self.priority}')"