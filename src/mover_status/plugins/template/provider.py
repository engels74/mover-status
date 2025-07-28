"""Template notification provider implementation.

This template provides a complete example of how to implement a notification
provider plugin for the Mover Status Monitor. Use this as a starting point
for creating your own custom notification providers.

To create a new provider:
1. Copy this template directory to a new directory named after your provider
2. Rename this file to match your provider
3. Implement all the required methods
4. Update the metadata in __init__.py
5. Create any provider-specific models or utilities
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, override
from collections.abc import Mapping

from mover_status.notifications.base.provider import NotificationProvider

if TYPE_CHECKING:
    from mover_status.notifications.models.message import Message

logger = logging.getLogger(__name__)

# Plugin metadata (used by the plugin discovery system)
PLUGIN_METADATA = {
    "name": "template",
    "description": "Template notification provider for development reference",
    "version": "1.0.0",
    "author": "Mover Status Team",
    "tags": ["template", "example", "development"],
    "dependencies": []  # List any external dependencies here (e.g., ["requests", "aiohttp"])
}


class TemplateProvider(NotificationProvider):
    """Template notification provider.
    
    This is a complete example implementation that demonstrates all the
    required methods and best practices for creating a notification provider.
    
    Key features demonstrated:
    - Configuration validation with helpful error messages
    - Async notification sending with error handling
    - Proper logging and status reporting
    - Clean separation of concerns
    """
    
    def __init__(self, config: Mapping[str, object]) -> None:
        """Initialize the template provider.
        
        Args:
            config: Provider configuration dictionary
            
        Expected configuration format:
        {
            "enabled": bool,           # Whether the provider is enabled
            "api_key": str,           # API key for the service (required)
            "endpoint": str,          # Service endpoint URL (required)
            "timeout": float,         # Request timeout in seconds (default: 30.0)
            "retries": int,           # Number of retry attempts (default: 3)
            "format": str,            # Message format ("json" or "text", default: "json")
            "custom_field": str       # Example custom configuration field
        }
        """
        super().__init__(config)
        
        # Validate configuration before storing values
        self.validate_config()
        
        # Extract and store configuration values with defaults
        self.api_key: str = str(config["api_key"])
        self.endpoint: str = str(config["endpoint"])
        
        # Optional configuration with defaults
        timeout_val = config.get("timeout", 30.0)
        self.timeout: float = float(timeout_val) if isinstance(timeout_val, (int, float, str)) else 30.0
        
        retries_val = config.get("retries", 3)
        self.retries: int = int(retries_val) if isinstance(retries_val, (int, float, str)) else 3
        
        self.format: str = str(config.get("format", "json"))
        self.custom_field: str = str(config.get("custom_field", "default_value"))
        
        logger.info("Template provider initialized with endpoint: %s", self.endpoint)
    
    @override
    def validate_config(self) -> None:
        """Validate the provider configuration.
        
        This method should check all required configuration fields and
        validate their formats and values. It should raise ValueError
        with descriptive messages for any configuration issues.
        
        Raises:
            ValueError: If the configuration is invalid
        """
        # Check required fields
        required_fields = ["api_key", "endpoint"]
        for field in required_fields:
            if field not in self.config:
                raise ValueError(f"{field} is required for template provider")
            
            value = self.config[field]
            if not value or (isinstance(value, str) and not value.strip()):
                raise ValueError(f"{field} cannot be empty")
        
        # Validate API key format (example validation)
        api_key = str(self.config["api_key"])
        if len(api_key) < 10:
            raise ValueError("api_key must be at least 10 characters long")
        
        # Validate endpoint URL format
        endpoint = str(self.config["endpoint"])
        if not endpoint.startswith(("http://", "https://")):
            raise ValueError("endpoint must be a valid HTTP/HTTPS URL")
        
        # Validate optional numeric fields
        timeout_val = self.config.get("timeout")
        if timeout_val is not None:
            try:
                if isinstance(timeout_val, (int, float, str)):
                    timeout = float(timeout_val)
                    if timeout <= 0:
                        raise ValueError("timeout must be positive")
                else:
                    raise ValueError("timeout must be a number")
            except (ValueError, TypeError) as e:
                raise ValueError(f"Invalid timeout value: {e}")
        
        retries_val = self.config.get("retries")
        if retries_val is not None:
            try:
                if isinstance(retries_val, (int, float, str)):
                    retries = int(retries_val)
                    if retries < 0:
                        raise ValueError("retries must be non-negative")
                else:
                    raise ValueError("retries must be a number")
            except (ValueError, TypeError) as e:
                raise ValueError(f"Invalid retries value: {e}")
        
        # Validate format field
        format_val = self.config.get("format")
        if format_val is not None:
            format_str = str(format_val)
            if format_str not in ("json", "text"):
                raise ValueError("format must be 'json' or 'text'")
        
        logger.debug("Template provider configuration validated successfully")
    
    @override
    def get_provider_name(self) -> str:
        """Get the name of this provider.
        
        Returns:
            The provider name (should match the plugin directory name)
        """
        return "template"
    
    @override
    async def send_notification(self, message: Message) -> bool:
        """Send a notification message.
        
        This is the main method that handles sending notifications.
        It should implement the actual communication with the external
        service, handle errors gracefully, and return success/failure status.
        
        Args:
            message: The notification message to send
            
        Returns:
            True if the notification was sent successfully, False otherwise
        """
        try:
            logger.debug("Sending template notification: %s", message.title)
            
            # Format the message according to the configured format
            formatted_message = self._format_message(message)
            
            # Simulate sending the message (replace with actual implementation)
            success = await self._send_to_service(formatted_message)
            
            if success:
                logger.info("Template notification sent successfully: %s", message.title)
                return True
            else:
                logger.error("Failed to send template notification: %s", message.title)
                return False
                
        except Exception as e:
            logger.error("Error sending template notification '%s': %s", message.title, e)
            return False
    
    def _format_message(self, message: Message) -> dict[str, object] | str:
        """Format a message according to the configured format.
        
        Args:
            message: The message to format
            
        Returns:
            Formatted message data
        """
        if self.format == "json":
            # Return structured data for JSON format
            return {
                "title": message.title,
                "content": message.content,
                "priority": message.priority,
                "tags": message.tags,
                "metadata": message.metadata,
                "custom_field": self.custom_field  # Include custom configuration
            }
        else:
            # Return plain text format
            text_parts = [f"Title: {message.title}"]
            
            if message.content:
                text_parts.append(f"Content: {message.content}")
            
            text_parts.append(f"Priority: {message.priority}")
            
            if message.tags:
                text_parts.append(f"Tags: {', '.join(message.tags)}")
            
            if message.metadata:
                metadata_lines = [f"  {key}: {value}" for key, value in message.metadata.items()]
                text_parts.append("Metadata:")
                text_parts.extend(metadata_lines)
            
            return "\n".join(text_parts)
    
    async def _send_to_service(self, formatted_message: dict[str, object] | str) -> bool:
        """Send formatted message to the external service.
        
        This method should contain the actual implementation for communicating
        with your notification service. This template version just simulates
        the process.
        
        Args:
            formatted_message: The formatted message to send
            
        Returns:
            True if sending was successful, False otherwise
        """
        # TODO: Replace this simulation with actual service communication
        
        # Example of what real implementation might look like:
        """
        import aiohttp
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
            for attempt in range(self.retries + 1):
                try:
                    payload = {
                        "message": formatted_message,
                        "api_key": self.api_key
                    }
                    
                    async with session.post(self.endpoint, json=payload) as response:
                        if response.status == 200:
                            return True
                        elif response.status == 429:  # Rate limited
                            if attempt < self.retries:
                                await asyncio.sleep(2 ** attempt)  # Exponential backoff
                                continue
                        else:
                            logger.error("Service returned status %d: %s", 
                                       response.status, await response.text())
                            return False
                            
                except aiohttp.ClientError as e:
                    logger.error("Network error on attempt %d: %s", attempt + 1, e)
                    if attempt < self.retries:
                        await asyncio.sleep(1)
                        continue
                    return False
        
        return False
        """
        
        # Simulation: Always succeed for demonstration
        logger.debug("Simulating message send to %s with data: %s", 
                    self.endpoint, formatted_message)
        
        # In a real implementation, you would:
        # 1. Make HTTP request to self.endpoint
        # 2. Include self.api_key in headers or payload
        # 3. Handle various response codes
        # 4. Implement retry logic with exponential backoff
        # 5. Handle network timeouts and errors
        
        return True
    
    def get_status(self) -> dict[str, object]:
        """Get provider status information.
        
        This is an optional method that can provide detailed status
        information for debugging and monitoring purposes.
        
        Returns:
            Dictionary with status information
        """
        return {
            "provider_name": self.get_provider_name(),
            "enabled": self.is_enabled(),
            "configuration": {
                "endpoint": self.endpoint,
                "timeout": self.timeout,
                "retries": self.retries,
                "format": self.format,
                "custom_field": self.custom_field
            },
            "metadata": PLUGIN_METADATA
        }
    
    async def test_connection(self) -> tuple[bool, str]:
        """Test connection to the service.
        
        This is an optional method that can be used to verify that
        the provider is properly configured and can communicate with
        the external service.
        
        Returns:
            Tuple of (success, message) indicating test result
        """
        try:
            # TODO: Implement actual connection test
            # This might involve sending a test message or ping to the service
            
            logger.debug("Testing connection to %s", self.endpoint)
            
            # Simulation: Always succeed
            return True, "Connection test successful"
            
        except Exception as e:
            error_msg = f"Connection test failed: {e}"
            logger.error(error_msg)
            return False, error_msg