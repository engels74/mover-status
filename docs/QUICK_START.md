# Quick Start Guide

Get mover-status running on your Unraid server in minutes using pre-built Docker images.

## Prerequisites

- Unraid server with Docker support
- SSH access to your Unraid server
- Basic familiarity with Docker and docker-compose

## Installation

### 1. Download Files

SSH into your Unraid server and create a directory for the application:

```bash
# SSH into your Unraid server
ssh root@your-unraid-ip

# Create project directory
mkdir -p /mnt/user/appdata/mover-status
cd /mnt/user/appdata/mover-status

# Download docker-compose.yml
curl -fsSL https://raw.githubusercontent.com/engels74/mover-status/main/docker-compose.yml -o docker-compose.yml

# Download config examples
mkdir -p configs
curl -fsSL https://raw.githubusercontent.com/engels74/mover-status/main/configs/examples/config.yaml.example -o configs/config.yaml.example
```

### 2. Configure

```bash
# Copy example config (ONLY file you need to copy)
cp configs/config.yaml.example configs/config.yaml

# Edit configuration
nano configs/config.yaml
```

**Minimum required configuration:**
```yaml
# Basic monitoring settings
monitoring:
  interval: 30
  detection_timeout: 60
  dry_run: false

# Process to monitor (REQUIRED)
process:
  name: "mover"
  paths:
    - "/usr/local/sbin/mover"

# Notification settings
notifications:
  enabled_providers: []  # Start with no providers for testing
  events:
    - "started"
    - "completed"
    - "failed"
```

**Important:** You only need to copy and edit the main `config.yaml` file. Provider-specific configs are automatically created when you enable providers.

### 3. Run

```bash
# Pull the image and start the container
docker-compose up -d

# Check if it's running
docker-compose ps

# View logs
docker-compose logs -f mover-status
```

## Add Notifications (Optional)

### Telegram Setup

1. **Create a Telegram bot:**
   - Message @BotFather on Telegram
   - Send `/newbot` and follow instructions
   - Save the bot token

2. **Get your chat ID:**
   - Add your bot to a chat
   - Send a message to the bot
   - Visit: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
   - Find your chat ID in the response

3. **Enable Telegram in main config:**
   ```yaml
   # In configs/config.yaml
   notifications:
     enabled_providers:
       - "telegram"
   ```

4. **Restart to auto-create Telegram config:**
   ```bash
   docker-compose restart
   ```

5. **Configure credentials:**
   ```bash
   # Edit the auto-created config
   nano configs/config_telegram.yaml
   
   # Update these fields:
   # telegram:
   #   bot_token: "YOUR_BOT_TOKEN_HERE"
   #   chat_ids:
   #     - "YOUR_CHAT_ID_HERE"
   ```

6. **Final restart:**
   ```bash
   docker-compose restart
   ```

### Discord Setup

1. **Create a Discord webhook:**
   - Go to your Discord channel settings
   - Navigate to Integrations → Webhooks
   - Create a new webhook and copy the URL

2. **Enable Discord in main config:**
   ```yaml
   # In configs/config.yaml
   notifications:
     enabled_providers:
       - "discord"
   ```

3. **Restart to auto-create Discord config:**
   ```bash
   docker-compose restart
   ```

4. **Configure webhook URL:**
   ```bash
   # Edit the auto-created config
   nano configs/config_discord.yaml
   
   # Update this field:
   # discord:
   #   webhook_url: "YOUR_WEBHOOK_URL_HERE"
   ```

5. **Final restart:**
   ```bash
   docker-compose restart
   ```

## Testing

### Dry Run Mode

Test your configuration without sending notifications:

```bash
# Edit config to enable dry run
nano configs/config.yaml

# Set dry_run: true in the monitoring section
monitoring:
  dry_run: true

# Restart and check logs
docker-compose restart
docker-compose logs -f mover-status
```

### Manual Test

Trigger the mover manually to test notifications:

```bash
# Check if mover is already running
ps aux | grep mover

# If not running, start it manually (be careful!)
mover start

# Watch the logs
docker-compose logs -f mover-status
```

## Updating

```bash
# Pull latest image
docker-compose pull

# Restart with new image
docker-compose down && docker-compose up -d
```

## Troubleshooting

### Common Issues

1. **Container won't start:**
   ```bash
   # Check logs
   docker-compose logs mover-status
   
   # Check config syntax
   docker-compose config
   ```

2. **No notifications:**
   ```bash
   # Check if providers are enabled
   docker-compose exec mover-status cat /app/configs/config.yaml
   
   # Test in dry run mode
   # Set dry_run: true in config
   ```

3. **Permission errors:**
   ```bash
   # Check volume mounts
   docker-compose exec mover-status ls -la /mnt /var/log
   
   # Ensure config files are readable
   chmod 644 configs/*.yaml
   ```

### Debug Commands

```bash
# Enter container shell
docker-compose exec mover-status bash

# View config
docker-compose exec mover-status cat /app/configs/config.yaml

# Check Python import
docker-compose exec mover-status python -c "import mover_status; print('OK')"

# Manual run
docker-compose exec mover-status python -m mover_status --help
```

## Directory Structure

Your final directory structure should look like:

```
/mnt/user/appdata/mover-status/
├── docker-compose.yml
├── configs/
│   ├── config.yaml               # Main config (you create this)
│   ├── config_telegram.yaml      # Auto-created when telegram enabled
│   ├── config_discord.yaml       # Auto-created when discord enabled
│   └── config.yaml.example       # Downloaded example
└── logs/ (created automatically)
```

**Note:** Provider config files are automatically created with sensible defaults when you enable providers in the main config.

## Next Steps

- Read the [full documentation](https://github.com/engels74/mover-status)
- Customize your configuration in `configs/config.yaml`
- Set up additional notification providers
- Configure advanced monitoring options
- Create custom Docker templates for Unraid WebUI

## Support

If you encounter issues:
1. Check the [troubleshooting guide](https://github.com/engels74/mover-status/blob/main/DOCKER_SETUP.md#troubleshooting)
2. Review the logs: `docker-compose logs -f mover-status`
3. Create an issue: https://github.com/engels74/mover-status/issues

That's it! Your mover-status monitor should now be running and ready to notify you about your Unraid mover process.