# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Mover Status is a Python 3.14+ monitoring application for Unraid systems that tracks the Mover process (SSD cache → HDD array data transfer) and sends real-time progress notifications to Discord and/or Telegram. This is a rewrite of a legacy bash script with a focus on extensibility, type safety, and maintainability.

## Development Commands

### Package Management (uv)
```bash
# Install dependencies
uv sync

# Run application
uv run mover-status

# Add runtime dependency
uv add <package>

# Add dev dependency
uv add --dev <package>
```

### Testing
```bash
# Run all tests with coverage (requires 80% minimum)
nox -s tests

# Run tests directly (faster for iteration)
uv run pytest

# Run specific test category
uv run pytest -m unit          # Unit tests only
uv run pytest -m integration   # Integration tests only
uv run pytest -m property      # Property-based tests only

# Run specific test file
uv run pytest tests/unit/core/test_calculation.py

# Run with verbose output
uv run pytest -v

# Generate coverage report
nox -s coverage
```

### Code Quality
```bash
# Lint and format check
nox -s lint

# Auto-fix and format code
nox -s format

# Type checking (basedpyright)
nox -s typecheck

# Check provider isolation (critical architectural rule)
nox -s check_isolation

# Run all quality checks
nox
```

### Individual Tools
```bash
# Ruff (linting and formatting)
uv run ruff check . --fix      # Auto-fix lint issues
uv run ruff format .           # Format code

# Type checking
uvx basedpyright@latest        # Comprehensive type check
uvx basedpyright src/          # Check specific directory
```

## Architecture

**CRITICAL: No Provider-Specific References in Core Code**

Core modules (`core/`, `types/`, `utils/`) MUST maintain complete provider agnosticism:
- **Code**: NEVER import, reference, or implement logic for specific providers (Discord, Telegram, etc.)
- **Documentation**: NEVER mention specific provider names in docstrings, comments, or examples
- **Type Definitions**: Use generic examples only (e.g., "webhook services", "chat platforms", "provider_a")
- **Violations**: Any hardcoded provider name outside `plugins/` directory is an architectural violation

This ensures the plugin architecture remains extensible and prevents tight coupling between core and providers.

### Layered Design

1. **Core** (`src/mover_status/core/`): Monitoring, progress calculation, disk tracking
2. **Plugins** (`src/mover_status/plugins/`): Self-contained notification providers
3. **Utils** (`src/mover_status/utils/`): Shared infrastructure (HTTP, formatting, templates, logging)
4. **Types** (`src/mover_status/types/`): Protocol definitions, type aliases, shared data models

### Critical Architectural Rule: Provider Isolation

**NEVER reference specific providers (Discord, Telegram, etc.) in core/, types/, or utils/ modules.**

- Core modules must remain completely provider-agnostic
- Use generic examples only ("webhook services", "chat platforms", "provider_a")
- Violations: Any hardcoded provider name outside `plugins/` directory
- Enforcement: `nox -s check_isolation` validates this rule
- Rationale: Ensures plugin architecture remains extensible without core modifications

### Plugin Architecture

Each provider is self-contained in `plugins/<provider>/`:
```
plugins/discord/
├── __init__.py       # Plugin metadata and entry point
├── provider.py       # NotificationProvider Protocol implementation
├── client.py         # Provider-specific API client
├── formatter.py      # Message formatter for platform
├── config.py         # Pydantic configuration schema
└── constants.py      # Provider-specific constants
```

**Adding new providers requires zero changes to core code.** Simply:
1. Create new directory in `plugins/` following naming convention
2. Implement NotificationProvider Protocol
3. Define Pydantic config schema
4. Add provider-specific YAML template to `config/providers/`

### Concurrency Model

