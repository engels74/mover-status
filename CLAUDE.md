# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Mover Status is a Python 3.14+ application that monitors Unraid's Mover process and sends real-time progress notifications to Discord and/or Telegram. This is a modern rewrite of a legacy bash script, emphasizing modularity, type safety, and extensibility through a plugin architecture.

**Key Context**: The Unraid Mover has a multi-layer invocation chain (bash wrapper → PHP orchestrator → actual mover binary) managed through `/var/run/mover.pid`. The monitoring must handle scenarios where mover may not start (parity check running, already executing, etc.).

## High-Level Architecture

The codebase follows a **layered, plugin-based architecture** with strict separation of concerns:

### Core Layers
```
src/mover_status/
├── core/          # Application core (monitoring, calculation, orchestration, config)
├── plugins/       # Notification provider plugins (Discord, Telegram, future providers)
├── types/         # Protocols, type aliases, data models
└── utils/         # HTTP client, formatting, templates, logging
```

### Critical Architectural Principles

1. **Plugin Isolation**: Core modules (`core/`, `types/`, `utils/`) MUST NOT reference specific providers. Providers are self-contained packages implementing the `NotificationProvider` Protocol.

2. **Two-Tier Configuration**:
   - Main config (`config/mover-status.yaml`): Application settings + provider enablement flags
   - Provider configs (`config/providers/{provider}.yaml`): Provider-specific settings
   - Secrets via environment variables (prefix: `MOVER_STATUS_*`)

3. **Provider Independence**: Each provider plugin is completely self-contained:
   - Own API client, message formatter, config schema
   - No shared provider code or cross-provider dependencies
   - Adding new providers requires ZERO core code changes

4. **Type Safety**: Comprehensive type hints using Python 3.14+ features (PEP 695 generics, TypeIs narrowing, Protocol-based interfaces). See `.claude/python-313-pro.md` for detailed guidelines.

5. **Structured Concurrency**: `TaskGroup` for concurrent notification delivery (not `gather()`/`create_task()`), enabling proper cancellation, cleanup, and true parallelism in free-threaded builds.

## Development Commands

### Environment Setup
```bash
# Initialize development environment (uv handles everything)
uv sync

# Run the application
uv run mover-status

# Run in development mode with specific config
uv run python -m mover_status --config config/mover-status.yaml
```

### Testing
```bash
# Run full test suite with coverage (requires 80%+)
nox -s tests

# Run specific test categories
pytest tests/unit          # Unit tests only
pytest tests/integration   # Integration tests only
pytest tests/property      # Property-based tests (Hypothesis)

# Run single test file/function
pytest tests/unit/core/test_calculation.py
pytest tests/unit/core/test_calculation.py::test_progress_percentage
```

### Code Quality
```bash
# Lint and format (auto-fix)
nox -s format

# Lint check only (CI mode)
nox -s lint

# Type checking (comprehensive)
nox -s typecheck

# Check provider isolation (architectural rule enforcement)
nox -s check_isolation

# Full quality check before commit
nox -s lint typecheck tests
```

### Individual Tools
```bash
# Ruff (10-100x faster than Black+isort+Flake8)
ruff check .           # Lint
ruff check . --fix     # Auto-fix
ruff format .          # Format

# Type checking (multi-checker approach)
basedpyright           # Comprehensive (slow but thorough)
uvx ty check --watch   # Fast feedback during development

# Coverage
pytest --cov=mover_status --cov-report=html
nox -s coverage        # View HTML coverage report
```

## Key Design Patterns

### Adding a New Provider

1. Create plugin package: `src/mover_status/plugins/new_provider/`
2. Implement `NotificationProvider` Protocol (see `types/protocols.py`)
3. Create provider-specific:
   - `client.py` - API client for webhook delivery
   - `formatter.py` - Message formatting logic
   - `config.py` - Pydantic schema for provider config
4. Add YAML template: `config/providers/new_provider.yaml`
5. Enable in main config: `new_provider_enabled: true`

**No core code changes required** - plugin discovery is automatic.

### Data Flow Overview

