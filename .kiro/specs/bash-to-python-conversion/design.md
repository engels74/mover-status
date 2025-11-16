# Design Document

## Overview

This design document describes the architecture for converting the legacy moverStatus.sh bash script into a modern Python 3.14+ application. The design emphasizes modularity, type safety, extensibility, and maintainability through a plugin-based architecture that enables seamless addition of notification providers without modifying core application code.

### Core Design Principles

1. **Modularity**: Complete separation between core monitoring logic, provider plugins, configuration management, and utilities
2. **Protocol-Based Abstraction**: All component interactions defined through Protocol interfaces for loose coupling
3. **Plugin Architecture**: Zero hardcoded providers with dynamic discovery and loading
4. **Type Safety**: Comprehensive type hints using Python 3.14+ features (PEP 695, TypeIs, type statement)
5. **Structured Concurrency**: TaskGroup-based async operations for clean resource management
6. **Configuration Validation**: Pydantic-based validation with fail-fast error reporting

### System Context

The application monitors the Unraid mover process which moves data from cache drives to array drives. The mover process is managed through:
- PID file at `/var/run/mover.pid` created by the PHP orchestrator
- Process variants: `/usr/local/sbin/mover.old` or `/usr/local/emhttp/plugins/ca.mover.tuning/age_mover`
- Integration with Unraid syslog for operational logging

## Architecture

### Layered Architecture

The system follows a five-layer architecture with clear separation of concerns:

**Layer 1: Application Core**
- Monitoring Engine: Mover process lifecycle detection and state management
- Progress Calculator: Percentage and ETC calculations using pure functions
- Disk Usage Tracker: Baseline and periodic sampling with exclusion path support
- Orchestrator: Coordinates all components using structured concurrency

**Layer 2: Plugin System**
- Plugin Discovery: Convention-based automatic provider detection
- Plugin Loader: Dynamic initialization with lazy loading
- Plugin Registry: Active provider instance management
- Notification Dispatcher: Concurrent message routing to enabled providers

**Layer 3: Provider Plugins**
- Self-contained packages (Discord, Telegram, future providers)
- Each encapsulates: API client, message formatter, configuration schema
- Zero cross-provider dependencies
- Isolated failure domains

**Layer 4: Configuration & Validation**
- Main application configuration (YAML + Pydantic validation)
- Provider-specific configurations (separate YAML per provider)
- Environment variable integration (optional for secrets)
- Fail-fast validation with actionable diagnostics

**Layer 5: Utilities & Infrastructure**
- HTTP Client: Protocol-based webhook delivery abstraction
- Message Templates: Placeholder-based template system
- Formatters: Human-readable size and time formatting
- Logging: Structured logging with syslog integration


### Component Interaction Flow

**Startup Sequence:**
1. Configuration Loader validates main YAML (Pydantic schema)
2. Enabled providers identified from boolean flags
3. Plugin Discovery scans plugins directory
4. Provider-specific YAMLs loaded and validated
5. Provider instances created with validated config
6. Health checks verify provider connectivity
7. Monitoring Engine enters waiting state

**Monitoring Loop:**
1. PID file watcher detects `/var/run/mover.pid` creation
2. Process existence validated in process table
3. Baseline disk usage captured
4. "Mover Started" notification dispatched concurrently to all providers
5. Periodic disk usage sampling begins
6. Progress percentage calculated: `(baseline - current) / baseline * 100`
7. Threshold evaluation triggers notifications (25%, 50%, 75%, etc.)
8. ETC calculated: `remaining_data / movement_rate`
9. Process termination detected
10. "Mover Completed" notification with final statistics
11. Return to waiting state

**Notification Dispatch Flow:**
1. Notification event created with template placeholders
2. Template engine populates placeholders with current values
3. TaskGroup created for concurrent provider dispatch
4. Each provider task:
   - Formats message for platform (Discord embeds, Telegram HTML)
   - Delivers via HTTP client with timeout protection
   - Logs success/failure
5. Exception groups handle multi-provider failures
6. Failed providers don't block successful deliveries

## Components and Interfaces

### Core Protocols

All component interactions defined through Protocol interfaces for structural subtyping:

**NotificationProvider Protocol**
```python
from typing import Protocol
from collections.abc import Mapping

class NotificationProvider(Protocol):
    async def send_notification(self, data: NotificationData) -> NotificationResult:
        """Deliver notification to provider platform"""
        ...
    
    def validate_config(self) -> bool:
        """Validate provider configuration"""
        ...
    
    async def health_check(self) -> HealthStatus:
        """Verify provider connectivity"""
        ...
```

