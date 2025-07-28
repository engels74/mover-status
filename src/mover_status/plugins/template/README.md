# Plugin Template

This directory contains a complete template implementation for creating notification provider plugins for the Mover Status Monitor. Use this as a reference and starting point for building your own custom notification providers.

## Overview

The plugin system allows you to create custom notification providers that are automatically discovered and loaded at runtime. Each provider must implement the `NotificationProvider` interface and provide proper configuration validation.

## File Structure

```
template/
├── __init__.py          # Plugin metadata and exports
├── provider.py          # Main provider implementation
└── README.md           # This documentation file
```

## Key Features Demonstrated

- **Dynamic Discovery**: Plugins are automatically discovered by the plugin loader
- **Configuration Validation**: Comprehensive validation with helpful error messages
- **Async Notification Sending**: Proper async/await patterns for external service calls
- **Error Handling**: Graceful error handling with proper logging
- **Extensibility**: Easy to extend with custom fields and functionality
- **Testing Support**: Includes connection testing and status reporting

## Creating a New Provider

### Step 1: Copy the Template

```bash
# Copy the template directory
cp -r src/mover_status/plugins/template src/mover_status/plugins/your_provider_name

# Navigate to your new provider directory
cd src/mover_status/plugins/your_provider_name
```

### Step 2: Update Plugin Metadata

Edit `__init__.py` and update the plugin metadata:

```python
PLUGIN_INFO = {
    "name": "your_provider_name",           # Match your directory name
    "version": "1.0.0",
    "description": "Your provider description",
    "author": "Your Name",
    "provider_class": YourProviderClass,    # Update class name
    "enabled": True,                        # Enable your provider
    "tags": ["custom", "notification"],
    "dependencies": ["requests"],           # List external dependencies
    "config_schema": {
        # Define your configuration schema here
    }
}
```

### Step 3: Implement Your Provider Class

Edit `provider.py` and rename `TemplateProvider` to your provider class name:

```python
class YourProviderProvider(NotificationProvider):
    """Your custom notification provider."""
    
    def __init__(self, config: Mapping[str, object]) -> None:
        super().__init__(config)
        self.validate_config()
        
        # Extract your configuration values
        self.api_key = str(config["api_key"])
        # Add other configuration fields...
    
    @override
    def validate_config(self) -> None:
        """Validate provider configuration."""
        # Implement your validation logic
        if "api_key" not in self.config:
            raise ValueError("api_key is required")
    
    @override
    def get_provider_name(self) -> str:
        """Return provider name."""
        return "your_provider_name"
    
    @override
    async def send_notification(self, message: Message) -> bool:
        """Send notification to your service."""
        try:
            # Implement your notification sending logic here
            # This might involve HTTP requests, API calls, etc.
            return True
        except Exception as e:
            logger.error("Failed to send notification: %s", e)
            return False
```

### Step 4: Update Configuration Schema

Define your configuration schema in the `PLUGIN_INFO` dictionary. This is used for validation and documentation:

```python
"config_schema": {
    "type": "object",
    "properties": {
        "enabled": {
            "type": "boolean",
            "default": True,
            "description": "Enable this provider"
        },
        "api_key": {
            "type": "string",
            "description": "API key for your service"
        },
        "endpoint": {
            "type": "string",
            "format": "uri",
            "description": "Service endpoint URL"
        },
        # Add more configuration fields as needed
    },
    "required": ["api_key"],
    "additionalProperties": False
}
```

### Step 5: Test Your Implementation

Create a test configuration file (e.g., `config_your_provider.yaml`):

```yaml
your_provider_name:
  enabled: true
  api_key: "your_test_api_key"
  endpoint: "https://api.yourservice.com/notifications"
  # Add other configuration values
```

Enable your provider in the main config:

```yaml
notifications:
  enabled_providers:
    - "your_provider_name"
```

## Required Methods

Every notification provider must implement these methods:

### `__init__(self, config: Mapping[str, object]) -> None`
Initialize the provider with configuration. Should call `validate_config()`.

### `validate_config(self) -> None`
Validate configuration and raise `ValueError` for invalid configurations.

### `get_provider_name(self) -> str`
Return the provider name (should match the plugin directory name).

### `async send_notification(self, message: Message) -> bool`
Send a notification message. Return `True` for success, `False` for failure.

## Optional Methods

These methods can be implemented for additional functionality:

### `get_status(self) -> dict[str, object]`
Return provider status information for debugging and monitoring.

### `async test_connection(self) -> tuple[bool, str]`
Test connection to the external service. Return success status and message.

## Configuration Guidelines

