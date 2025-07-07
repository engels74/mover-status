"""Base message formatter for Telegram notifications."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mover_status.notifications.models.message import Message


class MessageFormatter(ABC):
    """Abstract base class for message formatters."""
    
    @abstractmethod
    def format_message(self, message: Message) -> str:
        """Format a message for Telegram.
        
        Args:
            message: The message to format
            
        Returns:
            Formatted message text
        """
        
    @abstractmethod
    def escape_text(self, text: str) -> str:
        """Escape special characters in text.
        
        Args:
            text: Text to escape
            
        Returns:
            Escaped text
        """
        
    def format_title(self, title: str) -> str:
        """Format message title with emphasis.
        
        Args:
            title: Title text
            
        Returns:
            Formatted title
        """
        return self.escape_text(title)
    
    def format_content(self, content: str) -> str:
        """Format message content.
        
        Args:
            content: Content text
            
        Returns:
            Formatted content
        """
        return self.escape_text(content)
    
    def format_tags(self, tags: list[str]) -> str:
        """Format tags list.
        
        Args:
            tags: List of tags
            
        Returns:
            Formatted tags string
        """
        if not tags:
            return ""
        
        tags_str = ", ".join(tags)
        return f"Tags: {self.escape_text(tags_str)}"
    
    def format_metadata(self, metadata: dict[str, str]) -> str:
        """Format metadata dictionary.
        
        Args:
            metadata: Metadata dictionary
            
        Returns:
            Formatted metadata string
        """
        if not metadata:
            return ""
        
        lines: list[str] = []
        for key, value in metadata.items():
            escaped_key = self.escape_text(key)
            escaped_value = self.escape_text(value)
            lines.append(f"{escaped_key}: {escaped_value}")
        
        return "\n".join(lines)
    
    def format_priority(self, priority: str) -> str:
        """Format priority level with appropriate styling.
        
        Args:
            priority: Priority level
            
        Returns:
            Formatted priority
        """
        priority_upper = priority.upper()
        return self.escape_text(f"Priority: {priority_upper}")