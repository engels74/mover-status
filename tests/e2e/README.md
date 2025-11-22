# End-to-End (E2E) Mover Workflow Tests

This directory contains end-to-end tests that simulate the complete Unraid mover workflow in a containerized environment. The tests verify that mover-status correctly detects, monitors, and reports on the mover process lifecycle by sending real notifications to Discord and Telegram.

## Overview

The E2E test suite simulates a realistic Unraid mover scenario:

1. **Mover simulator** creates test data files and progressively moves them from "cache" to "array"
2. **Mover-status** detects the PID file, monitors disk usage, calculates progress, and sends notifications
3. **Real notifications** are sent to Discord and Telegram using test webhooks/credentials
4. **Test orchestrator** verifies that all expected notifications were sent successfully

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Docker Compose E2E Environment                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌────────────────────┐         ┌──────────────────────┐       │
│  │ mover-status       │         │ mover-simulator      │       │
│  │                    │         │                      │       │
│  │ - Monitors PID     │◄────────│ - Creates PID file   │       │
│  │ - Tracks disk      │         │ - Creates test data  │       │
│  │ - Sends webhooks   │         │ - Moves files        │       │
│  └────────┬───────────┘         │ - Deletes PID file   │       │
│           │                     └──────────────────────┘       │
│           │                                                     │
│           │  Shared Volumes:                                   │
│           │  - /var/run (PID file)                             │
│           │  - /mnt/cache (source data)                        │
│           │  - /mnt/user (destination)                         │
│           │                                                     │
└───────────┼─────────────────────────────────────────────────────┘
            │
            │ Real HTTP Requests
            ▼
    ┌───────────────┐         ┌───────────────┐
    │   Discord     │         │   Telegram    │
    │   Webhook     │         │   Bot API     │
    └───────────────┘         └───────────────┘
```

## Files

### Core Components

- **[mover_simulator.py](mover_simulator.py)** - Python script that simulates Unraid mover process behavior
  - Creates PID file (`/var/run/mover.pid`)
  - Generates test data files (100MB by default)
  - Progressively moves files from cache to array
  - Deletes PID file on completion

- **[run_e2e_test.py](run_e2e_test.py)** - Test orchestration script
  - Builds Docker image
  - Starts Docker Compose services
  - Monitors logs for notification events
  - Verifies success criteria
  - Reports pass/fail status

- **[docker-compose.e2e.yml](docker-compose.e2e.yml)** - Docker Compose configuration
  - Defines two services: `mover-status` and `mover-simulator`
  - Creates shared volumes for PID file and filesystem
  - Configures environment variables for secrets

### Configuration

- **[config/mover-status.yaml](config/mover-status.yaml)** - E2E test-specific configuration
  - Fast polling intervals (0.5s PID check, 2s sampling)
  - Low progress thresholds (10%, 25%, 50%, 75%, 100%)
  - DEBUG logging enabled
  - Both Discord and Telegram providers enabled

- **[config/providers/discord.yaml](config/providers/discord.yaml)** - Discord provider config
  - Uses `${E2E_DISCORD_WEBHOOK_URL}` from environment
  - Custom username: "Mover Status E2E Test"
  - Orange embed color for easy identification

- **[config/providers/telegram.yaml](config/providers/telegram.yaml)** - Telegram provider config
  - Uses `${E2E_TELEGRAM_BOT_TOKEN}` and `${E2E_TELEGRAM_CHAT_ID}` from environment
  - HTML parse mode enabled

## Running E2E Tests

### Prerequisites

#### 1. Create Test Notification Channels

To avoid spamming production channels, create dedicated test channels:

**Discord:**
1. Create a Discord server or use an existing one
2. Create a channel named `#mover-status-e2e-tests`
3. Go to Server Settings → Integrations → Webhooks → New Webhook
4. Name it "Mover Status E2E Test"
5. Select the `#mover-status-e2e-tests` channel
6. Copy the webhook URL

