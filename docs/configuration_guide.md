# Configuration System Guide

## Overview

The Mover Status configuration system provides a flexible, type-safe way to configure the application using YAML files, environment variables, or programmatic configuration. The system uses Pydantic models for validation and supports multiple configuration sources with automatic merging and precedence rules.

## Quick Start

### Basic Configuration

1. **Create a configuration file** (e.g., `config.yaml`):

```yaml
# Process monitoring configuration
process:
  name: "mover"
  path: "/usr/local/sbin/mover"

# Monitoring behavior
monitoring:
  interval: 30
  detection_timeout: 300
  dry_run: false

# Progress tracking
progress:
  min_change_threshold: 1.0
  estimation_window: 10
  exclude_paths:
    - "/mnt/cache/downloads"
    - "/mnt/cache/temp"

# Notifications
notifications:
  enabled_providers: ["telegram", "discord"]
  events: ["started", "progress", "completed", "failed"]
  rate_limits:
    progress: 300
    status: 60

# Logging
logging:
  level: "INFO"
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  file: "/var/log/mover-status.log"

# Provider configurations
providers:
  telegram:
    bot_token: "YOUR_BOT_TOKEN"
    chat_ids: ["-1001234567890"]
    notifications:
      events: ["started", "progress", "completed", "failed"]
  
  discord:
    webhook_url: "https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_WEBHOOK_TOKEN"
    username: "Mover Status Bot"
    embeds:
      enabled: true
      colors:
        started: 0x00ff00
        progress: 0x0099ff
        completed: 0x00cc00
        failed: 0xff0000
```

2. **Load the configuration**:

```python
from mover_status.config.loader import YamlLoader
from mover_status.config.models.main import AppConfig

# Load from YAML file
loader = YamlLoader()
config_data = loader.load(Path("config.yaml"))

# Validate and create config object
config = AppConfig.model_validate(config_data)
```

### Environment Variable Configuration

Set environment variables with the `MOVER_STATUS_` prefix:

```bash
export MOVER_STATUS_PROCESS__NAME="mover"
export MOVER_STATUS_MONITORING__INTERVAL=30
export MOVER_STATUS_NOTIFICATIONS__ENABLED_PROVIDERS="telegram,discord"
export MOVER_STATUS_PROVIDERS__TELEGRAM__BOT_TOKEN="your_bot_token"
export MOVER_STATUS_PROVIDERS__DISCORD__WEBHOOK_URL="your_webhook_url"
```

## Configuration Schema

### Main Configuration (`AppConfig`)

The root configuration object that contains all application settings.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `monitoring` | `MonitoringConfig` | No | Monitoring behavior configuration |
| `process` | `ProcessConfig` | **Yes** | Process detection configuration |
| `progress` | `ProgressConfig` | No | Progress tracking configuration |
| `notifications` | `NotificationConfig` | No | Notification settings |
| `logging` | `LoggingConfig` | No | Logging configuration |
| `providers` | `ProviderConfig` | No | Provider-specific configurations |

### Process Configuration (`ProcessConfig`)

Configuration for process detection and monitoring.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | `str` | **Yes** | Process name to monitor |
| `path` | `str` | No | Full path to process executable |

**Example:**
```yaml
process:
  name: "mover"
  path: "/usr/local/sbin/mover"
```

### Monitoring Configuration (`MonitoringConfig`)

Configuration for monitoring behavior and timing.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `interval` | `int` | `30` | Monitoring interval in seconds (1-3600) |
| `detection_timeout` | `int` | `300` | Process detection timeout in seconds (1-7200) |
| `dry_run` | `bool` | `false` | Enable dry run mode for testing |

**Example:**
```yaml
monitoring:
  interval: 30
  detection_timeout: 300
  dry_run: false
```

### Progress Configuration (`ProgressConfig`)

Configuration for progress tracking and estimation.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `min_change_threshold` | `float` | `1.0` | Minimum change percentage to trigger notification (0.1-10.0) |
| `estimation_window` | `int` | `10` | Number of samples for progress estimation (1-100) |
| `exclude_paths` | `list[str]` | `[]` | Paths to exclude from progress calculation |

**Example:**
```yaml
progress:
  min_change_threshold: 1.0
  estimation_window: 10
  exclude_paths:
    - "/mnt/cache/downloads"
    - "/mnt/cache/temp"
```