- **Structured Concurrency**: Uses `asyncio.TaskGroup` for notification dispatch
- **Provider Isolation**: Single provider failure doesn't block others
- **Async I/O**: Concurrent webhook delivery to all providers
- **CPU Offloading**: `asyncio.to_thread` for disk usage calculations
- **Timeout Management**: Per-provider timeouts prevent hung requests

### Configuration System

Two-tier YAML configuration:
- **Main config** (`config/mover-status.yaml`): Application settings, provider enablement
- **Provider configs** (`config/providers/<provider>.yaml`): Provider-specific settings

Environment variable support: Use `${VARIABLE_NAME}` syntax in YAML (optional, direct values preferred).

## Type Safety

### Requirements
- **Type Checker**: basedpyright in "recommended" mode
- **Enforcement**: Zero errors, zero warnings (enforced by CI)
- **Ignores**: Only per-line, rule-scoped (`# pyright: ignore[rule-code]`)

### Modern Python 3.14 Features
- **PEP 695 Generics**: `class[T]` and `def[T]` syntax
- **Type Aliases**: `type` statement for complex aliases
- **Protocols**: Small, composable Protocol definitions (1-3 methods)
- **TypeIs**: Precise type narrowing for predicates
- **Built-in Generics**: Use `list[T]`, `dict[K, V]` not `typing.List`, `typing.Dict`

### Import Conventions
```python
# ALWAYS use absolute imports from package root
from mover_status.core.monitoring import MonitoringEngine
from mover_status.types.protocols import NotificationProvider
from mover_status.utils.formatting import format_bytes

# NEVER use relative imports
from ..core import monitoring  # ❌ Wrong
```

## Testing Strategy

### Test Structure
Tests mirror source structure:
- `tests/unit/core/` → `src/mover_status/core/`
- `tests/unit/plugins/` → `src/mover_status/plugins/`
- `tests/integration/` → Multi-component integration tests
- `tests/property/` → Hypothesis property-based tests

### Test Categories (pytest markers)
- `@pytest.mark.unit`: Fast, isolated tests with mocks
- `@pytest.mark.integration`: Multi-component tests (plugin loading, notification flow)
- `@pytest.mark.property`: Hypothesis-based invariant tests for calculations

### Coverage Requirements
- Minimum 80% coverage (enforced by pytest)
- Pure functions (calculation.py) should have 100% coverage
- Use fixtures for consistent test data

## Common Development Patterns

### Adding a Notification Provider
1. Create `plugins/<provider>/` directory
2. Implement files: `__init__.py`, `provider.py`, `client.py`, `formatter.py`, `config.py`
3. Create `config/providers/<provider>.yaml.template`
4. Add integration tests in `tests/integration/`
5. Run `nox -s check_isolation` to verify no core contamination

### Working with Calculations
- All calculation functions in `core/calculation.py` are pure functions
- Add property-based tests with Hypothesis for invariants
- Example invariants: progress ∈ [0, 100], ETC in future, rate ≥ 0

### Error Handling
- Use exception groups (`except*`) for multi-provider failures
- Provider exceptions must be isolated (use try/except in provider tasks)
- Log with structured context (correlation IDs, provider names)

## Docker Deployment

### Quick Start

```bash
# Build and start container
docker compose up -d

# View logs
docker compose logs -f

# Test configuration (dry-run mode)
docker compose run --rm mover-status --dry-run

# Stop container
docker compose down
```

### Prerequisites

Before running the containerized application, ensure:

1. **Configuration Files**: Create your config directory with required YAML files
   ```bash
   # Copy templates and configure
   mkdir -p config/providers
   cp config/mover-status.yaml.template config/mover-status.yaml
   cp config/providers/discord.yaml.template config/providers/discord.yaml  # If using Discord
   cp config/providers/telegram.yaml.template config/providers/telegram.yaml  # If using Telegram

   # Edit configs with your webhook URLs and settings
   vim config/mover-status.yaml
   vim config/providers/discord.yaml
   ```

