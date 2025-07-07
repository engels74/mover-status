"""HTML message formatter for Telegram notifications."""

from __future__ import annotations

import html
from typing import TYPE_CHECKING, override

from mover_status.plugins.telegram.formatting.base import MessageFormatter

if TYPE_CHECKING:
    from mover_status.notifications.models.message import Message


class HTMLFormatter(MessageFormatter):
    """HTML message formatter for Telegram."""
    
    @override
    def format_message(self, message: Message) -> str:
        """Format a message using HTML markup.
        
        Args:
            message: The message to format
            
        Returns:
            HTML-formatted message text
        """
        lines: list[str] = []
        
        # Title with bold formatting
        title = self.format_title(message.title)
        lines.append(f"<b>{title}</b>")
        
        # Content
        if message.content:
            content = self.format_content(message.content)
            lines.append(content)
        
        # Priority (only show if not normal)
        if message.priority != "normal":
            priority = self.format_priority_styled(message.priority)
            lines.append(priority)
        
        # Tags with italic formatting
        if message.tags:
            tags = self.format_tags_styled(message.tags)
            lines.append(tags)
        
        # Metadata
        if message.metadata:
            metadata = self.format_metadata(message.metadata)
            if metadata:
                lines.append("")  # Empty line for separation
                lines.append(metadata)
        
        return "\n".join(lines)
    
    @override
    def escape_text(self, text: str) -> str:
        """Escape HTML special characters.
        
        Args:
            text: Text to escape
            
        Returns:
            HTML-escaped text
        """
        return html.escape(text, quote=True)
    
    @override
    def format_title(self, title: str) -> str:
        """Format title for HTML (no additional formatting, just escape).
        
        Args:
            title: Title text
            
        Returns:
            Escaped title
        """
        return self.escape_text(title)
    
    def format_priority_styled(self, priority: str) -> str:
        """Format priority with appropriate HTML styling.
        
        Args:
            priority: Priority level
            
        Returns:
            Styled priority
        """
        priority_upper = priority.upper()
        
        # Use different styling based on priority
        if priority == "urgent":
            return f"<b><u>🚨 Priority: {self.escape_text(priority_upper)}</u></b>"
        elif priority == "high":
            return f"<b>⚠️ Priority: {self.escape_text(priority_upper)}</b>"
        elif priority == "low":
            return f"<i>ℹ️ Priority: {self.escape_text(priority_upper)}</i>"
        else:
            return f"Priority: {self.escape_text(priority_upper)}"
    
    def format_tags_styled(self, tags: list[str]) -> str:
        """Format tags with HTML styling.
        
        Args:
            tags: List of tags
            
        Returns:
            Styled tags
        """
        if not tags:
            return ""
        
        escaped_tags = [self.escape_text(tag) for tag in tags]
        tags_str = ", ".join(escaped_tags)
        return f"<i>🏷️ Tags: {tags_str}</i>"
    
    def format_code(self, code: str) -> str:
        """Format code block with HTML.
        
        Args:
            code: Code text
            
        Returns:
            HTML-formatted code
        """
        return f"<pre><code>{self.escape_text(code)}</code></pre>"
    
    def format_inline_code(self, code: str) -> str:
        """Format inline code with HTML.
        
        Args:
            code: Code text
            
        Returns:
            HTML-formatted inline code
        """
        return f"<code>{self.escape_text(code)}</code>"
    
    def format_link(self, url: str, text: str | None = None) -> str:
        """Format a link with HTML.
        
        Args:
            url: URL to link to
            text: Optional link text (uses URL if not provided)
            
        Returns:
            HTML-formatted link
        """
        escaped_url = self.escape_text(url)
        if text:
            escaped_text = self.escape_text(text)
            return f'<a href="{escaped_url}">{escaped_text}</a>'
        else:
            return f'<a href="{escaped_url}">{escaped_url}</a>'
    
    def format_mention(self, username: str, user_id: int | None = None) -> str:
        """Format a user mention with HTML.
        
        Args:
            username: Username to mention
            user_id: Optional user ID for deep linking
            
        Returns:
            HTML-formatted mention
        """
        escaped_username = self.escape_text(username)
        if user_id:
            return f'<a href="tg://user?id={user_id}">@{escaped_username}</a>'
        else:
            return f"@{escaped_username}"
    
    def format_bold(self, text: str) -> str:
        """Format text as bold.
        
        Args:
            text: Text to format
            
        Returns:
            Bold-formatted text
        """
        return f"<b>{self.escape_text(text)}</b>"
    
    def format_italic(self, text: str) -> str:
        """Format text as italic.
        
        Args:
            text: Text to format
            
        Returns:
            Italic-formatted text
        """
        return f"<i>{self.escape_text(text)}</i>"
    
    def format_underline(self, text: str) -> str:
        """Format text as underlined.
        
        Args:
            text: Text to format
            
        Returns:
            Underlined text
        """
        return f"<u>{self.escape_text(text)}</u>"
    
    def format_strikethrough(self, text: str) -> str:
        """Format text as strikethrough.
        
        Args:
            text: Text to format
            
        Returns:
            Strikethrough text
        """
        return f"<s>{self.escape_text(text)}</s>"