### Notification Configuration (`NotificationConfig`)

Configuration for notification behavior and providers.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled_providers` | `list[str]` | `[]` | List of enabled providers ("telegram", "discord") |
| `events` | `list[str]` | `["started", "progress", "completed", "failed"]` | Events to notify about |
| `rate_limits` | `RateLimitConfig` | See below | Rate limiting configuration |

**Rate Limits:**
| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `progress` | `int` | `300` | Seconds between progress notifications (0-3600) |
| `status` | `int` | `60` | Seconds between status notifications (0-3600) |

**Example:**
```yaml
notifications:
  enabled_providers: ["telegram", "discord"]
  events: ["started", "progress", "completed", "failed"]
  rate_limits:
    progress: 300
    status: 60
```

### Logging Configuration (`LoggingConfig`)

Configuration for application logging.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `level` | `str` | `"INFO"` | Log level ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL") |
| `format` | `str` | `"%(asctime)s - %(name)s - %(levelname)s - %(message)s"` | Log format string |
| `file` | `str` | `None` | Optional log file path |

**Example:**
```yaml
logging:
  level: "INFO"
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  file: "/var/log/mover-status.log"
```

### Provider Configuration (`ProviderConfig`)

Configuration for notification providers.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `telegram` | `TelegramConfig` | `None` | Telegram bot configuration |
| `discord` | `DiscordConfig` | `None` | Discord webhook configuration |

#### Telegram Configuration (`TelegramConfig`)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `bot_token` | `str` | **Yes** | Telegram bot token |
| `chat_ids` | `list[str]` | **Yes** | List of chat IDs to send messages to |
| `notifications` | `TelegramNotificationConfig` | No | Notification settings |
| `message_format` | `TelegramMessageFormat` | No | Message formatting options |
| `templates` | `TelegramTemplateConfig` | No | Message templates |
| `retry` | `RetryConfig` | No | Retry configuration |

**Notification Settings:**
| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `events` | `list[str]` | `["started", "progress", "completed", "failed"]` | Events to notify about |
| `parse_mode` | `str` | `"HTML"` | Message parse mode ("HTML", "Markdown", "MarkdownV2") |
| `disable_web_page_preview` | `bool` | `true` | Disable web page previews |
| `disable_notification` | `bool` | `false` | Send silent notifications |

**Message Format:**
| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `use_emojis` | `bool` | `true` | Include emojis in messages |
| `include_timestamp` | `bool` | `true` | Include timestamp in messages |
| `include_progress_bar` | `bool` | `true` | Include progress bar in messages |
| `progress_bar_length` | `int` | `20` | Length of progress bar (10-50) |

**Example:**
```yaml
providers:
  telegram:
    bot_token: "123456789:ABCdefGHIjklMNOpqrsTUVwxyz"
    chat_ids: ["-1001234567890"]
    notifications:
      events: ["started", "progress", "completed", "failed"]
      parse_mode: "HTML"
      disable_web_page_preview: true
      disable_notification: false
    message_format:
      use_emojis: true
      include_timestamp: true
      include_progress_bar: true
      progress_bar_length: 20
    retry:
      max_attempts: 3
      backoff_factor: 2.0
      timeout: 30
```

#### Discord Configuration (`DiscordConfig`)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `webhook_url` | `str` | **Yes** | Discord webhook URL |
| `username` | `str` | No | Bot username override |
| `avatar_url` | `str` | No | Bot avatar URL |
| `embeds` | `DiscordEmbedConfig` | No | Embed configuration |
| `notifications` | `DiscordNotificationConfig` | No | Notification settings |
| `retry` | `RetryConfig` | No | Retry configuration |

**Embed Configuration:**
| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | `bool` | `true` | Enable rich embeds |
| `colors` | `DiscordColorConfig` | See below | Color scheme |
| `thumbnail` | `bool` | `true` | Include thumbnail |
| `timestamp` | `bool` | `true` | Include timestamp |

**Color Configuration:**
| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `started` | `int` | `0x00ff00` | Color for started events |
| `progress` | `int` | `0x0099ff` | Color for progress events |
| `completed` | `int` | `0x00cc00` | Color for completed events |
| `failed` | `int` | `0xff0000` | Color for failed events |

**Notification Settings:**
| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `events` | `list[str]` | `["started", "progress", "completed", "failed"]` | Events to notify about |
| `mentions` | `dict[str, list[str]]` | `{}` | User/role mentions for events |
| `rate_limits` | `RateLimitConfig` | See above | Rate limiting |

**Example:**
```yaml
providers:
  discord:
    webhook_url: "https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_WEBHOOK_TOKEN"
    username: "Mover Status Bot"
    avatar_url: "https://example.com/bot-avatar.png"
    embeds:
      enabled: true
      colors:
        started: 0x00ff00
        progress: 0x0099ff
        completed: 0x00cc00
        failed: 0xff0000
      thumbnail: true
      timestamp: true
    notifications:
      events: ["started", "progress", "completed", "failed"]
      mentions:
        failed: ["@everyone"]
        started: []
        completed: []
      rate_limits:
        progress: 300
        status: 60
    retry:
      max_attempts: 3
      backoff_factor: 2.0
      timeout: 30