2. **Verify Unraid Paths**: Ensure volume mounts in [docker-compose.yml](docker-compose.yml) match your system
   - Default monitored path: `/mnt/cache`
   - Additional cache pools: Uncomment relevant volume mounts
   - PID file location: `/var/run/mover.pid` (standard on Unraid)

3. **Set Secrets** (optional): Use environment variables instead of hardcoding in YAML
   ```bash
   # Create .env file
   echo "DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/YOUR_ID/YOUR_TOKEN" > .env
   echo "TELEGRAM_BOT_TOKEN=1234567890:YOUR_BOT_TOKEN" >> .env
   echo "TELEGRAM_CHAT_ID=-1001234567890" >> .env
   ```

### Volume Mounts Explained

The container requires specific volume mounts for Unraid integration:

| Mount | Purpose | Access | Required |
|-------|---------|--------|----------|
| `/var/run:/var/run:ro` | Monitor `/var/run/mover.pid` for process detection | Read-only | Yes |
| `/mnt/cache:/mnt/cache:ro` | Calculate disk usage for progress tracking | Read-only | Yes |
| `/proc:/proc:ro` | Validate mover process is running | Read-only | Yes |
| `./config:/app/config:ro` | Load application and provider configurations | Read-only | Yes |
| `/dev/log:/dev/log:rw` | Send logs to Unraid syslog (operational visibility) | Read-write | No* |

\* If `/dev/log` is unavailable, use `--no-syslog` flag to disable syslog integration.

**Security Note**: All mounts are read-only except `/dev/log` (syslog). The application never modifies system files, only monitors them.

### Configuration in Containers

Two approaches for managing secrets:

**Approach 1: Environment Variables** (Recommended for secrets)
```yaml
# docker-compose.yml
environment:
  - DISCORD_WEBHOOK_URL=${DISCORD_WEBHOOK_URL}
  - TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
```

```yaml
# config/providers/discord.yaml
webhook_url: ${DISCORD_WEBHOOK_URL}
```

**Approach 2: Direct Values** (Simpler, less secure)
```yaml
# config/providers/discord.yaml
webhook_url: https://discord.com/api/webhooks/1234567890/abcdef...
```

### Running Options

```bash
# Production: Run in background with auto-restart
docker compose up -d

# Development: See logs in foreground
docker compose up

# Test configuration without sending notifications
docker compose run --rm mover-status --dry-run

# Debug with verbose logging
docker compose run --rm mover-status --log-level DEBUG

# Disable syslog (if /dev/log unavailable)
docker compose run --rm mover-status --no-syslog

# Monitor specific paths
docker compose run --rm mover-status /mnt/cache /mnt/cache2

# Rebuild after code changes
docker compose build
docker compose up -d
```

### Docker Image

Pre-built images are available from GitHub Container Registry:

```bash
# Pull latest image
docker pull ghcr.io/engels74/mover-status:latest

# Run directly (without docker-compose)
docker run -d \
  --name mover-status \
  --user 1000:1000 \
  --read-only \
  --tmpfs /tmp \
  --security-opt no-new-privileges:true \
  -v /var/run:/var/run:ro \
  -v /mnt/cache:/mnt/cache:ro \
  -v /proc:/proc:ro \
  -v ./config:/app/config:ro \
  -v /dev/log:/dev/log:rw \
  ghcr.io/engels74/mover-status:latest
```

### Building from Source

```bash
# Build image
docker build -t mover-status:local .

# Run built image
docker run --rm mover-status:local --help
```

### Troubleshooting

**Container exits immediately:**
```bash
# Check logs for configuration errors
docker compose logs

# Verify config files exist and are valid
docker compose run --rm mover-status --dry-run
```

**"Permission denied" errors:**
```bash
# Ensure user UID:GID matches file ownership
# Default is 1000:1000, adjust in docker-compose.yml if needed
user: "99:100"  # Example: Unraid 'nobody' user
```

