---
inclusion: always
---

# Technology Stack

## Python Version

- **Required**: Python 3.14+
- **Rationale**: Modern type system (PEP 695 generics, TypeIs), structured concurrency (TaskGroup), performance improvements (tail-call interpreter, optional JIT)
- **Free-Threading**: Designed to leverage free-threading for concurrent webhook delivery when available

## Build System & Package Management

- **Package Manager**: uv (10-100x faster than pip/poetry)
- **Build Backend**: uv_build (zero-config for pure Python projects)
- **Lock File**: uv.lock for reproducible builds
- **Project Structure**: src/ layout with `src/mover_status/` as main package

### Common Commands

```bash
# Install dependencies
uv sync

# Run application
uv run mover-status

# Add dependency
uv add <package>

# Add dev dependency
uv add --dev <package>

# Run tests
uv run pytest

# Type checking
uvx basedpyright@latest

# Linting and formatting
uv run ruff check . --fix
uv run ruff format .
```

## Core Dependencies

### Runtime
- **aiohttp** or **httpx**: Async HTTP client for webhook delivery
- **pydantic**: Configuration validation and data modeling at API boundaries
- **PyYAML**: YAML configuration file parsing

### Development
- **pytest**: Testing framework with fixtures and parametrization
- **pytest-asyncio**: Async test support
- **hypothesis**: Property-based testing for calculations
- **ruff**: Unified linting and formatting (replaces Black, isort, Flake8)
- **basedpyright**: Type checker with strict mode
- **ty**: Ultra-fast type checker for development feedback

## Type Safety Tooling

- **Type Checker**: basedpyright with `typeCheckingMode = "recommended"`
- **Enforcement**: 0 errors, 0 warnings across all code including tests
- **CI Pipeline**: Both basedpyright and ty for maximum coverage
- **Ignore Policy**: Per-line, rule-scoped ignores only (`# pyright: ignore[rule-code]`)

## Architecture Patterns

### Concurrency
- **Structured Concurrency**: TaskGroup for concurrent webhook notifications
- **Async/Await**: asyncio for I/O-bound webhook delivery
- **CPU Offloading**: asyncio.to_thread for disk usage calculations
- **Timeout Management**: asyncio.timeout for webhook request timeouts

### Type System
- **PEP 695 Generics**: Modern `class[T]` and `def[T]` syntax
- **Type Aliases**: `type` statement for complex type aliases
- **Protocols**: Small, composable Protocol definitions for structural subtyping
- **TypeIs**: Precise type narrowing for predicates
- **TypedDict**: ReadOnly fields for immutable configuration

### Data Modeling
- **Dataclasses**: Simple DTOs with `slots=True` for memory efficiency
- **Pydantic**: Validation at API boundaries (configuration loading)
- **Immutability**: ReadOnly TypedDict fields for runtime configuration

### Error Handling
- **Exception Groups**: `except*` for handling multiple provider failures
- **Provider Isolation**: Single provider failure doesn't affect others
- **Retry Logic**: Exponential backoff for transient failures
- **Circuit Breaker**: Prevent resource waste on persistently failing providers

## Testing Strategy

- **Unit Tests**: Pure function testing with fixtures
- **Integration Tests**: Plugin loading and notification flow
- **Property-Based Tests**: Hypothesis for calculation invariants
- **Parametrized Tests**: Multiple inputs via pytest.mark.parametrize
- **Test Structure**: Mirror project structure in tests/ directory

## Configuration

- **Format**: YAML (two-tier: main app config + provider-specific configs)
- **Validation**: Pydantic models for schema validation
- **Secrets**: Direct YAML values by default; optional environment variable references using `${VARIABLE_NAME}` syntax
- **Location**: Project root or designated config/ directory

## Unraid Integration

- **Execution**: Via User Scripts plugin (Run in Background)
- **PID File**: Monitors `/var/run/mover.pid` for process detection
- **Logging**: Integration with Unraid syslog
- **Persistence**: Configuration stored in `/boot/config/plugins/mover-status/`