```

## Environment Variables

Environment variables use the `MOVER_STATUS_` prefix and support nested configuration using double underscores (`__`).

### Naming Convention

- **Prefix**: `MOVER_STATUS_`
- **Nested fields**: Use double underscores (`__`) to separate levels
- **Arrays**: Use comma-separated values
- **Booleans**: Use `true`/`false` (case-insensitive)

### Examples

```bash
# Process configuration
export MOVER_STATUS_PROCESS__NAME="mover"
export MOVER_STATUS_PROCESS__PATH="/usr/local/sbin/mover"

# Monitoring configuration
export MOVER_STATUS_MONITORING__INTERVAL=30
export MOVER_STATUS_MONITORING__DETECTION_TIMEOUT=300
export MOVER_STATUS_MONITORING__DRY_RUN=false

# Progress configuration
export MOVER_STATUS_PROGRESS__MIN_CHANGE_THRESHOLD=1.0
export MOVER_STATUS_PROGRESS__ESTIMATION_WINDOW=10
export MOVER_STATUS_PROGRESS__EXCLUDE_PATHS="/mnt/cache/downloads,/mnt/cache/temp"

# Notification configuration
export MOVER_STATUS_NOTIFICATIONS__ENABLED_PROVIDERS="telegram,discord"
export MOVER_STATUS_NOTIFICATIONS__EVENTS="started,progress,completed,failed"
export MOVER_STATUS_NOTIFICATIONS__RATE_LIMITS__PROGRESS=300
export MOVER_STATUS_NOTIFICATIONS__RATE_LIMITS__STATUS=60

# Logging configuration
export MOVER_STATUS_LOGGING__LEVEL="INFO"
export MOVER_STATUS_LOGGING__FILE="/var/log/mover-status.log"

# Telegram provider configuration
export MOVER_STATUS_PROVIDERS__TELEGRAM__BOT_TOKEN="your_bot_token"
export MOVER_STATUS_PROVIDERS__TELEGRAM__CHAT_IDS="-1001234567890"
export MOVER_STATUS_PROVIDERS__TELEGRAM__NOTIFICATIONS__PARSE_MODE="HTML"
export MOVER_STATUS_PROVIDERS__TELEGRAM__MESSAGE_FORMAT__USE_EMOJIS=true

# Discord provider configuration
export MOVER_STATUS_PROVIDERS__DISCORD__WEBHOOK_URL="your_webhook_url"
export MOVER_STATUS_PROVIDERS__DISCORD__USERNAME="Mover Status Bot"
export MOVER_STATUS_PROVIDERS__DISCORD__EMBEDS__ENABLED=true
export MOVER_STATUS_PROVIDERS__DISCORD__EMBEDS__COLORS__STARTED=0x00ff00
```

## Configuration Precedence

The configuration system follows a clear precedence order where later sources override earlier ones:

1. **Default values** (lowest priority)
2. **YAML configuration files**
3. **Environment variables** (highest priority)

### Example

Given this YAML configuration:
```yaml
monitoring:
  interval: 30
  dry_run: false
```

And these environment variables:
```bash
export MOVER_STATUS_MONITORING__INTERVAL=60
```

The final configuration will be:
```yaml
monitoring:
  interval: 60      # Overridden by environment variable
  dry_run: false    # From YAML file
