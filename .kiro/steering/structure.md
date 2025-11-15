---
inclusion: always
---

# Project Structure

## Directory Layout

```
mover-status/
├── .kiro/                      # Kiro IDE configuration
│   └── steering/               # AI assistant steering rules
├── src/                        # Source code (src/ layout)
│   └── mover_status/           # Main package
│       ├── __init__.py         # Package entry point
│       ├── core/               # Core application logic
│       │   ├── monitoring.py   # Mover process lifecycle detection
│       │   ├── calculation.py  # Progress and ETC calculations
│       │   ├── orchestrator.py # Component coordination
│       │   └── config.py       # Configuration loading/validation
│       ├── plugins/            # Provider plugins
│       │   ├── discord/        # Discord provider
│       │   │   ├── __init__.py
│       │   │   ├── provider.py # NotificationProvider implementation
│       │   │   ├── client.py   # Discord API client
│       │   │   ├── formatter.py # Discord embed formatter
│       │   │   ├── config.py   # Discord config schema
│       │   │   └── constants.py
│       │   └── telegram/       # Telegram provider (same structure)
│       ├── utils/              # Shared utilities
│       │   ├── http_client.py  # Webhook delivery
│       │   ├── formatting.py   # Size/time formatting
│       │   ├── template.py     # Message templates
│       │   └── logging.py      # Structured logging
│       └── types/              # Type definitions
│           ├── protocols.py    # Protocol definitions
│           ├── aliases.py      # Type aliases
│           └── models.py       # Shared data models
├── tests/                      # Test suite (mirrors src/)
│   ├── unit/
│   │   ├── core/
│   │   ├── plugins/
│   │   └── utils/
│   ├── integration/
│   └── property/
├── config/                     # Configuration files
│   ├── mover-status.yaml       # Main application config
│   └── providers/              # Provider-specific configs
│       ├── discord.yaml
│       └── telegram.yaml
├── .old_script/                # Legacy bash implementation
│   └── moverStatus.sh
├── pyproject.toml              # Project metadata and dependencies
├── uv.lock                     # Dependency lock file
├── ARCHITECTURE.md             # Comprehensive design document
└── README.md                   # User documentation
```

## Module Organization Principles

### Core Modules (`src/mover_status/core/`)

**Separation of Concerns:**
- `monitoring.py`: Mover process lifecycle only (PID file watching, state management)
- `calculation.py`: Pure functions for progress/ETC calculations (no side effects)
- `orchestrator.py`: Coordinates monitoring, calculation, and notification dispatch
- `config.py`: Configuration loading, validation, environment variable resolution

**Dependencies:**
- Core modules depend on utils and types
- Core modules do NOT depend on plugins
- Calculation module has zero dependencies (pure functions)

### Plugin Modules (`src/mover_status/plugins/`)

**Complete Self-Containment:**
- Each provider is a self-contained package
- No dependencies between provider plugins
- Each plugin includes: provider implementation, API client, formatter, config schema, constants

**Plugin Structure (consistent across all providers):**
```
plugins/<provider>/
├── __init__.py          # Plugin entry point and metadata
├── provider.py          # NotificationProvider Protocol implementation
├── client.py            # Provider-specific API client
├── formatter.py         # Message formatter for platform
├── config.py            # Pydantic configuration schema
└── constants.py         # Provider-specific constants
```

**Adding New Providers:**
1. Create new directory in `plugins/` following naming convention
2. Implement NotificationProvider Protocol
3. Define Pydantic config schema
4. Add provider-specific YAML template
5. No changes to core application code required

### Utility Modules (`src/mover_status/utils/`)

**Shared Infrastructure:**
- `http_client.py`: Protocol-based HTTP client for webhook delivery
- `formatting.py`: Pure functions for human-readable formatting
- `template.py`: Message template parsing and placeholder replacement
- `logging.py`: Structured logging configuration

**Design Principles:**
- Pure functions where possible (formatting, template)
- Protocol-based interfaces (http_client)
- No provider-specific code in utilities

### Type Modules (`src/mover_status/types/`)

**Type Definitions:**
- `protocols.py`: All Protocol definitions (NotificationProvider, MessageFormatter, HTTPClient)
- `aliases.py`: Complex type aliases using `type` statement
- `models.py`: Shared dataclasses (notification data, progress data)

**Type Safety:**
- Small, composable Protocols (1-3 methods each)
- PEP 695 generic syntax for type parameters
- TypeIs for type predicates
- ReadOnly TypedDict for immutable configs

## Test Structure (`tests/`)

**Mirror Project Structure:**
- Test directory structure mirrors `src/` layout
- `tests/unit/core/` tests `src/mover_status/core/`
- `tests/unit/plugins/` tests `src/mover_status/plugins/`

**Test Categories:**
- `unit/`: Fast, isolated tests with mocks
- `integration/`: Multi-component tests (plugin loading, notification flow)
- `property/`: Hypothesis-based property tests for calculations

## Configuration Structure

**Two-Tier System:**
1. **Main Config** (`config/mover-status.yaml`): Application settings, provider enablement, monitoring config
2. **Provider Configs** (`config/providers/<provider>.yaml`): Provider-specific settings (webhooks, tokens, formatting)

**Configuration Approach:**
- Direct YAML values are the default configuration method
- Optional environment variable references using `${VARIABLE_NAME}` syntax
- Validation errors halt startup with clear diagnostics

## Import Conventions

**Absolute Imports:**
```python
from mover_status.core.monitoring import MonitoringEngine
from mover_status.plugins.discord.provider import DiscordProvider
from mover_status.types.protocols import NotificationProvider
from mover_status.utils.formatting import format_bytes
```

**No Relative Imports:**
- Avoid `from ..core import ...`
- Use absolute imports from package root

**Type-Only Imports:**
```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mover_status.types.protocols import NotificationProvider
```

## File Naming Conventions

- **Modules**: lowercase with underscores (`http_client.py`, `notification_provider.py`)
- **Classes**: PascalCase (`MonitoringEngine`, `DiscordProvider`)
- **Functions**: lowercase with underscores (`calculate_progress`, `format_bytes`)
- **Constants**: UPPERCASE with underscores (`MAX_RETRIES`, `DEFAULT_TIMEOUT`)
- **Type Aliases**: PascalCase (`NotificationData`, `ProviderRegistry`)
