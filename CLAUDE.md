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