```

## Advanced Configuration

### Loading Configuration in Code

```python
from pathlib import Path
from mover_status.config.loader import YamlLoader, EnvLoader
from mover_status.config.manager import ConfigMerger
from mover_status.config.models.main import AppConfig

# Load from multiple sources
yaml_loader = YamlLoader()
env_loader = EnvLoader()
merger = ConfigMerger(track_sources=True)

# Load configurations
yaml_config = yaml_loader.load(Path("config.yaml"))
env_config = env_loader.load()

# Merge configurations with precedence
merged_config = merger.merge_multiple([yaml_config, env_config])

# Validate and create config object
config = AppConfig.model_validate(merged_config)

# Optional: Get audit trail
audit_trail = merger.get_audit_trail()
print(f"Configuration sources: {audit_trail}")
```

### Custom Configuration Paths

```python
from pathlib import Path
from mover_status.config.loader import YamlLoader

loader = YamlLoader()

# Load from custom path
config_data = loader.load(Path("/etc/mover-status/config.yaml"))

# Load from multiple files
configs = [
    loader.load(Path("base_config.yaml")),
    loader.load(Path("production_config.yaml"))
]

# Merge configurations
merged = merger.merge_multiple(configs)
```

### Environment Variable Prefix Customization

```python
from mover_status.config.loader import EnvLoader

# Use custom prefix
loader = EnvLoader(prefix="MYAPP_")
config = loader.load()

# Use custom mappings
loader = EnvLoader(custom_mappings={
    "DATABASE_URL": "database.url",
    "SECRET_KEY": "security.secret_key"
})
config = loader.load()
```

## Error Handling

The configuration system provides comprehensive error handling with detailed error messages.

### Common Errors

#### Configuration Validation Errors

```python
from mover_status.config.models.main import AppConfig
from mover_status.config.exceptions import ConfigValidationError

try:
    config = AppConfig.model_validate(config_data)
except ConfigValidationError as e:
    print(f"Validation error: {e}")
    print(f"Field errors: {e.errors}")
```

#### File Loading Errors

```python
from mover_status.config.loader import YamlLoader
from mover_status.config.exceptions import ConfigLoadError

try:
    loader = YamlLoader()
    config = loader.load(Path("config.yaml"))
except ConfigLoadError as e:
    print(f"Failed to load config: {e}")
    print(f"File path: {e.file_path}")
```

#### Environment Variable Errors

```python
from mover_status.config.loader import EnvLoader
from mover_status.config.exceptions import EnvLoadError

try:
    loader = EnvLoader()
    config = loader.load()
except EnvLoadError as e:
    print(f"Environment variable error: {e}")
    print(f"Variable: {e.env_var}")
```

#### Configuration Merging Errors

```python
from mover_status.config.manager import ConfigMerger
from mover_status.config.exceptions import ConfigMergeError

try:
    merger = ConfigMerger()
    result = merger.merge_multiple([config1, config2])
except ConfigMergeError as e:
    print(f"Merge error: {e}")
    print(f"Config path: {e.config_path}")
```

## Troubleshooting

### Common Issues

#### 1. Provider Not Configured Error

**Error**: `Enabled providers ['telegram'] are not configured`

**Solution**: Ensure that enabled providers in `notifications.enabled_providers` have corresponding configuration in the `providers` section.

```yaml
# Correct configuration
notifications:
  enabled_providers: ["telegram"]

providers:
  telegram:
    bot_token: "your_token"
    chat_ids: ["your_chat_id"]
```

#### 2. Invalid Environment Variable Format

**Error**: `Invalid environment variable format`

**Solution**: Check environment variable naming and value format.

```bash
# Incorrect
export MOVER_STATUS_MONITORING_INTERVAL=30

# Correct
export MOVER_STATUS_MONITORING__INTERVAL=30
```

#### 3. YAML Parsing Error

**Error**: `Failed to parse YAML file`

**Solution**: Validate YAML syntax and structure.

```bash
# Check YAML syntax
python -c "import yaml; yaml.safe_load(open('config.yaml'))"
```

#### 4. Type Validation Error

**Error**: `Field validation error`

**Solution**: Check field types and constraints.

```yaml
# Incorrect
monitoring:
  interval: "30"  # Should be integer

# Correct
monitoring:
  interval: 30
```

### Debugging Configuration

#### Enable Debug Logging

```python
import logging
from mover_status.config.exceptions import log_config_error

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)

