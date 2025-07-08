# Configuration Setup Guide

This guide explains how to set up your configuration files for the mover-status application.

## Quick Setup

### 1. Create Config Directory

```bash
# Create the configs directory
mkdir -p configs
```

### 2. Copy Main Configuration (Required)

```bash
# Copy the main config file (REQUIRED)
cp configs/examples/config.yaml.example configs/config.yaml

# Edit the main config with your settings
nano configs/config.yaml
```

**Important:** You only need to copy the main config file. Provider-specific configs are automatically created when you enable providers.

### 3. How Multi-File Configuration Works

The configuration system uses **multiple files** that are automatically loaded and merged:

- **`configs/config.yaml`** - Main application configuration *(REQUIRED)*
- **`configs/config_telegram.yaml`** - Telegram settings *(AUTO-CREATED)*
- **`configs/config_discord.yaml`** - Discord settings *(AUTO-CREATED)*

**Provider configs are automatically created with sensible defaults** when you enable a provider in the main config. You only need to customize them if you want to change credentials or templates.

## Configuration Files

### Main Configuration (`configs/config.yaml`)

This is the primary configuration file that controls the core application behavior:

```yaml
# Core monitoring settings
monitoring:
  interval: 30                    # Check every 30 seconds
  detection_timeout: 60          # Wait up to 60 seconds for process detection
  dry_run: false                 # Set to true for testing

# Process detection (REQUIRED)
process:
  name: "mover"                   # Process name to monitor
  paths:                          # Paths where the process might be located
    - "/usr/local/sbin/mover"
    - "/usr/bin/mover"

# Progress tracking
progress:
  min_change_threshold: 5.0       # Minimum % change to trigger notification
  estimation_window: 10           # Samples for ETC calculation
  exclusions:                     # Paths to exclude from size calculations
    - "/.Trash-*"
    - "/lost+found"
    - "/tmp"

# Notification settings
notifications:
  enabled_providers:              # Which providers to use
    - "telegram"
    - "discord"
  events:                         # Which events trigger notifications
    - "started"
    - "progress"
    - "completed"
    - "failed"
  rate_limits:                    # Notification frequency limits
    progress: 300                 # seconds between progress notifications
    status: 60                    # seconds between status notifications

# Logging
logging:
  level: "INFO"                   # Log level
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  file: null                      # Log to console only
```

### Provider Configuration Files (Auto-Created)

#### How Provider Configs Work

When you enable a provider in the main config (e.g., `enabled_providers: ["telegram"]`), the system automatically:

1. **Creates the provider config file** with sensible defaults
2. **Loads and merges** it with the main config
3. **Validates** the configuration structure

#### Telegram Configuration (`configs/config_telegram.yaml`)

**Auto-created** when you enable `telegram` in main config:

```yaml
# This file is automatically created with defaults
# You only need to customize the bot_token and chat_ids
telegram:
  bot_token: "YOUR_BOT_TOKEN_HERE"  # <- Change this
  chat_ids:
    - "YOUR_CHAT_ID_HERE"           # <- Change this
  
  # Everything below uses sensible defaults
  parse_mode: "HTML"
  format:
    disable_notification: false
    disable_web_page_preview: true
  templates:
    started: "🚀 <b>Mover Started</b>\n..."
    progress: "📊 <b>Progress Update</b>\n..."
    # ... many more templates
  rate_limit:
    messages_per_second: 30
    burst_limit: 20
```

#### Discord Configuration (`configs/config_discord.yaml`)

**Auto-created** when you enable `discord` in main config:

```yaml
# This file is automatically created with defaults
# You only need to customize the webhook_url
discord:
  webhook_url: "YOUR_WEBHOOK_URL_HERE"  # <- Change this
  
  # Everything below uses sensible defaults
  embed:
    color: 0x00ff00
    footer_text: "Mover Status Monitor"
    timestamp: true
  templates:
    started:
      title: "🚀 Mover Started"
      description: "The mover process has begun..."
    # ... many more templates
  mentions:
    users: []
    roles: []
```

## Docker Configuration

### Directory Structure

Your directory structure should look like this:

```
your-project/
├── docker-compose.yml
├── Dockerfile
├── configs/
│   ├── config.yaml              # Main config (you create this)
│   ├── config_telegram.yaml     # Telegram config (optional)
│   ├── config_discord.yaml      # Discord config (optional)
│   └── examples/
│       ├── config.yaml.example
│       ├── config_telegram.yaml.example
│       └── config_discord.yaml.example
└── ... (other project files)
```

### Docker Compose Configuration

The docker-compose.yml file is already configured to mount the configs directory:

