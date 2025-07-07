"""Markdown message formatter for Telegram notifications."""

from __future__ import annotations

from typing import TYPE_CHECKING, override

from mover_status.plugins.telegram.formatting.base import MessageFormatter

if TYPE_CHECKING:
    from mover_status.notifications.models.message import Message


class MarkdownFormatter(MessageFormatter):
    """Markdown message formatter for Telegram (legacy mode)."""
    
    @override
    def format_message(self, message: Message) -> str:
        """Format a message using Markdown markup.
        
        Args:
            message: The message to format
            
        Returns:
            Markdown-formatted message text
        """
        lines: list[str] = []
        
        # Title with bold formatting
        title = self.format_title(message.title)
        lines.append(f"*{title}*")
        
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
        """Escape Markdown special characters.
        
        Args:
            text: Text to escape
            
        Returns:
            Markdown-escaped text
        """
        # Escape special Markdown characters
        chars_to_escape = r"_*[]()~`>#+-=|{}.!&"
        escaped_text = text
        for char in chars_to_escape:
            escaped_text = escaped_text.replace(char, f"\\{char}")
        return escaped_text
    
    @override
    def format_title(self, title: str) -> str:
        """Format title for Markdown (no additional formatting, just escape).
        
        Args:
            title: Title text
            
        Returns:
            Escaped title
        """
        return self.escape_text(title)
    
    def format_priority_styled(self, priority: str) -> str:
        """Format priority with appropriate Markdown styling.
        
        Args:
            priority: Priority level
            
        Returns:
            Styled priority
        """
        priority_upper = priority.upper()
        
        # Use different styling based on priority
        if priority == "urgent":
            return f"*🚨 Priority: {self.escape_text(priority_upper)}*"
        elif priority == "high":
            return f"*⚠️ Priority: {self.escape_text(priority_upper)}*"
        elif priority == "low":
            return f"_ℹ️ Priority: {self.escape_text(priority_upper)}_"
        else:
            return f"Priority: {self.escape_text(priority_upper)}"
    
    def format_tags_styled(self, tags: list[str]) -> str:
        """Format tags with Markdown styling.
        
        Args:
            tags: List of tags
            
        Returns:
            Styled tags
        """
        if not tags:
            return ""
        
        escaped_tags = [self.escape_text(tag) for tag in tags]
        tags_str = ", ".join(escaped_tags)
        return f"_🏷️ Tags: {tags_str}_"
    
    def format_code(self, code: str) -> str:
        """Format code block with Markdown.
        
        Args:
            code: Code text
            
        Returns:
            Markdown-formatted code
        """
        # Use triple backticks for code blocks
        return f"```\n{code}\n```"
    
    def format_inline_code(self, code: str) -> str:
        """Format inline code with Markdown.
        
        Args:
            code: Code text
            
        Returns:
            Markdown-formatted inline code
        """
        return f"`{code}`"
    
    def format_link(self, url: str, text: str | None = None) -> str:
        """Format a link with Markdown.
        
        Args:
            url: URL to link to
            text: Optional link text (uses URL if not provided)
            
        Returns:
            Markdown-formatted link
        """
        if text:
            escaped_text = self.escape_text(text)
            return f"[{escaped_text}]({url})"
        else:
            return f"[{url}]({url})"
    
    def format_mention(self, username: str, user_id: int | None = None) -> str:
        """Format a user mention with Markdown.
        
        Args:
            username: Username to mention
            user_id: Optional user ID for deep linking
            
        Returns:
            Markdown-formatted mention
        """
        escaped_username = self.escape_text(username)
        if user_id:
            return f"[{escaped_username}](tg://user?id={user_id})"
        else:
            return f"@{escaped_username}"
    
    def format_bold(self, text: str) -> str:
        """Format text as bold.
        
        Args:
            text: Text to format
            
        Returns:
            Bold-formatted text
        """
        return f"*{self.escape_text(text)}*"
    
    def format_italic(self, text: str) -> str:
        """Format text as italic.
        
        Args:
            text: Text to format
            
        Returns:
            Italic-formatted text
        """
        return f"_{self.escape_text(text)}_"