1. **Required Fields**: Always validate required configuration fields
2. **Default Values**: Provide sensible defaults for optional fields
3. **Type Validation**: Validate field types and formats
4. **Error Messages**: Provide clear, helpful error messages
5. **Security**: Never log sensitive information like API keys

## Best Practices

### Error Handling
```python
try:
    # Your notification logic
    return True
except SpecificServiceError as e:
    logger.error("Service-specific error: %s", e)
    return False
except Exception as e:
    logger.error("Unexpected error: %s", e)
    return False
```

### Logging
```python
import logging

logger = logging.getLogger(__name__)

# Use appropriate log levels
logger.debug("Debug information")
logger.info("Important information")
logger.warning("Warning message")
logger.error("Error message")
```

### Async Operations
```python
import aiohttp

async def send_to_service(self, data: dict[str, object]) -> bool:
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(self.endpoint, json=data) as response:
                return response.status == 200
        except aiohttp.ClientError:
            return False
```

## Testing Your Provider

### Unit Tests
Create unit tests for your provider in `tests/unit/plugins/your_provider_name/`:

```python
import pytest
from unittest.mock import Mock, patch

from mover_status.plugins.your_provider_name import YourProviderProvider

class TestYourProviderProvider:
    def test_initialization(self):
        config = {
            "api_key": "test_key",
            "endpoint": "https://api.test.com"
        }
        provider = YourProviderProvider(config)
        assert provider.api_key == "test_key"
        assert provider.endpoint == "https://api.test.com"
    
    def test_config_validation(self):
        with pytest.raises(ValueError, match="api_key is required"):
            YourProviderProvider({})
    
    @pytest.mark.asyncio
    async def test_send_notification(self):
        # Test your send_notification method
        pass
```

### Integration Tests
Test with actual service endpoints (if possible) or use mock servers.

## Common Patterns

### HTTP-based Services
Most notification providers communicate via HTTP APIs:

```python
import aiohttp
from typing import Any

async def _send_http_request(
    self, 
    method: str, 
    url: str, 
    data: dict[str, Any] | None = None
) -> tuple[bool, str]:
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
        try:
            async with session.request(method, url, json=data) as response:
                if response.status == 200:
                    return True, "Success"
                else:
                    error_text = await response.text()
                    return False, f"HTTP {response.status}: {error_text}"
        except aiohttp.ClientError as e:
            return False, f"Network error: {e}"
```

### Retry Logic
Implement retry logic for transient failures:

```python
import asyncio
from typing import Any

async def _send_with_retry(self, data: Any) -> bool:
    for attempt in range(self.max_retries + 1):
        try:
            success = await self._send_to_service(data)
            if success:
                return True
        except Exception as e:
            if attempt == self.max_retries:
                logger.error("Final attempt failed: %s", e)
                return False
            
            # Exponential backoff
            wait_time = 2 ** attempt
            await asyncio.sleep(wait_time)
    
    return False
```

### Message Formatting
Format messages appropriately for your service:

```python
def _format_message(self, message: Message) -> dict[str, Any]:
    return {
        "title": message.title,
        "content": message.content,
        "priority": self._map_priority(message.priority),
        "timestamp": message.timestamp.isoformat() if message.timestamp else None,
        "metadata": message.metadata
    }

def _map_priority(self, priority: str) -> str:
    """Map internal priority to service-specific priority."""
    priority_mapping = {
        "low": "info",
        "normal": "normal", 
        "high": "warning",
        "urgent": "critical"
    }
    return priority_mapping.get(priority, "normal")
```

## Troubleshooting

### Common Issues

1. **Import Errors**: Ensure your plugin directory has `__init__.py`
2. **Discovery Issues**: Check that your plugin metadata is correctly defined
3. **Configuration Errors**: Verify configuration schema matches your validation logic
4. **Network Issues**: Implement proper timeout and retry logic
5. **Type Errors**: Use proper type annotations and validation

### Debugging Tips

1. **Enable Debug Logging**: Set log level to DEBUG to see detailed information
2. **Test Connection**: Implement and use the `test_connection` method
3. **Check Status**: Use the `get_status` method to inspect provider state
4. **Unit Tests**: Write comprehensive unit tests for all methods
5. **Mock Services**: Use mock HTTP servers for testing without external dependencies

## Additional Resources

- [Plugin Discovery Documentation](../loader/README.md)
- [Notification Base Classes](../../notifications/base/README.md)
- [Configuration Models](../../config/models/README.md)
- [Message Models](../../notifications/models/README.md)

## Support

If you need help creating a custom provider:

1. Check the existing Discord and Telegram implementations for examples
2. Review the test files for testing patterns
3. Look at the plugin loader documentation for discovery details
4. Refer to the base provider interface for required methods