**Syslog errors:**
```bash
# If /dev/log is unavailable, disable syslog
docker compose run --rm mover-status --no-syslog

# Or add flag to docker-compose.yml
command: ["--no-syslog"]
```

**Notifications not sending:**
```bash
# Test configuration in dry-run mode
docker compose run --rm mover-status --dry-run

# Check provider configs are mounted correctly
docker compose exec mover-status cat /app/config/providers/discord.yaml

# Verify network connectivity
docker compose exec mover-status ping -c 3 discord.com
```

**Can't find mover.pid:**
```bash
# Verify PID file is accessible from container
docker compose run --rm mover-status ls -la /var/run/mover.pid

# Check volume mount is correct
docker compose config | grep /var/run
```

### Security Hardening

The Docker configuration follows security best practices:

- **Non-root user**: Runs as UID 1000 (configurable)
- **Read-only root filesystem**: Prevents container modification
- **No privileged mode**: Standard user permissions only
- **No new privileges**: Prevents privilege escalation
- **Minimal attack surface**: Outbound HTTPS only, no inbound ports
- **Resource limits**: Memory capped at 256MB, CPU at 0.5 cores

**Network Security:**
- Only outbound HTTPS to Discord/Telegram APIs required
- No inbound network connections needed
- Bridge network mode (isolated from host network)

**File System Permissions:**
```bash
# Application NEVER writes to:
- /var/run/mover.pid (read-only monitoring)
- /mnt/cache (read-only disk usage calculation)
- /proc (read-only process validation)
- Config files (read-only at startup)

# Application ONLY writes to:
- /dev/log (syslog messages, optional)
- /tmp (ephemeral temp files)
```

### CI/CD Integration

Docker images are automatically built and pushed on every commit to `main`:

- **Registry**: GitHub Container Registry (ghcr.io)
- **Tags**: `latest` (main branch), branch names, PR numbers, commit SHAs
- **Workflow**: [.github/workflows/ci.yml](.github/workflows/ci.yml)
- **Quality Gates**: All tests, linting, type checking, and provider isolation checks must pass

Pull pre-built images:
```bash
docker pull ghcr.io/engels74/mover-status:latest
docker pull ghcr.io/engels74/mover-status:feat-rewrite_v5
docker pull ghcr.io/engels74/mover-status:main-a3abd46
```

## Project-Specific Context

### Unraid Integration
- Runs via User Scripts plugin in background mode
- Monitors `/var/run/mover.pid` for process detection
- Logs to Unraid syslog for operational visibility
- Configuration typically in `/boot/config/plugins/mover-status/`

### Process Monitoring
- Detects mover process via PID file creation/deletion
- Process variants: `/usr/local/sbin/mover.old` or `/usr/local/emhttp/plugins/ca.mover.tuning/age_mover`
- Continuous loop: waiting → started → monitoring → completed → waiting

### Data Flow
1. PID file created → baseline disk usage captured
2. Periodic sampling → progress calculation → threshold evaluation
3. Notification event → concurrent dispatch to all providers → formatted messages
4. Provider-specific formatting (Discord embeds, Telegram HTML)

## Key Files and Responsibilities

- `core/monitoring.py`: PID file watching, state machine (waiting/started/monitoring/completed)
- `core/calculation.py`: Pure functions for progress/ETC calculations
- `core/disk_tracker.py`: Disk usage sampling with exclusion path support
- `plugins/registry.py`: Provider instance management with health tracking
- `plugins/loader.py`: Dynamic plugin discovery and initialization
- `types/protocols.py`: All Protocol definitions (NotificationProvider, MessageFormatter, HTTPClient)

## Documentation
- **Architecture Details**: See `.kiro/specs/bash-to-python-conversion/design.md` for comprehensive design
- **Project Structure**: See `.kiro/steering/structure.md` for module organization principles
- **Technology Stack**: See `.kiro/steering/tech.md` for tooling and patterns