class MarkdownV2Formatter(MessageFormatter):
    """MarkdownV2 message formatter for Telegram (new mode)."""
    
    @override
    def format_message(self, message: Message) -> str:
        """Format a message using MarkdownV2 markup.
        
        Args:
            message: The message to format
            
        Returns:
            MarkdownV2-formatted message text
        """
        lines: list[str] = []
        
        # Title with bold formatting
        title = self.format_title(message.title)
        lines.append(f"*{title}*")
        
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
        """Escape MarkdownV2 special characters.
        
        Args:
            text: Text to escape
            
        Returns:
            MarkdownV2-escaped text
        """
        # MarkdownV2 has more characters that need escaping
        chars_to_escape = r"_*[]()~`>#+-=|{}.!&"
        escaped_text = text
        for char in chars_to_escape:
            escaped_text = escaped_text.replace(char, f"\\{char}")
        return escaped_text
    
    @override
    def format_title(self, title: str) -> str:
        """Format title for MarkdownV2 (no additional formatting, just escape).
        
        Args:
            title: Title text
            
        Returns:
            Escaped title
        """
        return self.escape_text(title)
    
    def format_priority_styled(self, priority: str) -> str:
        """Format priority with appropriate MarkdownV2 styling.
        
        Args:
            priority: Priority level
            
        Returns:
            Styled priority
        """
        priority_upper = priority.upper()
        
        # Use different styling based on priority
        if priority == "urgent":
            return f"*🚨 Priority: {self.escape_text(priority_upper)}*"
        elif priority == "high":
            return f"*⚠️ Priority: {self.escape_text(priority_upper)}*"
        elif priority == "low":
            return f"_ℹ️ Priority: {self.escape_text(priority_upper)}_"
        else:
            return f"Priority: {self.escape_text(priority_upper)}"
    
    def format_tags_styled(self, tags: list[str]) -> str:
        """Format tags with MarkdownV2 styling.
        
        Args:
            tags: List of tags
            
        Returns:
            Styled tags
        """
        if not tags:
            return ""
        
        escaped_tags = [self.escape_text(tag) for tag in tags]
        tags_str = ", ".join(escaped_tags)
        return f"_🏷️ Tags: {tags_str}_"
    
    def format_code(self, code: str) -> str:
        """Format code block with MarkdownV2.
        
        Args:
            code: Code text
            
        Returns:
            MarkdownV2-formatted code
        """
        # Use triple backticks for code blocks
        return f"```\n{code}\n```"
    
    def format_inline_code(self, code: str) -> str:
        """Format inline code with MarkdownV2.
        
        Args:
            code: Code text
            
        Returns:
            MarkdownV2-formatted inline code
        """
        return f"`{code}`"
    
    def format_link(self, url: str, text: str | None = None) -> str:
        """Format a link with MarkdownV2.
        
        Args:
            url: URL to link to
            text: Optional link text (uses URL if not provided)
            
        Returns:
            MarkdownV2-formatted link
        """
        if text:
            escaped_text = self.escape_text(text)
            return f"[{escaped_text}]({url})"
        else:
            return f"[{url}]({url})"
    
    def format_mention(self, username: str, user_id: int | None = None) -> str:
        """Format a user mention with MarkdownV2.
        
        Args:
            username: Username to mention
            user_id: Optional user ID for deep linking
            
        Returns:
            MarkdownV2-formatted mention
        """
        escaped_username = self.escape_text(username)
        if user_id:
            return f"[{escaped_username}](tg://user?id={user_id})"
        else:
            return f"@{escaped_username}"
    
    def format_bold(self, text: str) -> str:
        """Format text as bold.
        
        Args:
            text: Text to format
            
        Returns:
            Bold-formatted text
        """
        return f"*{self.escape_text(text)}*"
    
    def format_italic(self, text: str) -> str:
        """Format text as italic.
        
        Args:
            text: Text to format
            
        Returns:
            Italic-formatted text
        """
        return f"_{self.escape_text(text)}_"
    
    def format_underline(self, text: str) -> str:
        """Format text as underlined.
        
        Args:
            text: Text to format
            
        Returns:
            Underlined text
        """
        return f"__{self.escape_text(text)}__"
    
    def format_strikethrough(self, text: str) -> str:
        """Format text as strikethrough.
        
        Args:
            text: Text to format
            
        Returns:
            Strikethrough text
        """
        return f"~{self.escape_text(text)}~"
    
    def format_spoiler(self, text: str) -> str:
        """Format text as spoiler.
        
        Args:
            text: Text to format
            
        Returns:
            Spoiler text
        """
        return f"||{self.escape_text(text)}||"