# Log configuration errors
try:
    config = AppConfig.model_validate(config_data)
except Exception as e:
    log_config_error(e, {"config_file": "config.yaml"})
```

#### Inspect Configuration Sources

```python
from mover_status.config.manager import ConfigMerger

merger = ConfigMerger(track_sources=True)
result = merger.merge_multiple([yaml_config, env_config])

# Get audit trail
audit_trail = merger.get_audit_trail()
for path, source in audit_trail.items():
    print(f"{path}: {source}")
```

#### Validate Configuration Schema

```python
from mover_status.config.models.main import AppConfig

# Get JSON schema
schema = AppConfig.model_json_schema()
print(json.dumps(schema, indent=2))
```

## Best Practices

### 1. Configuration Management

- **Use YAML files** for complex configurations
- **Use environment variables** for secrets and deployment-specific values
- **Version control** your configuration files (excluding secrets)
- **Validate configurations** before deployment

### 2. Security

- **Never commit secrets** to version control
- **Use environment variables** for sensitive information
- **Restrict file permissions** on configuration files
- **Rotate credentials** regularly

### 3. Deployment

- **Use different configs** for different environments
- **Test configurations** in staging before production
- **Document configuration changes** in deployment notes
- **Monitor configuration errors** in production

### 4. Maintenance

- **Regular validation** of configuration schemas
- **Update examples** when adding new fields
- **Keep documentation current** with code changes
- **Test error handling** paths

## Example Configurations

### Minimal Configuration

```yaml
# Minimal working configuration
process:
  name: "mover"

providers:
  telegram:
    bot_token: "YOUR_BOT_TOKEN"
    chat_ids: ["YOUR_CHAT_ID"]
```

### Production Configuration

```yaml
# Production configuration with full features
process:
  name: "mover"
  path: "/usr/local/sbin/mover"

monitoring:
  interval: 30
  detection_timeout: 300
  dry_run: false

progress:
  min_change_threshold: 1.0
  estimation_window: 10
  exclude_paths:
    - "/mnt/cache/downloads"
    - "/mnt/cache/temp"
    - "/mnt/cache/.DS_Store"

notifications:
  enabled_providers: ["telegram", "discord"]
  events: ["started", "progress", "completed", "failed"]
  rate_limits:
    progress: 300
    status: 60

logging:
  level: "INFO"
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  file: "/var/log/mover-status.log"

providers:
  telegram:
    bot_token: "YOUR_BOT_TOKEN"
    chat_ids: ["YOUR_CHAT_ID"]
    notifications:
      events: ["started", "progress", "completed", "failed"]
      parse_mode: "HTML"
      disable_web_page_preview: true
      disable_notification: false
    message_format:
      use_emojis: true
      include_timestamp: true
      include_progress_bar: true
      progress_bar_length: 20
    retry:
      max_attempts: 3
      backoff_factor: 2.0
      timeout: 30
  
  discord:
    webhook_url: "YOUR_WEBHOOK_URL"
    username: "Mover Status Bot"
    embeds:
      enabled: true
      colors:
        started: 0x00ff00
        progress: 0x0099ff
        completed: 0x00cc00
        failed: 0xff0000
      thumbnail: true
      timestamp: true
    notifications:
      events: ["started", "progress", "completed", "failed"]
      mentions:
        failed: ["@everyone"]
      rate_limits:
        progress: 300
        status: 60
    retry:
      max_attempts: 3
      backoff_factor: 2.0
      timeout: 30
```

### Development Configuration

```yaml
# Development configuration with debugging
process:
  name: "mover"

monitoring:
  interval: 10
  detection_timeout: 60
  dry_run: true  # Enable dry run for testing

progress:
  min_change_threshold: 0.5
  estimation_window: 5

notifications:
  enabled_providers: ["telegram"]
  events: ["started", "progress", "completed", "failed"]
  rate_limits:
    progress: 30
    status: 10

logging:
  level: "DEBUG"
  format: "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s"

providers:
  telegram:
    bot_token: "YOUR_DEV_BOT_TOKEN"
    chat_ids: ["YOUR_DEV_CHAT_ID"]
    notifications:
      events: ["started", "progress", "completed", "failed"]
```

This comprehensive configuration guide provides all the information needed to effectively configure and use the Mover Status application configuration system.