```yaml
services:
  mover-status:
    # ...
    volumes:
      - "./configs:/app/configs:ro"  # Mount configs directory
```

## Environment Variables

You can override any configuration setting using environment variables with the format:
`MOVER_STATUS_SECTION__SUBSECTION__SETTING`

Examples:
```bash
# Override monitoring interval
MOVER_STATUS_MONITORING__INTERVAL=60

# Override log level
MOVER_STATUS_LOGGING__LEVEL=DEBUG

# Override Telegram bot token
MOVER_STATUS_TELEGRAM__BOT_TOKEN=your_token_here
```

### In Docker Compose

```yaml
services:
  mover-status:
    # ...
    environment:
      - MOVER_STATUS_MONITORING__INTERVAL=60
      - MOVER_STATUS_LOGGING__LEVEL=DEBUG
      - MOVER_STATUS_TELEGRAM__BOT_TOKEN=your_token_here
```

## Getting Provider Credentials

### Telegram Setup

1. **Create a Bot:**
   - Message @BotFather on Telegram
   - Send `/newbot` and follow instructions
   - Save the bot token

2. **Get Chat ID:**
   - Add your bot to a chat/channel
   - Send a message to the bot
   - Visit: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
   - Find your chat ID in the response

### Discord Setup

1. **Create Webhook:**
   - Go to your Discord channel settings
   - Navigate to Integrations → Webhooks
   - Create a new webhook
   - Copy the webhook URL

## Testing Configuration

### Dry Run Mode

Test your configuration without sending notifications:

```yaml
# In configs/config.yaml
monitoring:
  dry_run: true
```

### Docker Test

```bash
# Run with your configuration
docker-compose up mover-status

# Check logs
docker-compose logs -f mover-status
```

### Validate Configuration

```bash
# Run configuration validation
docker-compose run --rm mover-status python -c "
import yaml
with open('/app/configs/config.yaml') as f:
    config = yaml.safe_load(f)
    print('Configuration loaded successfully')
    print(f'Enabled providers: {config.get(\"notifications\", {}).get(\"enabled_providers\", [])}')
"
```

## Troubleshooting

### Common Issues

1. **File Not Found**: Ensure config files exist in the `configs/` directory
2. **Permission Denied**: Check file permissions (`chmod 644 configs/*.yaml`)
3. **Invalid YAML**: Validate YAML syntax online or with a linter
4. **Missing Providers**: Ensure provider config files exist for enabled providers

### Debug Commands

```bash
# Check mounted configs
docker-compose exec mover-status ls -la /app/configs/

# Validate YAML syntax
docker-compose exec mover-status python -c "
import yaml
try:
    with open('/app/configs/config.yaml') as f:
        yaml.safe_load(f)
    print('YAML is valid')
except Exception as e:
    print(f'YAML error: {e}')
"

# Test configuration loading
docker-compose exec mover-status python -c "
from mover_status.config.loader.yaml_loader import YamlLoader
loader = YamlLoader()
config = loader.load('/app/configs/config.yaml')
print('Configuration loaded successfully')
"
```

## Security Best Practices

1. **Never commit secrets**: Add `configs/` to `.gitignore`
2. **Use environment variables**: For sensitive data like tokens
3. **File permissions**: Restrict access to config files
4. **Webhook security**: Use Discord's webhook features for additional security

## Example Complete Setup

Here's a complete example setup for a Telegram-only configuration:

```bash
# 1. Create configs directory
mkdir -p configs

# 2. Create main config
cat > configs/config.yaml << 'EOF'
monitoring:
  interval: 30
  detection_timeout: 60
  dry_run: false

process:
  name: "mover"
  paths:
    - "/usr/local/sbin/mover"

progress:
  min_change_threshold: 5.0
  estimation_window: 10
  exclusions:
    - "/.Trash-*"
    - "/lost+found"

notifications:
  enabled_providers:
    - "telegram"
  events:
    - "started"
    - "progress"
    - "completed"
    - "failed"
  rate_limits:
    progress: 300
    status: 60

logging:
  level: "INFO"
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  file: null
EOF

# 3. Create Telegram config
cat > configs/config_telegram.yaml << 'EOF'
telegram:
  bot_token: "YOUR_BOT_TOKEN_HERE"
  chat_ids:
    - "YOUR_CHAT_ID_HERE"
  parse_mode: "HTML"
  rate_limit:
    messages_per_second: 30
    burst_limit: 20
EOF

# 4. Edit the files with your actual values
nano configs/config_telegram.yaml

# 5. Test the setup
docker-compose up mover-status
```

This setup provides a complete configuration for monitoring your Unraid mover process with Telegram notifications.