**MessageFormatter Protocol**
```python
from collections.abc import Mapping
from datetime import datetime

class MessageFormatter(Protocol):
    def format_message(self, template: str, placeholders: Mapping[str, object]) -> str:
        """Format message with platform-specific formatting"""
        ...
    
    def format_time(self, timestamp: datetime) -> str:
        """Convert timestamp to platform-specific format"""
        ...
```

**HTTPClient Protocol**
```python
from collections.abc import Mapping

class HTTPClient(Protocol):
    async def post(
        self, 
        url: str, 
        payload: Mapping[str, object], 
        *, 
        timeout: float
    ) -> Response:
        """Send HTTP POST with timeout"""
        ...
    
    async def post_with_retry(
        self, 
        url: str, 
        payload: Mapping[str, object]
    ) -> Response:
        """Send HTTP POST with exponential backoff retry"""
        ...
```


### Monitoring Engine

**Responsibilities:**
- PID file observation at `/var/run/mover.pid`
- Process lifecycle state machine (waiting → started → monitoring → completed)
- Process existence validation via process table
- Edge case handling (mover never starts, unexpected termination)
- Syslog integration for operational events

**Design:**
- Async file watching using `asyncio` primitives
- State machine pattern for lifecycle management
- Signals to Progress Calculator when monitoring begins
- Triggers Notification Dispatcher at lifecycle milestones
- Coordinates with Disk Usage Tracker for sampling intervals

**Key Methods:**
- `watch_pid_file()`: Async generator yielding PID file events
- `validate_process(*, pid: int)`: Verify process exists in process table
- `get_current_state()`: Return current lifecycle state
- `handle_process_start()`: Initialize monitoring session
- `handle_process_end()`: Cleanup and return to waiting

### Progress Calculator

**Responsibilities:**
- Progress percentage calculation from baseline and current usage
- Data movement rate calculation across sampling intervals
- Estimated time of completion (ETC) projection
- Remaining data calculation
- Threshold evaluation for notification triggering

**Design:**
- Pure functions for all calculations (enables comprehensive testing)
- Immutable dataclasses with `slots=True` for calculation inputs
- Moving average for rate calculation to smooth variations
- Graceful edge case handling (zero movement, negative deltas)
- Provider-agnostic time representations

**Key Functions:**
```python
from datetime import datetime, timedelta

def calculate_progress(baseline: int, current: int) -> float:
    """Calculate progress percentage"""
    if baseline == 0:
        return 100.0
    return ((baseline - current) / baseline) * 100.0

def calculate_etc(remaining: int, rate: float) -> datetime | None:
    """Calculate estimated time of completion"""
    if rate <= 0:
        return None
    seconds_remaining = remaining / rate
    return datetime.now() + timedelta(seconds=seconds_remaining)

def calculate_rate(samples: list[DiskSample]) -> float:
    """Calculate moving average data movement rate"""
    if len(samples) < 2:
        return 0.0
    # Moving average implementation
    ...
```

### Disk Usage Tracker

**Responsibilities:**
- Baseline disk usage capture at mover start
- Periodic current usage sampling during execution
- Exclusion path filtering (configurable directories to skip)
- Delta calculation for progress determination
- Caching to prevent excessive disk I/O

**Design:**
- CPU-bound calculations offloaded to thread pool via `asyncio.to_thread`
- Configurable sampling intervals (balance accuracy vs. system load)
- Memory-efficient directory traversal
- Error handling for inaccessible paths
- Human-readable size formatting utility

**Key Methods:**
- `capture_baseline(paths: list[Path], *, exclusions: list[Path])`: Initial snapshot
- `sample_current_usage()`: Periodic sampling
- `calculate_delta()`: Difference between baseline and current
- `format_size(bytes: int)`: Convert to human-readable (GB/TB/MB/KB)


### Plugin System

**Plugin Discovery:**
- Convention-based: plugins located in `src/plugins/` directory
- Naming convention: each provider in its own subdirectory
- Metadata registration: each plugin exposes name, version, required config fields
- Automatic scanning at startup
- Conditional loading: only enabled providers loaded