```
Monitoring Loop (core/monitoring.py)
  ↓ detects mover start via /var/run/mover.pid
Disk Usage Tracker
  ↓ samples cache usage (excluding configured paths)
Progress Calculator (core/calculation.py)
  ↓ calculates percentage, ETC, rate
Notification Dispatcher
  ↓ concurrent TaskGroup dispatch
Provider Plugins (plugins/discord, plugins/telegram)
  ↓ format messages (embeds, HTML)
HTTP Client (utils/http_client.py)
  ↓ deliver webhooks with timeout/retry
```

### Calculation Logic

Progress calculation mirrors the bash script exactly for behavioral parity:
- **Progress**: `(baseline - current) / baseline * 100`
- **ETC**: `remaining / movement_rate`
- **Thresholds**: Configurable (default: 25%, 50%, 75%, 100%)

Pure functions in `core/calculation.py` enable comprehensive property-based testing with Hypothesis.

## Important Files & References

- **[ARCHITECTURE.md](ARCHITECTURE.md)**: Comprehensive 2500-line architectural design document covering every design decision, data flow, and extension point
- **[.claude/python-313-pro.md](.claude/python-313-pro.md)**: Python 3.14+ best practices (PEP 695, TypeIs, TaskGroup, free-threading, security)
- **[README.md](README.md)**: User-facing documentation, Unraid installation instructions
- **[noxfile.py](noxfile.py)**: Multi-environment testing sessions

## Testing Philosophy

- **Unit tests**: Pure functions (calculation, formatting) with parametrized test cases
- **Integration tests**: Plugin loading, notification flow, configuration validation
- **Property-based tests**: Hypothesis for calculation invariants (progress 0-100%, ETC non-negative, etc.)
- **Fixture-based**: Pytest fixtures mirror project structure (see `tests/` directory)
- **Coverage requirement**: Minimum 80% (enforced in CI)

## Security Considerations

1. **Secrets Management**: Never commit secrets. Use environment variables (`MOVER_STATUS_*` prefix) referenced in YAML configs.
2. **Webhook Validation**: Discord/Telegram webhook URLs validated at config load time (scheme, domain, format).
3. **Dependency Security**:
   - `pip-audit` for vulnerability scanning
   - Hash verification in production: `uv export --generate-hashes`
   - Multi-tool scanning (bandit, safety) in nox sessions
4. **Input Sanitization**: Pydantic validation at all API boundaries (configuration, notification data).

## Type Checking Notes

- **Multi-checker CI**: Both `basedpyright` (comprehensive) and `ty` (fast) must pass
- **No bare `# type: ignore`**: Use rule-scoped ignores: `# pyright: ignore[reportUnknownVariableType]`
- **Protocol-based interfaces**: Prefer small composable Protocols (1-3 methods) over inheritance
- **Modern syntax**: Use PEP 695 `class[T]`/`def[T]` instead of `TypeVar`, `type` statement for aliases

## Migration Context

This Python application replaces `.old_script/moverStatus.sh` (bash). Key migration requirements:
- **Feature parity**: All bash script functionality preserved
- **Behavioral parity**: Same notification timing, message content, calculation logic
- **Rollback plan**: Bash script preserved during migration phase

## Common Gotchas

1. **Provider isolation**: Never import provider-specific code in `core/`, `types/`, or `utils/`. Use the `nox -s check_isolation` session to verify.
2. **Secrets in logs**: Ensure webhook URLs and tokens never appear in log output or error messages.
3. **TaskGroup vs gather()**: Always use `TaskGroup` for structured concurrency (automatic cleanup, proper cancellation).
4. **Dataclass slots**: Use `@dataclass(slots=True)` for 40% memory savings on data-heavy structures.
5. **Async file operations**: Disk usage calculations are CPU-bound, offload to thread pool via `asyncio.to_thread`.

## Unraid Integration

- **Execution**: Runs via User Scripts plugin in background mode (continuous monitoring loop)
- **Environment Variables**: User Scripts UI supports secret configuration without hardcoding
- **Logging**: Integrates with Unraid syslog for operational transparency
- **Startup**: Configurable to start with array start via User Scripts scheduling
- **PID File**: Monitors `/var/run/mover.pid` (created by Mover Tuning Plugin's PHP orchestrator)