**Telegram:**
1. Create a new bot via [@BotFather](https://t.me/BotFather)
   - Send `/newbot`
   - Name it something like "Mover Status E2E Test Bot"
   - Copy the bot token (format: `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`)
2. Create a test group or use an existing one
3. Add the bot to the group
4. Get the chat ID:
   ```bash
   # Send a message in the group, then run:
   curl "https://api.telegram.org/bot<BOT_TOKEN>/getUpdates" | jq
   # Look for "chat": {"id": -1001234567890, ...}
   ```

#### 2. Set Environment Variables

**Local development:**
```bash
export E2E_DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_TOKEN"
export E2E_TELEGRAM_BOT_TOKEN="1234567890:ABCdefGHIjklMNOpqrsTUVwxyz"
export E2E_TELEGRAM_CHAT_ID="-1001234567890"
```

**GitHub Actions:**
1. Go to repository Settings → Secrets and variables → Actions
2. Add the following secrets:
   - `E2E_DISCORD_WEBHOOK_URL`
   - `E2E_TELEGRAM_BOT_TOKEN`
   - `E2E_TELEGRAM_CHAT_ID`

### Running Locally

#### Option 1: Using the Orchestrator Script (Recommended)

```bash
# From project root
uv run python tests/e2e/run_e2e_test.py

# With debug logging
uv run python tests/e2e/run_e2e_test.py --log-level DEBUG

# Keep containers running for debugging
uv run python tests/e2e/run_e2e_test.py --keep-running

# Skip Docker build (reuse existing image)
uv run python tests/e2e/run_e2e_test.py --skip-build
```

#### Option 2: Using Docker Compose Directly

```bash
# Build the image
docker compose -f tests/e2e/docker-compose.e2e.yml build

# Run the test
docker compose -f tests/e2e/docker-compose.e2e.yml up --abort-on-container-exit

# View logs
docker compose -f tests/e2e/docker-compose.e2e.yml logs -f

# Clean up
docker compose -f tests/e2e/docker-compose.e2e.yml down -v
```

### Running in GitHub Actions

#### Manual Trigger

1. Go to the "Actions" tab in your GitHub repository
2. Select "E2E Mover Test" workflow
3. Click "Run workflow"
4. Select log level (default: INFO)
5. Click "Run workflow"

#### Automatic Trigger (Optional)

Uncomment the `pull_request` trigger in [`.github/workflows/e2e-mover-test.yml`](../../.github/workflows/e2e-mover-test.yml) to run E2E tests on PRs to main:

```yaml
on:
  workflow_dispatch:
    # ...
  pull_request:
    branches: [main]
```

**Note:** E2E tests will only run if secrets are configured. The workflow automatically skips if secrets are missing.

## Success Criteria

An E2E test passes when:

1. ✅ **Mover simulator** completes successfully
2. ✅ **Started notification** sent to both Discord and Telegram
3. ✅ **At least one progress notification** sent to both providers
4. ✅ **Completed notification** sent to both providers
5. ✅ **No errors** in mover-status logs
6. ✅ **Test completes** within 5 minutes

## Expected Notifications

During a typical E2E test run, you should see the following notifications in your test channels:

### Discord

1. **Started** - Blue embed with "Mover started" message
2. **Progress (10%)** - Progress bar at 10%
3. **Progress (25%)** - Progress bar at 25%
4. **Progress (50%)** - Progress bar at 50%
5. **Progress (75%)** - Progress bar at 75%
6. **Completed** - Green embed with "Mover completed" message

### Telegram

1. **Started** - Bold message "**Mover started**"
2. **Progress (10%)** - Progress update with ETC
3. **Progress (25%)** - Progress update with ETC
4. **Progress (50%)** - Progress update with ETC
5. **Progress (75%)** - Progress update with ETC
6. **Completed** - Bold message "**Mover completed**"

**Note:** Actual notification count may vary depending on mover timing and threshold evaluation.

## Troubleshooting

### Test Fails with "Missing required environment variables"

**Problem:** Environment variables are not set.

**Solution:**
```bash
export E2E_DISCORD_WEBHOOK_URL="your_webhook_url"
export E2E_TELEGRAM_BOT_TOKEN="your_bot_token"
export E2E_TELEGRAM_CHAT_ID="your_chat_id"
```

### No Notifications Received

**Problem:** Webhooks are being sent but not appearing in channels.

**Possible causes:**
1. Webhook URL is incorrect or expired
2. Bot is not added to the Telegram group
3. Telegram chat ID is incorrect
4. Rate limiting (running tests too frequently)

**Solution:**
- Verify webhook URLs and credentials
- Check Discord/Telegram for errors
- Wait a few minutes and retry
- Check logs: `docker compose -f tests/e2e/docker-compose.e2e.yml logs`

### Test Times Out

**Problem:** Test exceeds 5-minute timeout.

**Possible causes:**
1. Mover simulator is stuck (file I/O issues)
2. Mover-status is not detecting PID file
3. Network issues preventing webhook delivery

**Solution:**
```bash
# Check container status
docker ps -a

# Check logs for both services
docker compose -f tests/e2e/docker-compose.e2e.yml logs mover-simulator
docker compose -f tests/e2e/docker-compose.e2e.yml logs mover-status

# Run with debug logging
uv run python tests/e2e/run_e2e_test.py --log-level DEBUG --keep-running
```

### "Permission denied" Errors

**Problem:** Docker containers cannot write to volumes.

**Solution:**
```bash
# Ensure Docker has proper permissions
docker compose -f tests/e2e/docker-compose.e2e.yml down -v
docker system prune -f

# Retry test
uv run python tests/e2e/run_e2e_test.py
```

### Containers Exit Immediately

**Problem:** Configuration errors or missing dependencies.

**Solution:**
```bash
# Check configuration syntax
uv run python -c "import yaml; yaml.safe_load(open('tests/e2e/config/mover-status.yaml'))"

# Rebuild Docker image
docker compose -f tests/e2e/docker-compose.e2e.yml build --no-cache

# Check for missing Python dependencies
uv sync --frozen --group dev
```

## Customization

### Adjust Test Duration

Edit [docker-compose.e2e.yml](docker-compose.e2e.yml):

```yaml
services:
  mover-simulator:
    command:
      - "--duration=30"        # Shorter test (30 seconds)
      - "--chunk-interval=2"   # Faster chunks (2 seconds)
```

### Adjust Test Data Size

```yaml
services:
  mover-simulator:
    command:
      - "--test-data-size=50"  # Create 50MB instead of 100MB
```

### Change Notification Thresholds

Edit [config/mover-status.yaml](config/mover-status.yaml):

```yaml
notifications:
  thresholds:
    - 0.0
    - 50.0
    - 100.0  # Only start, 50%, and completion
```

## Development

### Running Mover Simulator Standalone

```bash
# Create test data and move it
uv run python tests/e2e/mover_simulator.py \
  --source-dir /tmp/test-cache \
  --dest-dir /tmp/test-array \
  --pid-file /tmp/test-mover.pid \
  --create-test-data \
  --test-data-size 50 \
  --duration 30 \
  --log-level DEBUG
```

### Testing Without Real Webhooks

For testing the simulation logic without sending notifications:

1. Set `dry_run: true` in [config/mover-status.yaml](config/mover-status.yaml)
2. Run the E2E test as normal
3. Notifications will be logged but not sent

```yaml
application:
  dry_run: true  # Log notification payloads without sending
```

### Adding New Test Scenarios

To test edge cases or specific behaviors:

1. Copy `docker-compose.e2e.yml` to a new file (e.g., `docker-compose.e2e-edge-case.yml`)
2. Modify simulator parameters for the scenario
3. Run with: `docker compose -f tests/e2e/docker-compose.e2e-edge-case.yml up`

## CI/CD Integration

The E2E test workflow ([`.github/workflows/e2e-mover-test.yml`](../../.github/workflows/e2e-mover-test.yml)) includes:

- ✅ Automatic Docker image building with caching
- ✅ Secret validation (skips if not configured)
- ✅ Log collection on failure
- ✅ Artifact upload for debugging
- ✅ Automatic cleanup of Docker resources
- ✅ Summary job for clear pass/fail status

## Security Considerations

### Webhook Security

- **Never commit** webhook URLs or bot tokens to version control
- Use **environment variables** or GitHub Secrets exclusively
- Consider using **dedicated test channels** to avoid production data leakage
- **Rotate credentials** periodically

### Rate Limiting

- Discord: 30 requests per minute per webhook
- Telegram: 30 messages per second per bot

E2E tests should not hit these limits, but be aware when running tests frequently during development.

### Data Privacy

- Test data is randomly generated (no real user data)
- Test data is deleted after each run (`docker compose down -v`)
- Temporary files are cleaned up automatically

## Related Documentation

- [Main Project README](../../README.md)
- [CLAUDE.md - Development Guidelines](../../CLAUDE.md)
- [Docker Deployment Guide](../../CLAUDE.md#docker-deployment)
- [CI/CD Workflow](.github/workflows/ci.yml)

## Contributing

When modifying E2E tests:

1. Ensure tests remain **fast** (< 5 minutes)
2. Maintain **idempotency** (safe to run multiple times)
3. Follow **type safety** guidelines (basedpyright compliance)
4. Update this README with any new features or requirements
5. Test both **locally** and **in CI** before merging

## Support

If you encounter issues with E2E tests:

1. Check the [Troubleshooting](#troubleshooting) section
2. Review logs: `docker compose -f tests/e2e/docker-compose.e2e.yml logs`
3. Run with debug logging: `--log-level DEBUG`
4. Open an issue at https://github.com/engels74/mover-status/issues with:
   - Full error messages
   - Docker logs
   - Environment (local vs CI, OS version)
   - Steps to reproduce