**Plugin Structure:**
```
src/plugins/
├── discord/
│   ├── __init__.py          # Plugin metadata and entry point
│   ├── provider.py          # NotificationProvider implementation
│   ├── client.py            # Discord API client
│   ├── formatter.py         # Discord embed formatter
│   ├── config.py            # Pydantic configuration schema
│   └── constants.py         # Discord-specific constants
├── telegram/
│   ├── __init__.py
│   ├── provider.py
│   ├── client.py
│   ├── formatter.py
│   ├── config.py
│   └── constants.py
└── [future_provider]/       # Same structure for new providers
```

**Plugin Isolation Guarantees:**
- Zero imports between provider plugins
- No shared provider-specific code
- Each provider independently testable
- Provider addition/removal doesn't affect others
- Common infrastructure (HTTP client, logging) accessed via Protocol interfaces

**Plugin Lifecycle:**
1. **Discovery**: Scan plugins directory, identify available providers
2. **Filtering**: Load only providers enabled in main config
3. **Validation**: Validate provider-specific YAML against provider's Pydantic schema
4. **Initialization**: Create provider instances with validated config
5. **Health Check**: Verify connectivity before registration
6. **Registration**: Add healthy providers to plugin registry
7. **Operation**: Dispatch notifications concurrently to all registered providers
8. **Shutdown**: Graceful cleanup with timeout for pending notifications

### Configuration System

**Two-Tier Configuration:**

**Main Application YAML** (`config/mover-status.yaml`):
```yaml
# Monitoring settings
monitoring:
  pid_file: /var/run/mover.pid
  sampling_interval: 60  # seconds
  process_timeout: 300   # seconds
  exclusion_paths:
    - /mnt/cache/appdata
    - /mnt/cache/system

# Notification settings
notifications:
  thresholds: [0, 25, 50, 75, 100]  # percentage
  completion_enabled: true
  retry_attempts: 5

# Provider enablement
providers:
  discord_enabled: true
  telegram_enabled: false

# Application settings
application:
  log_level: INFO
  dry_run: false
  version_check: true
  syslog_enabled: true
```

**Provider-Specific YAML** (`config/providers/discord.yaml`):
```yaml
# Discord webhook configuration
webhook_url: https://discord.com/api/webhooks/...
# Or use environment variable:
# webhook_url: ${MOVER_STATUS_DISCORD_WEBHOOK_URL}

username: Mover Status Bot
embed_color: 0x5865F2
```

**Configuration Validation:**
- Pydantic BaseModel for main config schema
- Provider-specific Pydantic models in each plugin
- Field validators for complex validation (URL format, path existence, percentage ranges)
- ReadOnly TypedDict fields for immutable runtime config
- Fail-fast: invalid configuration prevents startup
- Actionable error messages with field-level diagnostics

**Environment Variable Support:**
- Optional: direct YAML values are default
- Syntax: `${VARIABLE_NAME}` in YAML
- Resolution at startup
- Validation: missing required variables fail startup
- No secret logging or exposure in errors


### Notification Dispatcher

**Responsibilities:**
- Concurrent notification delivery to all enabled providers
- Exception group handling for multi-provider failures
- Provider failure isolation (one failure doesn't block others)
- Timeout enforcement per provider
- Success/failure logging with correlation IDs

**Design:**
- TaskGroup for structured concurrency
- Each provider gets dedicated task
- Timeout protection via `asyncio.timeout`
- Exception groups with `except*` for multi-provider error handling
- Context variables for correlation ID tracking

**Notification Flow:**
```python
async def dispatch_notification(self, event: NotificationEvent):
    """Dispatch notification to all enabled providers concurrently"""
    notification_data = self._prepare_notification_data(event)
    
    async with asyncio.TaskGroup() as tg:
        for provider in self.registry.get_healthy_providers():
            tg.create_task(
                self._send_to_provider(provider, notification_data)
            )
    
    # TaskGroup ensures all tasks complete or cancel together
    # Exception groups handled separately

async def _send_to_provider(self, provider: NotificationProvider, data: NotificationData):
    """Send notification to single provider with timeout"""
    try:
        async with asyncio.timeout(10.0):  # 10 second timeout
            result = await provider.send_notification(data)
            self.logger.info(f"Notification sent to {provider.name}", extra={"result": result})
    except TimeoutError:
        self.logger.warning(f"Timeout sending to {provider.name}")
        self.registry.mark_for_retry(provider)
    except Exception as e:
        self.logger.error(f"Failed to send to {provider.name}: {e}")
        self.registry.mark_unhealthy(provider)
```

### Message Template System

**Responsibilities:**
- Template loading from configuration
- Placeholder identification and validation
- Placeholder replacement with runtime values
- Provider-specific formatting delegation

**Supported Placeholders:**
- `{percent}`: Progress percentage (e.g., "75.5")
- `{remaining_data}`: Human-readable remaining data (e.g., "125.3 GB")
- `{etc}`: Estimated time of completion (provider-specific format)
- `{moved_data}`: Amount moved so far (e.g., "350.7 GB")
- `{total_data}`: Total data to move (e.g., "476.0 GB")
- `{rate}`: Current movement rate (e.g., "45.2 MB/s")

**Template Examples:**
```yaml
templates:
  started: "Mover process started. Total data to move: {total_data}"
  progress: "Progress: {percent}% complete. Remaining: {remaining_data}. ETC: {etc}"
  completed: "Mover completed! Moved {moved_data} in total."
```

**Provider-Specific Formatting:**
- Discord: ETC as Unix timestamp with relative formatting (`<t:1234567890:R>`)
- Telegram: ETC as human-readable datetime string
- Each provider's formatter implements platform-specific conversions

## Data Models

### Core Data Structures

All data models use dataclasses with `slots=True` for memory efficiency:

```python
from dataclasses import dataclass
from datetime import datetime

@dataclass(slots=True, frozen=True)
class DiskSample:
    """Immutable disk usage sample"""
    timestamp: datetime
    bytes_used: int
    path: str

@dataclass(slots=True, frozen=True)
class ProgressData:
    """Immutable progress calculation result"""
    percent: float
    remaining_bytes: int
    moved_bytes: int
    total_bytes: int
    rate_bytes_per_second: float
    etc: datetime | None

@dataclass(slots=True)
class NotificationData:
    """Generic notification data for all providers"""
    event_type: str  # "started", "progress", "completed"
    percent: float
    remaining_data: str  # Human-readable
    moved_data: str
    total_data: str
    rate: str
    etc_timestamp: datetime | None
    correlation_id: str

@dataclass(slots=True)
class NotificationResult:
    """Result of notification delivery attempt"""
    success: bool
    provider_name: str
    error_message: str | None
    delivery_time_ms: float
```


## Error Handling

### Provider Failure Isolation

**Design Principle:** Single provider failure MUST NOT prevent other providers from functioning

**Isolation Mechanisms:**
- Each provider task executes in isolated TaskGroup task
- Provider exceptions caught within provider's execution context
- Failed provider marked unhealthy in registry; others remain active
- Health check mechanism periodically retries unhealthy providers

**Failure Scenarios:**

**Network Timeout:**
- Provider's HTTP request times out
- TimeoutError caught and logged
- Provider marked for retry with exponential backoff
- Other providers unaffected

**Invalid Configuration:**
- Provider's webhook URL returns 404 Not Found
- Error logged with provider context
- Provider marked permanently unhealthy until config corrected
- Other providers continue functioning

**API Rate Limiting:**
- Provider's API returns 429 Too Many Requests
- Provider backs off according to Retry-After header
- Notification queued for retry
- Other providers deliver immediately

### Retry Strategy

**Exponential Backoff:**
- Initial retry after 1 second
- Subsequent retries double interval: 2s, 4s, 8s, 16s
- Maximum retry interval: 60 seconds
- Maximum retry attempts: 5 (configurable)
- Random jitter (±20%) to prevent thundering herd

**Retry Conditions:**
- Network timeouts
- HTTP 5xx server errors
- Connection refused/reset
- DNS resolution failures

**Non-Retry Conditions:**
- HTTP 4xx client errors (except 429)
- Authentication failures (401, 403)
- Validation errors from provider API
- Configuration errors

**Circuit Breaker Pattern:**
- After N consecutive failures, provider circuit "opens"
- Open circuit prevents retry attempts for cooldown period
- After cooldown, single "half-open" request attempted
- Success closes circuit; failure reopens for longer cooldown

### Exception Groups

Using `except*` for multi-provider error handling:

```python
try:
    async with asyncio.TaskGroup() as tg:
        for provider in providers:
            tg.create_task(send_to_provider(provider, data))
except* TimeoutError as eg:
    # Handle all provider timeout failures together
    for exc in eg.exceptions:
        logger.warning(f"Provider timeout: {exc}")
except* ValueError as eg:
    # Handle all provider validation failures together
    for exc in eg.exceptions:
        logger.error(f"Provider validation error: {exc}")
except* Exception as eg:
    # Handle all other failures
    for exc in eg.exceptions:
        logger.error(f"Provider error: {exc}")
```

## Testing Strategy

### Unit Testing

**Pure Function Testing:**
- Progress calculation functions tested with parametrized inputs
- Edge cases: zero movement, negative deltas, overflow
- Boundary conditions: exactly at threshold, just below, just above
- Fixture-based mock data for consistent test scenarios

**Protocol Mock Testing:**
- Mock NotificationProvider for testing dispatcher
- Mock HTTPClient for testing providers
- Mock configuration for fast test execution
- Verify provider isolation (single failure doesn't affect others)

### Property-Based Testing

Using Hypothesis for invariant validation:

**Progress Calculation Invariants:**
- Progress percentage always between 0 and 100
- Remaining data always non-negative
- ETC always in future (not past)
- Rate calculation never produces NaN or Infinity

**Hypothesis Strategies:**
```python
from hypothesis import given, strategies as st

@given(
    baseline=st.integers(min_value=1, max_value=10**12),
    current=st.integers(min_value=0, max_value=10**12)
)
def test_progress_bounds(baseline: int, current: int):
    """Progress percentage always between 0 and 100"""
    progress = calculate_progress(baseline, current)
    assert 0.0 <= progress <= 100.0

@given(
    samples=st.lists(
        st.builds(DiskSample, 
                  timestamp=st.datetimes(),
                  bytes_used=st.integers(min_value=0),
                  path=st.just("/mnt/cache")),
        min_size=2
    )
)
def test_rate_non_negative(samples: list[DiskSample]):
    """Movement rate never negative"""
    rate = calculate_rate(samples)
    assert rate >= 0.0
```

### Integration Testing

**Plugin Loading:**
- Test plugin discovery from plugins directory
- Test conditional loading (only enabled providers)
- Test provider-specific config validation
- Test health check integration

**Notification Flow:**
- End-to-end notification dispatch
- Multiple providers with mixed success/failure
- Exception group handling validation
- Correlation ID tracking across providers

### Test Structure

Following pytest best practices with fixture-based testing:

```
tests/
├── unit/
│   ├── core/
│   │   ├── test_monitoring.py       # Monitoring engine tests
│   │   ├── test_calculation.py      # Pure function tests
│   │   ├── test_orchestrator.py     # Orchestration logic tests
│   │   └── test_config.py           # Configuration loading tests
│   ├── plugins/
│   │   ├── test_discord.py          # Discord provider tests
│   │   ├── test_telegram.py         # Telegram provider tests
│   │   └── test_plugin_system.py    # Plugin discovery/loading tests
│   └── utils/
│       ├── test_formatting.py       # Size/time formatting tests
│       ├── test_template.py         # Template system tests
│       └── test_http_client.py      # HTTP client tests
├── integration/
│   ├── test_plugin_loading.py       # End-to-end plugin loading
│   ├── test_notification_flow.py    # Full notification dispatch
│   └── test_configuration.py        # Config validation integration
└── property/
    ├── test_calculation_properties.py  # Hypothesis invariant tests
    └── test_formatting_properties.py   # Formatting invariant tests
```

**Fixture Examples:**
```python
import pytest
from unittest.mock import AsyncMock

@pytest.fixture
def mock_http_client():
    """Mock HTTP client for testing providers"""
    client = AsyncMock()
    client.post.return_value = Response(status=200, body={})
    return client

@pytest.fixture
def notification_data():
    """Sample notification data for testing"""
    return NotificationData(
        event_type="progress",
        percent=75.5,
        remaining_data="125.3 GB",
        moved_data="350.7 GB",
        total_data="476.0 GB",
        rate="45.2 MB/s",
        etc_timestamp=datetime.now() + timedelta(hours=1),
        correlation_id="test-123"
    )

@pytest.fixture
def plugin_registry(mock_http_client):
    """Plugin registry with mock providers"""
    registry = PluginRegistry()
    discord = DiscordProvider(config=discord_config, http_client=mock_http_client)
    telegram = TelegramProvider(config=telegram_config, http_client=mock_http_client)
    registry.register(discord)
    registry.register(telegram)
    return registry
```

### Type Checking Integration

**basedpyright Configuration:**
- basedpyright in "recommended" mode with `failOnWarnings = true`
- Comprehensive type checking for all code
- Must pass for merge approval

**Configuration:**
```toml
# pyproject.toml
[tool.basedpyright]
typeCheckingMode = "recommended"
failOnWarnings = true
pythonVersion = "3.14"
pythonPlatform = "All"
reportUnreachable = "warning"
reportAny = "warning"
reportIgnoreCommentWithoutRule = "warning"
enableTypeIgnoreComments = false
```

## Concurrency & Performance

### Structured Concurrency

**TaskGroup for Notification Dispatch:**
```python
async def dispatch_notifications(providers: list[NotificationProvider], data: NotificationData):
    """Dispatch to all providers concurrently with structured concurrency"""
    async with asyncio.TaskGroup() as tg:
        for provider in providers:
            tg.create_task(provider.send_notification(data))
    # All tasks complete or cancel together
    # No orphaned tasks
    # Automatic cleanup on exception
```

**Benefits:**
- Automatic cancellation propagation when any task fails
- No orphaned tasks: all tasks complete or cancel together
- Clean error handling via exception groups
- True parallelism in free-threaded Python builds
- Explicit task lifetime management

### Async I/O Optimization

**Concurrent Webhook Delivery:**
- Discord and Telegram webhook POSTs execute concurrently
- No blocking: while waiting for Discord response, Telegram request in flight
- Significant latency reduction: total time = max(provider latencies), not sum
- Timeout per provider prevents slow provider blocking others

**CPU-Bound Work Offloading:**
```python
async def sample_disk_usage(paths: list[Path]) -> int:
    """Offload CPU-bound disk calculation to thread pool"""
    return await asyncio.to_thread(_calculate_disk_usage_sync, paths)

def _calculate_disk_usage_sync(paths: list[Path]) -> int:
    """Synchronous disk usage calculation"""
    total = 0
    for path in paths:
        for entry in path.rglob("*"):
            if entry.is_file():
                total += entry.stat().st_size
    return total
```

**Benefits:**
- Monitoring loop remains responsive during calculations
- In free-threaded Python builds, true parallelism for CPU work
- Context variables preserved across thread boundary
- Maintains async/await code structure

### Timeout Management

**Per-Provider Timeouts:**
```python
async def send_with_timeout(provider: NotificationProvider, data: NotificationData):
    """Send notification with timeout protection"""
    try:
        async with asyncio.timeout(10.0):  # 10 second timeout
            return await provider.send_notification(data)
    except TimeoutError:
        logger.warning(f"Timeout sending to {provider.name}")
        raise
```

**Nested Timeouts:**
- Overall notification timeout (e.g., 30 seconds for all providers)
- Per-provider timeout (e.g., 10 seconds per provider)
- Prevents hung requests from blocking notification dispatch


## Security

### Secret Management

**Default: Direct YAML Configuration**
```yaml
# config/providers/discord.yaml
webhook_url: https://discord.com/api/webhooks/123456/abcdef
```

**Optional: Environment Variable References**
```yaml
# config/providers/discord.yaml
webhook_url: ${MOVER_STATUS_DISCORD_WEBHOOK_URL}
```

**Security Practices:**
- No secret logging or exposure in error messages
- Secure handling in memory (no persistence to disk)
- Validation at startup for missing environment variables
- Integration with Unraid User Scripts environment variable support

### Input Validation

**Configuration Validation:**
- All configuration fields validated against Pydantic schemas
- Type validation (strings, integers, booleans)
- Format validation (URLs, paths, percentages)
- Range validation (thresholds between 0-100, intervals positive)
- Reject invalid configurations before application starts

**Webhook URL Validation:**
- Regex pattern matching for provider-specific URL formats
- Scheme validation (HTTPS only)
- Domain validation (discord.com, api.telegram.org, etc.)
- Reject malformed URLs at configuration validation time

**Message Template Validation:**
- Placeholder validation: only known placeholders allowed
- No arbitrary code execution in templates
- Safe string substitution only

### Dependency Security

**Multi-Tool Scanning:**
- pip-audit: Scans against PyPI advisory database
- bandit: Static code analysis for security issues
- safety: Additional vulnerability database

**Hash Verification:**
```bash
# Generate requirements with hashes
uv export --frozen --generate-hashes > requirements.txt

# Install with hash verification
pip install --require-hashes -r requirements.txt
```

**Benefits:**
- Prevents dependency confusion attacks
- Prevents typosquatting attacks
- Supply chain security

## Deployment

### Package Structure

```
mover-status/
├── src/
│   ├── mover_status/
│   │   ├── __init__.py
│   │   ├── __main__.py          # Entry point
│   │   ├── core/
│   │   │   ├── monitoring.py
│   │   │   ├── calculation.py
│   │   │   ├── orchestrator.py
│   │   │   └── config.py
│   │   ├── plugins/
│   │   │   ├── discord/
│   │   │   └── telegram/
│   │   ├── utils/
│   │   │   ├── http_client.py
│   │   │   ├── formatting.py
│   │   │   ├── template.py
│   │   │   └── logging.py
│   │   └── types/
│   │       ├── protocols.py
│   │       ├── aliases.py
│   │       └── models.py
├── tests/
├── config/
│   ├── mover-status.yaml.template
│   └── providers/
│       ├── discord.yaml.template
│       └── telegram.yaml.template
├── pyproject.toml
├── uv.lock
└── README.md
```

### Unraid Integration

**Installation:**
- User Scripts plugin provides scheduled and manual execution
- Application installed in persistent location (e.g., `/boot/config/plugins/mover-status/`)
- Python 3.14 installed via Nerd Tools or standalone

**Execution:**
- Background script execution for continuous monitoring
- User Scripts manages process lifecycle (start, stop, restart)
- Application logs to syslog for integration with Unraid logging

**Configuration:**
- Configuration in persistent location (survives reboots)
- Environment variables via User Scripts UI
- Automatic startup with array start (configurable)

## Logging and Observability

### Structured Logging

**Log Levels:**
- DEBUG: Detailed diagnostic information (disk samples, calculation details)
- INFO: Operational events (mover started, notifications sent, thresholds crossed)
- WARNING: Unexpected but handled situations (provider failures, retries)
- ERROR: Serious problems requiring attention (configuration errors, all providers failed)

**Contextual Logging:**
```python
logger.info(
    "Notification sent successfully",
    extra={
        "provider": "discord",
        "event_type": "progress",
        "percent": 75.5,
        "correlation_id": "abc-123",
        "delivery_time_ms": 234.5
    }
)
```

**Syslog Integration:**
- Python logging configured to send to Unraid syslog
- Standard syslog severity levels
- Integration with Unraid's log rotation

### Correlation IDs

**Purpose:** Track notifications across multiple providers

**Implementation:**
```python
from contextvars import ContextVar

correlation_id_var: ContextVar[str] = ContextVar("correlation_id")

async def dispatch_notification(event: NotificationEvent):
    """Dispatch with correlation ID"""
    correlation_id = str(uuid.uuid4())
    correlation_id_var.set(correlation_id)
    
    # All provider tasks inherit correlation ID
    async with asyncio.TaskGroup() as tg:
        for provider in providers:
            tg.create_task(send_to_provider(provider, event))
```

**Benefits:**
- Trace single notification across all providers
- Correlate success/failure across providers
- Debug multi-provider issues

## Migration Path

### Feature Parity

**Core Functionality:**
- ✓ Mover process detection via PID file
- ✓ Disk usage monitoring with exclusion paths
- ✓ Progress percentage calculation
- ✓ ETC estimation based on movement rate
- ✓ Threshold-based notifications (configurable percentages)
- ✓ Completion notification
- ✓ Discord webhook integration with embeds
- ✓ Telegram bot integration with HTML formatting
- ✓ Human-readable size formatting
- ✓ Dry-run mode for testing
- ✓ Debug logging

**Behavioral Parity:**
- Same notification timing (at same progress percentages)
- Same message content and formatting
- Same ETC calculation logic
- Continuous monitoring loop (wait → monitor → wait cycle)

### Incremental Migration

**Phase 1: Parallel Deployment**
- Run Python application alongside bash script
- Both monitoring same mover process
- Compare notification outputs for consistency
- Identify any behavioral differences

**Phase 2: Provider Migration**
- Migrate one provider at a time (e.g., Discord first, then Telegram)
- Bash script handles un-migrated providers
- Python application handles migrated providers
- Gradual confidence building

**Phase 3: Full Migration**
- Disable bash script
- Python application handles all providers
- Monitor for issues during initial full production use
- Rollback plan: re-enable bash script if critical issues

**Phase 4: Bash Script Retirement**
- Archive bash script for reference
- Document lessons learned
- Remove bash script dependencies

## Development Tooling

### Package Management: uv

```bash
# Initialize project
uv init mover-status --lib

# Add dependencies
uv add pydantic pyyaml aiohttp

# Add dev dependencies
uv add --dev pytest hypothesis pytest-cov ruff basedpyright

# Run application
uv run python -m mover_status

# Run tests
uv run pytest
```

### Linting & Formatting: ruff

```bash
# Check and auto-fix
uv run ruff check . --fix

# Format code
uv run ruff format .
```

### Type Checking: basedpyright & ty

```bash
# Comprehensive type checking
uv run basedpyright

# Fast type checking (development)
uv run ty check --watch
```

### Testing: pytest, Hypothesis

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=mover_status --cov-report=html

# Run property-based tests
uv run pytest tests/property/

# Run specific test file
uv run pytest tests/unit/core/test_calculation.py
```

### Type Checking: basedpyright

```bash
# Comprehensive type checking
uv run basedpyright

# Check specific files
uv run basedpyright src/mover_status/core/

# Watch mode (if using basedpyright-langserver)
basedpyright --watch
```

### Multi-Environment Testing: Nox

```bash
# Run all sessions
uv run nox

# Run specific session
uv run nox -s tests
uv run nox -s lint
uv run nox -s typecheck
```

## Python 3.14+ Specific Features

### Modern Type System

**PEP 695 Generic Syntax:**
```python
# Generic provider registry
class ProviderRegistry[T: NotificationProvider]:
    def register(self, provider: T) -> None: ...
    def get_all(self) -> list[T]: ...

# Generic configuration loader
def load_config[T: BaseModel](config_path: Path, model: type[T]) -> T:
    data = yaml.safe_load(config_path.read_text())
    return model.model_validate(data)
```

**Type Aliases with `type` Statement:**
```python
# Clear type alias declarations
type NotificationData = dict[str, str | int | float]
type ProviderConfig = DiscordConfig | TelegramConfig
type ProviderRegistry[T] = dict[str, T]
```

**TypeIs for Type Narrowing:**
```python
from typing import TypeIs

def is_discord_config(config: ProviderConfig) -> TypeIs[DiscordConfig]:
    """Type predicate for Discord configuration"""
    return isinstance(config, DiscordConfig)

# Usage: type checker narrows in both branches
if is_discord_config(config):
    # config is DiscordConfig here
    webhook = config.webhook_url
else:
    # config is TelegramConfig here
    token = config.bot_token
```

**Built-in Generic Collections:**
```python
from collections.abc import Mapping, Iterable, Sequence

# Use built-in generics, not typing module
def process_notifications(
    providers: list[NotificationProvider],
    data: Mapping[str, object]
) -> Sequence[NotificationResult]:
    ...
```

### Python Version Requirements

**Minimum Version:**
```toml
[project]
name = "mover-status"
requires-python = ">=3.14"

classifiers = [
    "Programming Language :: Python :: 3.14",
    "Programming Language :: Python :: 3 :: Only",
]
```

**Rationale:**
- PEP 695 generic syntax (class[T], def[T])
- TypeIs for precise type narrowing
- type statement for type aliases
- Tail-call interpreter optimizations (3-5% baseline improvement)
- Improved error messages
- Free-threading support (optional, for future)

### Free-Threading Considerations

**Detection and Adaptation:**
```python
import sys

# Detect free-threading build
if hasattr(sys, '_is_gil_enabled') and not sys._is_gil_enabled():
    # Free-threaded build: built-in types thread-safe
    # TaskGroup provides true parallelism
    pass
```

**When to Leverage:**
- CPU-bound disk usage calculations across multiple paths
- Parallel processing of notification formatting
- Concurrent provider health checks

**When NOT to Rely On:**
- Single-threaded Unraid environments (most common)
- Pure I/O-bound operations (asyncio sufficient)
- Until Phase II maturity (October 2025)

## Summary

This design provides a comprehensive blueprint for converting the bash script to a modern Python 3.14+ application with:

- **Modularity**: Clear separation of concerns with Protocol-based interfaces
- **Extensibility**: Plugin architecture enabling zero-modification provider addition
- **Type Safety**: Comprehensive type hints with multi-checker validation
- **Reliability**: Provider failure isolation, retry logic, structured concurrency
- **Security**: Optional environment variable support, input validation, dependency scanning
- **Testability**: Pure functions, Protocol mocks, property-based testing
- **Maintainability**: Modern tooling (uv, ruff, basedpyright, ty), structured logging

The two-tier configuration system (main app + provider-specific YAMLs) provides clear separation while the plugin architecture ensures future providers can be added without touching core code. The design maintains complete feature parity with the bash script while establishing a foundation for long-term maintainability and extensibility.
