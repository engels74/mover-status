# Mover Status - Architectural Design Document

## 1. Introduction & Project Context

### 1.1 Purpose of Conversion

This document outlines the comprehensive architectural design for converting the legacy bash script (`.old_script/moverStatus.sh`) into a modern, modular Python 3.14+ application. The conversion serves multiple strategic objectives:

- **Maintainability**: Transform a monolithic bash script with hardcoded provider logic into a well-structured, type-safe Python application following industry best practices
- **Extensibility**: Enable seamless addition of new notification providers without modifying core application logic
- **Type Safety**: Leverage Python 3.14+ type system to catch errors at development time rather than runtime
- **Performance**: Utilize modern concurrency primitives for efficient async I/O operations
- **Testability**: Enable comprehensive unit, integration, and property-based testing
- **Security**: Implement defense-in-depth security practices for handling secrets and external API communications

### 1.2 Current State Analysis

The existing bash implementation monitors the Unraid Mover process and sends progress notifications through two hardcoded providers (Discord and Telegram). While functional, it exhibits several architectural limitations:

- **Tight Coupling**: Provider-specific logic is intermingled with core monitoring functionality
- **Limited Type Safety**: Bash's weak typing leads to runtime errors that could be caught at development time
- **Testing Challenges**: Minimal testability without extensive mocking infrastructure
- **Configuration Complexity**: Single-file configuration with bash variables lacks validation
- **Provider Addition Friction**: Adding new providers requires modifying core script logic with if/else blocks

### 1.3 Unraid Mover Process Architecture

Understanding the Unraid mover invocation chain is critical for proper integration:

**Multi-Layer Invocation Chain:**
- **Layer 1 (Entry Point)**: `/usr/local/sbin/mover` - Bash wrapper that captures parent process information
- **Layer 2 (Orchestrator)**: `/usr/local/emhttp/plugins/ca.mover.tuning/mover.php` - PHP script that manages execution logic
- **Layer 3 (Execution)**: Actual mover binary (either `/usr/local/sbin/mover.old` or `/usr/local/emhttp/plugins/ca.mover.tuning/age_mover`)

**Critical Integration Points:**

- **PID File Management**: The PHP orchestrator creates and manages `/var/run/mover.pid` to prevent concurrent executions
- **Process Variant Handling**: The actual mover binary varies based on Mover Tuning Plugin configuration (standard vs. filtered)
- **Conditional Execution**: Mover may not start due to:
  - Existing mover process already running
  - Parity check/rebuild in progress (when configured to wait)
  - Forced move disabled during parity operations
  - Mover schedule disabled in configuration
- **Invocation Methods**: Three distinct invocation paths (cron scheduled, manual bash CLI, Move button) that may affect behavior
- **Process Priority**: Mover runs with configurable nice and ionice levels
- **Logging Integration**: System logging via syslog for operational transparency

**Architectural Implications:**

The Python application must accommodate this multi-layer architecture by:
- Monitoring the PID file rather than relying solely on process name detection
- Handling scenarios where the mover never starts despite being invoked
- Understanding that the monitored process name may vary based on Mover Tuning Plugin settings
- Integrating with Unraid's syslog for consistent operational logging
- Respecting the existing plugin ecosystem without creating conflicts

### 1.4 Modernization Goals

The Python 3.14+ conversion aims to establish:

- **Plugin Architecture**: Zero hardcoded providers with dynamic discovery and loading
- **Strict Type Safety**: Comprehensive type hints using modern PEP 695 syntax with multi-checker validation
- **Structured Concurrency**: TaskGroup-based async operations for clean resource management
- **Configuration Validation**: Two-tier YAML system with Pydantic-based validation
- **Comprehensive Testing**: Fixture-based unit tests, property-based testing for calculations, and integration tests
- **Security Hardening**: Environment-based secret management, input validation at API boundaries, dependency scanning
- **Developer Experience**: Modern toolchain (uv, ruff, basedpyright, ty) for 10-100x productivity improvements

---

## 2. Design Philosophy & Guiding Principles

### 2.1 Modularity as Foundation

Modularity serves as the architectural cornerstone, manifesting at multiple levels:

- **Package-Level Modularity**: Clear separation between core monitoring logic, provider plugins, configuration management, and utility functions
- **Component-Level Modularity**: Each component handles a single, well-defined responsibility
- **Provider-Level Modularity**: Complete isolation of provider-specific code, APIs, and message formatting within dedicated plugin packages
- **Configuration-Level Modularity**: Separation of application-wide settings from provider-specific configurations

### 2.2 DRY (Don't Repeat Yourself) Principle

- **Template Abstraction**: Single source of truth for message templates with provider-specific formatters
- **Common Protocol Interfaces**: Shared interfaces for provider plugins, HTTP clients, and message formatters
- **Utility Function Reuse**: Centralized implementations for disk usage calculations, time formatting, and data conversion
- **Configuration Inheritance**: Provider configs inherit validation patterns from base schemas

### 2.3 SOLID Principles Application

**Single Responsibility Principle:**
- Monitoring engine: Process detection and lifecycle management only
- Calculation engine: Progress and ETC calculations only
- Plugin orchestrator: Plugin discovery, loading, and notification dispatch only
- Each provider plugin: Single notification platform integration only

**Open/Closed Principle:**
- Core application closed for modification but open for extension via plugin interface
- New providers added without touching existing core code
- Plugin interface defines contract; implementations vary

**Liskov Substitution Principle:**
- Any provider plugin implementing the NotificationProvider protocol can be substituted seamlessly
- HTTP client implementations interchangeable without affecting dependent code

**Interface Segregation Principle:**
- Small, focused Protocol definitions (following guideline at `.claude/python-313-pro.md:44-56`)
- Providers implement only the methods they need
- No fat interfaces forcing unnecessary method implementations

**Dependency Inversion Principle:**
- Core application depends on Protocol abstractions, not concrete provider implementations
- Plugin discovery layer mediates between abstractions and implementations
- Configuration validation depends on abstract schema interfaces

### 2.4 Type Safety Philosophy

Following modern Python 3.14+ type system capabilities (`.claude/python-313-pro.md:16-87`):

- **PEP 695 Generic Syntax**: Modern `class[T]` and `def[T]` syntax for clean type parameter scoping (`.claude/python-313-pro.md:18-26`)
- **Type Alias Clarity**: Use `type` statement for explicit type alias declarations (`.claude/python-313-pro.md:28-33`)
- **TypeIs Narrowing**: Precise type narrowing with `TypeIs[T]` for better type checker understanding (`.claude/python-313-pro.md:35-42`)
- **Protocol-Based Contracts**: Structural subtyping via small, composable Protocols (`.claude/python-313-pro.md:44-56`)
- **Multi-Checker Validation**: Both basedpyright and ty in CI for comprehensive error detection (`.claude/python-313-pro.md:430-439`)

---

## 3. System Architecture Overview

### 3.1 High-Level Architecture

The system follows a layered architecture with clear separation of concerns:

**Layer 1: Application Core**
- Monitoring engine for mover process lifecycle management
- Progress calculation engine for percentage and ETC estimation
- Disk usage tracker with exclusion path support
- Application orchestrator coordinating all components

**Layer 2: Plugin System**
- Plugin discovery mechanism for automatic provider detection
- Plugin loader for dynamic provider initialization
- Plugin registry maintaining active provider instances
- Notification dispatcher routing messages to enabled providers

**Layer 3: Provider Plugins**
- Self-contained provider packages (Discord, Telegram, future providers)
- Each plugin encapsulates its own API client, message formatter, and configuration schema
- No cross-provider dependencies or shared code in plugins

**Layer 4: Configuration & Validation**
- Main application configuration loader and validator
- Provider-specific configuration managers
- Environment variable integration for secret management
- YAML schema validation using Pydantic models

**Layer 5: Utilities & Infrastructure**
- HTTP client abstraction for webhook delivery
- Message template engine with placeholder replacement
- Time formatting converters for provider-specific requirements
- Human-readable data size formatters
- Logging infrastructure with structured output

### 3.2 Component Interaction Patterns

**Synchronous Interactions:**
- Configuration loading and validation at startup
- Plugin discovery and registration during initialization
- Message template loading and compilation

**Asynchronous Interactions:**
- Mover process monitoring loop using async/await
- Concurrent webhook notifications via TaskGroup (`.claude/python-313-pro.md:91-98`)
- Disk usage calculations offloaded to thread pool via asyncio.to_thread (`.claude/python-313-pro.md:125-131`)
- Timeout-protected external API calls using asyncio.timeout (`.claude/python-313-pro.md:147-155`)

**Event-Driven Patterns:**
- Mover lifecycle events: waiting → started → progressing → completed → waiting
- Progress threshold events triggering notification dispatch
- Error events isolated per provider (one provider failure doesn't cascade)

### 3.3 Data Flow Architecture

**Configuration Flow:**
1. Main YAML loaded and validated against Pydantic schema
2. Enabled providers identified from main config
3. Provider-specific YAMLs loaded for each enabled provider
4. Validation errors halt startup with clear diagnostic messages

**Monitoring Flow:**
1. PID file watcher detects mover process start
2. Initial disk usage baseline captured
3. Periodic disk usage samples collected
4. Progress percentage calculated from baseline and current usage
5. Threshold evaluation determines if notification needed
6. ETC calculated based on movement rate

**Notification Flow:**
1. Notification request created with template placeholders
2. Template engine populates placeholders with current values
3. Plugin dispatcher iterates through enabled providers
4. Each provider receives generic notification data
5. Provider-specific formatter converts to platform-specific format
6. HTTP client delivers formatted message to webhook
7. Failures logged but don't block other providers

---

## 4. Core Application Components

### 4.1 Monitoring Engine

**Responsibilities:**
- PID file observation for mover process lifecycle detection
- Process start event detection and notification
- Process termination detection and cleanup
- Handling edge cases where mover never starts despite invocation
- Integration with Unraid syslog for operational transparency

**Key Design Decisions:**
- Primary detection mechanism: `/var/run/mover.pid` file watching
- Secondary validation: Process existence confirmation via process table
- Graceful handling of process variants (mover.old vs. age_mover)
- Async file watching using appropriate primitives for efficiency
- State machine pattern for mover lifecycle management

**Integration Points:**
- Signals progress calculator when monitoring begins
- Triggers notification dispatcher at lifecycle milestones
- Coordinates with disk usage tracker for sampling intervals

### 4.2 Disk Usage Calculation Engine

**Responsibilities:**
- Baseline disk usage capture at mover start
- Periodic current usage sampling during mover execution
- Exclusion path filtering (configurable directory exclusions)
- Delta calculation for progress determination
- Rate calculation for ETC estimation

**Key Design Decisions:**
- CPU-bound disk usage calculations offloaded to thread pool (`.claude/python-313-pro.md:125-131`)
- Caching mechanism to prevent excessive disk I/O
- Configurable sampling intervals balancing accuracy vs. system load
- Human-readable size formatting (bytes to GB/TB/MB/KB) as utility function
- Error handling for inaccessible paths or permission issues

**Performance Considerations:**
- Leveraging free-threading for parallel disk scanning if multiple paths (`.claude/python-313-pro.md:168-179`)
- Async coordination with sync disk operations via asyncio.to_thread
- Memory-efficient traversal for large directory structures

### 4.3 Progress Calculation and ETC Estimation

**Responsibilities:**
- Percentage completion calculation from baseline and current usage
- Data movement rate calculation across sampling intervals
- Estimated time of completion projection based on current rate
- Remaining data calculation
- Threshold evaluation for notification triggering

**Key Design Decisions:**
- Immutable data structures for calculation inputs (using dataclasses with slots=True, `.claude/python-313-pro.md:64`)
- Pure functions for calculations enabling comprehensive testing
- Moving average for rate calculation to smooth out variations
- Graceful handling of edge cases (zero movement, negative deltas)
- Provider-agnostic time representations converted by formatters

**Testing Strategy:**
- Property-based testing with Hypothesis for invariant validation (`.claude/python-313-pro.md:310-318`)
- Parametrized tests covering edge cases (zero, negative, overflow)
- Fixture-based mock data for consistent test scenarios

### 4.4 Configuration Loader

**Responsibilities:**
- Main application YAML discovery and loading
- Schema validation using Pydantic models (`.claude/python-313-pro.md:504-514`)
- Provider-specific YAML loading coordination
- Environment variable integration for secrets (`.claude/python-313-pro.md:516-537`)
- Configuration error reporting with actionable diagnostics

**Key Design Decisions:**
- ReadOnly TypedDict fields for immutable config sections (`.claude/python-313-pro.md:402-411`)
- Validation at API boundaries following guideline (`.claude/python-313-pro.md:58-60`)
- Fail-fast approach: invalid configuration prevents application startup
- Clear separation between required and optional configuration parameters
- Default value provision for optional settings

### 4.5 Plugin Orchestrator

**Responsibilities:**
- Plugin discovery from designated plugin directories
- Dynamic plugin loading and initialization
- Plugin registry management
- Notification dispatch coordination across enabled providers
- Plugin lifecycle management (startup, shutdown, error recovery)

**Key Design Decisions:**
- Protocol-based plugin interface for structural subtyping (`.claude/python-313-pro.md:44-56`)
- Lazy loading: plugins loaded only when enabled in configuration
- Concurrent notification delivery using TaskGroup (`.claude/python-313-pro.md:91-98`)
- Exception group handling with except* for multi-provider errors (`.claude/python-313-pro.md:70-79`)
- Provider failure isolation: one provider's failure doesn't affect others

**Extensibility Mechanisms:**
- Plugin discovery via naming convention or metadata
- No hardcoded provider references in orchestrator
- Configuration-driven provider enablement

### 4.6 Message Template System

**Responsibilities:**
- Template loading from configuration
- Placeholder identification and validation
- Placeholder replacement with runtime values
- Provider-specific formatting delegation

**Key Design Decisions:**
- Generic template representation with typed placeholders
- Lazy evaluation: templates processed only when notifications triggered
- Provider-specific formatters implement formatting protocol
- Support for different placeholder requirements per provider
- Validation ensuring all required placeholders available at render time

**Supported Placeholders:**
- `{percent}`: Progress percentage
- `{remaining_data}`: Human-readable remaining data size
- `{etc}`: Estimated time of completion (provider-specific format)
- `{moved_data}`: Amount of data moved so far
- `{total_data}`: Total data to be moved
- `{rate}`: Current data movement rate

---

## 5. Plugin System Architecture

### 5.1 Provider Plugin Interface Design

The plugin system leverages Python's Protocol for structural subtyping, enabling provider implementations without inheritance coupling.

**Core Protocol Definition:**

Following the guideline for small, composable Protocols (`.claude/python-313-pro.md:44-56`), the provider interface consists of focused protocol definitions:

**NotificationProvider Protocol:**
- **Purpose**: Defines the contract all notification providers must implement
- **Methods**:
  - Async notification delivery method accepting generic notification data
  - Configuration validation method
  - Health check method for connectivity verification
- **Return Types**: Typed responses using modern generic syntax (`.claude/python-313-pro.md:413-428`)

**MessageFormatter Protocol:**
- **Purpose**: Defines provider-specific message formatting contract
- **Methods**:
  - Template rendering method accepting placeholders
  - Time format conversion method
  - Platform-specific rich content formatting (embeds, HTML, etc.)

**HTTPClient Protocol:**
- **Purpose**: Abstracts webhook delivery mechanism
- **Methods**:
  - Async POST method with timeout support
  - Response validation method
  - Retry logic for transient failures

### 5.2 Plugin Discovery and Dynamic Loading

**Discovery Mechanism:**

- **Convention-Based Discovery**: Plugins located in dedicated `plugins/` directory with standardized naming
- **Metadata Registration**: Each plugin exposes metadata (name, version, required config fields)
- **Automatic Scanning**: Plugin orchestrator scans plugins directory at startup
- **Conditional Loading**: Only enabled providers (per main config) are loaded

**Loading Strategy:**

- **Lazy Initialization**: Plugins instantiated only when first needed
- **Validation on Load**: Plugin configuration validated before activation
- **Error Handling**: Loading failures logged with clear diagnostics; app continues with remaining plugins
- **Version Compatibility**: Plugin metadata includes minimum/maximum app version

**Security Considerations:**

- **No Dynamic Code Execution**: Plugins are imported, not exec'd
- **Explicit Plugin Directory**: No searching arbitrary paths
- **Validation Before Load**: Plugin config validated against schema before initialization

### 5.3 Provider Isolation and Encapsulation Strategy

**Complete Self-Containment Principle:**

Each provider plugin is entirely self-contained within its directory structure:

**Provider Package Structure:**
- Provider-specific API client implementation
- Message formatter implementation for platform requirements
- Configuration schema (Pydantic model) defining required fields
- Rich content builders (embeds for Discord, HTML for Telegram)
- Platform-specific error handling and retry logic
- Provider-specific constants and enumerations

**No Shared Provider Code:**

- Zero dependencies between provider plugins
- No shared provider-specific utilities
- Each provider independently implements its requirements
- Common infrastructure (HTTP client, logging) used via protocols, not shared provider code

**Configuration Isolation:**

- Each provider has dedicated YAML configuration file
- Provider config schema defined within provider package
- Validation logic specific to provider's requirements
- No cross-provider configuration dependencies

**API Client Encapsulation:**

- Webhook URL handling specific to provider
- Authentication mechanism specific to provider (tokens, API keys, etc.)
- Rate limiting logic specific to provider's API constraints
- Response parsing tailored to provider's API responses

### 5.4 Plugin Lifecycle Management

**Initialization Phase:**
1. Plugin discovery scans plugins directory
2. Enabled providers identified from main configuration
3. Provider-specific configurations loaded and validated
4. Provider instances created with validated configuration
5. Health checks performed to verify connectivity
6. Providers registered in plugin registry

**Operational Phase:**
1. Notification requests received from core application
2. Generic notification data dispatched to all registered providers concurrently
3. Each provider formats message according to platform requirements
4. HTTP client delivers formatted message with timeout protection
5. Errors handled per provider without affecting others
6. Success/failure logged for observability

**Shutdown Phase:**
1. Graceful shutdown signal received
2. Pending notifications allowed to complete within timeout
3. Provider cleanup methods invoked
4. Resources released (HTTP connections, file handles)
5. Final status logged

**Error Recovery:**
- Transient failures: Automatic retry with exponential backoff
- Permanent failures: Provider marked unhealthy; continue with other providers
- Configuration errors: Provider disabled until config corrected and app restarted

---

## 6. Two-Tier Configuration Strategy

### 6.1 Main Application YAML Structure and Responsibilities

**Location**: Project root or designated configuration directory (e.g., `config/mover-status.yaml`)

**Primary Responsibilities:**

- **Provider Enablement**: Boolean flags determining which providers are active
- **General Application Settings**: Monitoring intervals, notification thresholds, logging levels
- **Mover Integration Settings**: PID file location, process name patterns, timeout values
- **Exclusion Paths**: Directory exclusions for disk usage calculation
- **Application Behavior**: Dry-run mode, debug logging, version checking enablement

**Configuration Categories:**

**Monitoring Configuration:**
- PID file path for mover detection
- Disk usage sampling interval
- Process detection timeout
- Exclusion path list

**Notification Configuration:**
- Progress notification threshold percentages
- Completion notification enablement
- Message template selections
- Notification retry attempts

**Provider Enablement:**
- Boolean flags per provider (e.g., `discord_enabled: true`, `telegram_enabled: false`)
- Future providers added with additional boolean flags

**Application Settings:**
- Logging level and format
- Dry-run mode for testing
- Version checking against GitHub releases
- Syslog integration enablement

### 6.2 Provider-Specific YAML Auto-Creation and Validation

**Auto-Creation Workflow:**

1. Main configuration loaded and parsed
2. Enabled providers identified from boolean flags
3. For each enabled provider:
   - Check if provider-specific YAML exists (e.g., `config/providers/discord.yaml`)
   - If missing, generate template with commented examples
   - Prompt user (or fail with clear instructions) to populate required fields
4. Load each provider-specific YAML
5. Validate against provider's Pydantic schema
6. Halt startup if any provider config invalid

**Provider Configuration Isolation:**

Each provider's YAML contains only settings relevant to that provider:

**Discord Provider Configuration:**
- Webhook URL (validated format)
- Custom username override
- Embed color preferences
- Rich embed field customizations

**Telegram Provider Configuration:**
- Bot token (from environment variable reference)
- Chat ID
- Message parse mode (HTML/Markdown)
- Message threading preferences

**Future Provider Configurations:**
- Each new provider defines its own schema
- No impact on existing provider configurations
- Additive model: adding providers doesn't affect others

### 6.3 Configuration Validation Approach Using Pydantic

Following the guideline for Pydantic validation at API boundaries (`.claude/python-313-pro.md:504-514`):

**Main Configuration Schema:**
- Pydantic BaseModel subclass defining application-wide settings
- ReadOnly fields for immutable runtime settings (`.claude/python-313-pro.md:402-411`)
- Field validators for complex validation logic (path existence, percentage ranges)
- Default value provision for optional settings

**Provider Configuration Schemas:**
- Each provider plugin defines its own Pydantic model
- Field validators specific to provider requirements (URL format, token format)
- Required vs. optional field distinction
- Custom validation methods for cross-field dependencies

**Validation Benefits:**
- Type safety at configuration boundaries
- Runtime validation preventing invalid configurations
- Clear error messages with field-level diagnostics
- Serialization/deserialization handled automatically
- IDE support for configuration editing

**Validation Timing:**
- Startup validation: All configurations validated before application begins
- Fail-fast philosophy: Invalid configuration prevents startup
- Detailed error reporting: Which file, which field, why invalid

### 6.4 Environment Variable Integration for Secrets

Following security best practices (`.claude/python-313-pro.md:516-537`):

**Secrets Management Strategy:**

- **Never Hardcode Secrets**: No tokens, API keys, or webhook URLs directly in YAML
- **Environment Variable References**: YAML contains references to environment variables
- **Runtime Resolution**: Secrets resolved from environment at application startup
- **Validation**: Missing required environment variables fail startup with clear errors

**Environment Variable Naming Convention:**
- Prefix: `MOVER_STATUS_`
- Provider-specific: `MOVER_STATUS_DISCORD_WEBHOOK_URL`
- Structured: `MOVER_STATUS_TELEGRAM_BOT_TOKEN`

**Configuration File Pattern:**
```yaml
# Provider config references environment variables
webhook_url: ${MOVER_STATUS_DISCORD_WEBHOOK_URL}
bot_token: ${MOVER_STATUS_TELEGRAM_BOT_TOKEN}
```

**Security Hardening:**
- Environment variable validation at startup
- No secret logging or error message exposure
- Secure handling in memory (no persistence to disk)
- Integration with Unraid's User Scripts environment variable support

**Development vs. Production:**
- Development: `.env` file for local secret management
- Production: Unraid User Scripts environment variable configuration
- Testing: Mock environment variables for unit tests

---

## 7. Module Responsibilities & Separation of Concerns

### 7.1 Core Modules

**Monitoring Module:**
- **Location**: `src/core/monitoring.py`
- **Responsibility**: Mover process lifecycle detection and state management
- **Dependencies**: Uses utility modules for PID file watching and process validation
- **Interfaces**: Exposes monitoring state via async generators or callbacks
- **Type Annotations**: Full type hints using modern syntax (`.claude/python-313-pro.md:18-26`)

**Calculation Module:**
- **Location**: `src/core/calculation.py`
- **Responsibility**: Progress percentage, ETC, and data rate calculations
- **Design**: Pure functions for testability
- **Data Structures**: Immutable dataclasses with slots=True (`.claude/python-313-pro.md:64`)
- **Dependencies**: Zero dependencies on monitoring or providers

**Orchestration Module:**
- **Location**: `src/core/orchestrator.py`
- **Responsibility**: Coordinates monitoring, calculation, and notification dispatch
- **Concurrency**: Uses TaskGroup for structured concurrency (`.claude/python-313-pro.md:91-98`)
- **Error Handling**: Exception groups with except* (`.claude/python-313-pro.md:70-79`)
- **State Management**: Context variables for task-local state (`.claude/python-313-pro.md:100-111`)

**Configuration Module:**
- **Location**: `src/core/config.py`
- **Responsibility**: Configuration loading, validation, and provider coordination
- **Validation**: Pydantic models for all configuration schemas
- **Environment Integration**: Environment variable resolution
- **Immutability**: ReadOnly TypedDict for runtime config (`.claude/python-313-pro.md:402-411`)

### 7.2 Provider Plugin Modules

**Plugin Package Structure:**
```
src/plugins/
├── discord/
│   ├── __init__.py          # Plugin entry point and metadata
│   ├── provider.py          # NotificationProvider implementation
│   ├── client.py            # Discord API client
│   ├── formatter.py         # Discord embed formatter
│   ├── config.py            # Discord configuration schema
│   └── constants.py         # Discord-specific constants
├── telegram/
│   ├── __init__.py          # Plugin entry point and metadata
│   ├── provider.py          # NotificationProvider implementation
│   ├── client.py            # Telegram API client
│   ├── formatter.py         # Telegram HTML formatter
│   ├── config.py            # Telegram configuration schema
│   └── constants.py         # Telegram-specific constants
└── [future_provider]/
    └── ...                  # Same structure for any new provider
```

**Plugin Isolation Guarantees:**
- No imports between provider plugins
- No shared state between providers
- Each provider independently testable
- Provider addition/removal doesn't affect others

### 7.3 Utility Modules

**HTTP Client Module:**
- **Location**: `src/utils/http_client.py`
- **Responsibility**: Webhook delivery with timeout and retry logic
- **Interface**: Protocol-based for pluggable implementations
- **Features**: Async HTTP POST, response validation, exponential backoff

**Formatting Module:**
- **Location**: `src/utils/formatting.py`
- **Responsibility**: Human-readable size formatting, time formatting utilities
- **Design**: Pure functions with comprehensive type annotations
- **Functionality**: Bytes to GB/TB/MB/KB conversion, timestamp formatting

**Template Module:**
- **Location**: `src/utils/template.py`
- **Responsibility**: Message template parsing and placeholder replacement
- **Features**: Template validation, placeholder enumeration, safe substitution
- **Security**: Prevent template injection attacks

**Logging Module:**
- **Location**: `src/utils/logging.py`
- **Responsibility**: Structured logging configuration and formatters
- **Integration**: Syslog integration for Unraid compatibility
- **Features**: Context-aware logging, log level management, structured output

### 7.4 Type Definition Modules

**Protocol Definitions:**
- **Location**: `src/types/protocols.py`
- **Content**: All Protocol definitions (NotificationProvider, MessageFormatter, HTTPClient)
- **Design**: Small, focused protocols (`.claude/python-313-pro.md:44-56`)
- **Documentation**: Each protocol extensively documented with usage examples

**Type Aliases:**
- **Location**: `src/types/aliases.py`
- **Content**: Complex type aliases using `type` statement (`.claude/python-313-pro.md:28-33`)
- **Purpose**: Improve readability and maintainability of complex type annotations

**Data Models:**
- **Location**: `src/types/models.py`
- **Content**: Shared data models (notification data, progress data, etc.)
- **Design**: Dataclasses with slots=True for memory efficiency (`.claude/python-313-pro.md:64`)

---

## 8. Data Flow & System Interactions

### 8.1 Application Startup Flow

1. **Configuration Loading Phase:**
   - Load main application YAML
   - Validate against main configuration schema
   - Identify enabled providers from boolean flags
   - Load provider-specific YAMLs for enabled providers
   - Validate each provider config against provider schema
   - Resolve environment variables for secrets
   - Halt on validation errors with diagnostic output

2. **Plugin Initialization Phase:**
   - Discover provider plugins from plugins directory
   - Load only enabled providers
   - Instantiate provider objects with validated configuration
   - Perform provider health checks (connectivity verification)
   - Register healthy providers in plugin registry
   - Log initialization summary (enabled providers, health status)

3. **Monitoring Preparation Phase:**
   - Initialize monitoring engine with mover configuration
   - Set up disk usage tracker with exclusion paths
   - Prepare message templates
   - Configure logging infrastructure
   - Enter mover waiting state

### 8.2 Mover Lifecycle Detection Flow

**Waiting State:**
1. Monitor `/var/run/mover.pid` for file creation
2. Poll at configurable interval with minimal resource usage
3. Handle false starts (PID file created but process not running)
4. Log waiting state transitions for debugging

**Started State:**
1. PID file detected
2. Validate process existence in process table
3. Capture baseline disk usage snapshot
4. Send "Mover Started" notification to all enabled providers concurrently
5. Transition to monitoring state
6. Initialize progress tracking variables

**Monitoring State:**
1. Begin periodic disk usage sampling loop
2. Calculate progress percentage from baseline and current usage
3. Evaluate notification thresholds (25%, 50%, 75%, etc.)
4. Calculate data movement rate across samples
5. Project ETC based on current rate
6. Send progress notifications when thresholds crossed
7. Continue until mover process terminates

**Completed State:**
1. Detect mover process termination (PID file removal or process disappearance)
2. Capture final disk usage
3. Calculate final statistics (total moved, duration, average rate)
4. Send "Mover Completed" notification with summary
5. Clean up monitoring resources
6. Return to waiting state for next mover run

**Error Handling:**
- Unexpected process termination: Send error notification, clean up, return to waiting
- Disk sampling failure: Log error, retry with exponential backoff
- Hung mover detection: Timeout after configurable duration, send warning notification

### 8.3 Notification Dispatch Flow

**Notification Request Creation:**
1. Triggering event occurs (threshold crossed, completion, error)
2. Gather current monitoring data (percentage, remaining, ETC, rate)
3. Create generic notification data structure (platform-agnostic)
4. Select appropriate message template
5. Create notification context with all placeholders

**Template Processing:**
1. Load template for notification type
2. Validate all required placeholders available
3. Perform placeholder replacement with current values
4. Generate base message content (before provider-specific formatting)

**Provider Dispatch (Concurrent):**
1. Retrieve all registered and healthy providers from plugin registry
2. Create TaskGroup for concurrent dispatch (`.claude/python-313-pro.md:91-98`)
3. For each provider, create task to:
   - Invoke provider's format method with notification data
   - Provider applies platform-specific formatting (embeds, HTML, etc.)
   - Invoke provider's send method with formatted message
   - HTTP client delivers message with timeout (`.claude/python-313-pro.md:147-155`)
   - Log delivery success or failure
4. Wait for all provider tasks to complete or fail
5. Handle exception groups for multi-provider failures (`.claude/python-313-pro.md:70-79`)

**Provider-Specific Formatting:**

**Discord Provider:**
- Convert notification data to Discord embed structure
- Apply color coding based on progress percentage
- Format ETC as Discord timestamp format (Unix timestamp with relative formatting)
- Build embed fields for progress metrics
- Add footer with version information

**Telegram Provider:**
- Convert notification data to HTML-formatted message
- Apply HTML tags for bold, italic formatting
- Format ETC as human-readable datetime string
- Construct message with proper HTML entity encoding
- Append footer with version information

**Future Providers:**
- Each implements formatting according to platform requirements
- No impact on other providers' formatting logic

**Failure Isolation:**
- Single provider failure doesn't prevent other providers from receiving notifications
- Failed provider logged for monitoring and alerting
- Temporary failures trigger retry logic
- Permanent failures mark provider unhealthy until restart

### 8.4 External API Integration Patterns

**HTTP Client Abstraction:**
- Protocol-based HTTP client interface
- Concrete implementation using async HTTP library (aiohttp or httpx)
- Request timeout enforcement (`.claude/python-313-pro.md:147-155`)
- Response validation (status codes, content types)
- Automatic retry for transient failures (5xx errors, network timeouts)
- Exponential backoff between retries

**Discord Webhook Integration:**
- Endpoint: POST to `https://discord.com/api/webhooks/{webhook_id}/{webhook_token}`
- Content-Type: application/json
- Payload: JSON embed structure with username override
- Rate Limiting: Respect Discord's rate limits (handled by retry logic)
- Error Handling: Parse Discord error responses for actionable diagnostics

**Telegram Bot API Integration:**
- Endpoint: POST to `https://api.telegram.org/bot{bot_token}/sendMessage`
- Content-Type: application/json
- Payload: JSON with chat_id, text, parse_mode
- Authentication: Bot token in URL path
- Error Handling: Parse Telegram error responses (invalid chat_id, bot blocked, etc.)

**GitHub Releases API Integration (Version Checking):**
- Endpoint: GET `https://api.github.com/repos/engels74/mover-status/releases`
- Headers: Accept: application/vnd.github.v3+json
- Response Parsing: Extract latest release tag, compare with current version
- Frequency: Configurable (e.g., once per day)
- Error Handling: Silent failure with logging (non-critical feature)

---

## 9. Type Safety & Modern Python 3.14+ Features

### 9.1 PEP 695 Generic Syntax Usage

Following the modern type parameter syntax (`.claude/python-313-pro.md:18-26`):

**Generic Provider Registry:**
- Use `class[T]` syntax for plugin registry generic over provider types
- Automatic variance inference for better type checker understanding
- Proper scoping eliminates TypeVar pollution in module namespace

**Generic Configuration Loader:**
- `def[T]` syntax for configuration loading functions generic over config types
- Type parameter bounds for ensuring loaded types are BaseModel subclasses
- Return type narrowing based on type parameter

**Generic Message Formatter:**
- Generic formatter interface accepting typed notification data
- Type-safe formatting pipeline from generic data to provider-specific formats

### 9.2 Protocol-Based Interfaces

Leveraging small, composable Protocols (`.claude/python-313-pro.md:44-56`):

**NotificationProvider Protocol:**
- Small interface with 2-3 methods maximum
- Async send method for notification delivery
- Config validation method
- Health check method

**MessageFormatter Protocol:**
- Single responsibility: format notification data for specific platform
- Pure transformation function signature
- No side effects, only data transformation

**HTTPClient Protocol:**
- Focused on HTTP request/response cycle
- Async POST method with typed request/response
- Timeout and retry configuration methods

**Composability:**
- Complex provider implementations compose multiple small protocols
- Testing simplified by mocking individual protocol implementations
- Interface segregation: implement only needed protocols

### 9.3 TypedDict Configuration Schemas

Using ReadOnly TypedDict fields (`.claude/python-313-pro.md:402-411`):

**Immutable Configuration Sections:**
- Runtime configuration marked with ReadOnly fields
- Prevents accidental modification after initialization
- Type checker enforces immutability without runtime overhead
- NotRequired fields for optional configuration parameters

**Nested Configuration Structures:**
- TypedDict composition for complex configuration hierarchies
- Clear separation between required and optional nested sections
- Type-safe access to configuration values throughout application

### 9.4 Async/Await Patterns with TaskGroup

Structured concurrency following guidelines (`.claude/python-313-pro.md:91-98`):

**Concurrent Notification Dispatch:**
- TaskGroup ensures all provider notifications complete or cancel together
- Automatic cleanup on exception: if one provider fails critically, others cancelled
- No orphaned tasks: TaskGroup guarantees proper lifecycle management
- True parallelism in free-threaded builds for I/O-bound webhook delivery

**Monitoring Loop Structure:**
- Main monitoring loop as long-running async task
- Disk sampling as periodic async tasks within TaskGroup
- Notification dispatch as concurrent task group per notification event
- Clean shutdown: cancel TaskGroup on shutdown signal

**Resource Management:**
- Async context managers for HTTP client lifecycle (`.claude/python-313-pro.md:133-145`)
- Automatic connection cleanup on exception or cancellation
- Proper resource release in free-threaded environments

### 9.5 Type Aliases and Type Statement

Modern type alias declarations (`.claude/python-313-pro.md:28-33`):

**Notification Data Type Alias:**
- `type NotificationData = dict[str, str | int | float]`
- Clear intent: notification data is structured dict with specific value types
- Better than TypeAlias annotation: syntax-level distinction from runtime values

**Provider Registry Type Alias:**
- `type ProviderRegistry[T] = dict[str, T]`
- Recursive type alias support for complex structures
- Proper scope for type parameters

**Configuration Type Aliases:**
- `type ProviderConfig = DiscordConfig | TelegramConfig | ...`
- Union type aliases for provider config variants
- Extensible: new providers add to union type

### 9.6 TypeIs for Type Predicates

Precise type narrowing (`.claude/python-313-pro.md:35-42`):

**Configuration Type Guards:**
- TypeIs-based predicates for determining specific provider config types
- Narrowing in both if and else branches (unlike TypeGuard)
- Matches isinstance() behavior for intuitive understanding

**Notification Data Validation:**
- TypeIs predicates validating notification data completeness
- Type checker understands validated data has all required fields
- Improved type safety in notification processing pipeline

---

## 10. Concurrency & Performance Strategy

### 10.1 Structured Concurrency with TaskGroup

Replacing gather/create_task with TaskGroup (`.claude/python-313-pro.md:91-98`):

**Benefits:**
- Automatic cancellation propagation when any task fails
- No orphaned tasks: all tasks complete or cancel together
- Clean error handling via exception groups
- True parallelism in free-threaded Python builds
- Explicit task lifetime management

**Application in Notification Dispatch:**
- Create TaskGroup for each notification event
- Spawn task per enabled provider
- All providers receive notification concurrently
- If one provider's HTTP request fails critically, others complete independently
- TaskGroup ensures all tasks finish before proceeding

**Application in Monitoring:**
- Periodic disk usage sampling as TaskGroup tasks
- Concurrent health checks for all providers
- Parallel initialization of multiple provider plugins

### 10.2 Async I/O for Webhook Notifications

**Webhook Delivery Parallelism:**
- Discord and Telegram webhook POSTs execute concurrently
- No blocking: while waiting for Discord response, Telegram request in flight
- Significant latency reduction: total time = max(provider latencies), not sum
- Timeout per provider prevents slow provider blocking others (`.claude/python-313-pro.md:147-155`)

**HTTP Client Async Design:**
- Async HTTP library (aiohttp or httpx) for non-blocking I/O
- Connection pooling for reused connections across notifications
- Concurrent request limits to prevent resource exhaustion
- Graceful degradation: slow provider doesn't block application

### 10.3 CPU-Bound Work Offloading

Using asyncio.to_thread for disk calculations (`.claude/python-313-pro.md:125-131`):

**Disk Usage Calculation:**
- Disk traversal and size calculation is CPU-bound and blocking
- Offload to thread pool via asyncio.to_thread
- Async monitoring loop remains responsive during calculations
- In free-threaded Python builds, true parallelism for CPU work (2.2-3.1x speedup on multi-core)
- Context variables preserved across thread boundary

**Benefits:**
- Monitoring loop doesn't block waiting for disk calculations
- Multiple disk paths can be calculated in parallel threads
- Maintains async/await code structure while handling sync operations
- Automatic in free-threaded builds without code changes

### 10.4 Context Variables for Task-Local State

Following context variable best practices (`.claude/python-313-pro.md:100-111`):

**Use Cases:**
- Request ID tracking across async tasks for correlated logging
- Provider-specific context during notification dispatch
- Monitoring session context for disk sampling tasks

**Advantages Over threading.local():**
- Automatic inheritance in asyncio tasks
- Proper isolation in concurrent task execution
- In free-threaded Python, threads copy caller's context on start
- No manual context passing through function chains

**Implementation:**
- ContextVar for notification session ID
- ContextVar for current provider during dispatch
- ContextVar for monitoring iteration count

### 10.5 Timeout Management

Using asyncio.timeout context manager (`.claude/python-313-pro.md:147-155`):

**Webhook Delivery Timeouts:**
- Each provider webhook POST wrapped in asyncio.timeout
- Configurable timeout per provider (e.g., 10 seconds)
- Prevents hung requests from blocking notification dispatch
- Nested timeouts supported: overall notification timeout + per-provider timeouts

**Monitoring Operation Timeouts:**
- Disk usage calculation timeout prevents hung filesystem operations
- Mover start detection timeout (if mover doesn't start within X minutes, alert)
- Provider health check timeouts during initialization

**Error Handling:**
- TimeoutError caught and logged with provider context
- Timed-out provider marked for retry or marked unhealthy
- Other providers continue unaffected

### 10.6 Free-Threading Considerations

Following free-threading performance guidance (`.claude/python-313-pro.md:168-179`):

**Applicable Scenarios:**
- CPU-bound disk usage calculations across multiple paths
- Parallel processing of multiple notification formatting tasks
- Concurrent provider health checks during initialization

**Detection and Adaptation:**
- Use `sys._is_gil_enabled()` to detect free-threaded builds (`.claude/python-313-pro.md:113-123`)
- Built-in types (dict, list, set) automatically thread-safe in free-threaded mode
- No code changes required: async with TaskGroup benefits automatically

**Performance Expectations:**
- 2.2-3.1x speedup on multi-core for parallel CPU-bound operations
- 5-10% single-thread overhead in 3.13; improved to ~5% in 3.14
- Primary benefit: concurrent webhook delivery truly parallel in free-threaded builds
- Secondary benefit: parallel disk scanning if monitoring multiple mover instances

**When NOT to Rely on Free-Threading:**
- Single-threaded execution: use standard async/await
- Pure I/O-bound operations: asyncio sufficient without free-threading
- Until Python 3.14 Phase II (October 2025): consider experimental

---

## 11. Error Handling & Resilience

### 11.1 Exception Groups for Concurrent Operations

Using exception groups with except* (`.claude/python-313-pro.md:70-79`):

**Multi-Provider Notification Failures:**
- TaskGroup may generate multiple exceptions (one per failed provider)
- ExceptionGroup contains all exceptions from failed provider tasks
- Use `except*` to handle specific exception types separately
- Example: `except* TimeoutError` handles all provider timeout failures together
- Example: `except* ValueError` handles all provider validation failures together

**Benefits:**
- No exception information lost when multiple providers fail simultaneously
- Detailed logging of each provider's specific failure
- Ability to handle different failure types with different recovery strategies
- Type-safe exception handling with proper type narrowing

**Error Categorization:**
- Transient errors (network timeouts, 5xx responses): Trigger retry logic
- Permanent errors (401 auth failures, invalid webhooks): Mark provider unhealthy
- Validation errors (malformed config): Fail fast during initialization

### 11.2 Provider Failure Isolation

**Design Principle:**
- Single provider failure MUST NOT prevent other providers from functioning
- Provider failures logged but don't propagate to application core
- Notification dispatch continues with healthy providers even if one fails

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

**Invalid Webhook Configuration:**
- Provider's webhook URL returns 404 Not Found
- Error logged with provider context
- Provider marked permanently unhealthy until configuration corrected
- Other providers continue functioning

**API Rate Limiting:**
- Provider's API returns 429 Too Many Requests
- Provider backs off according to Retry-After header
- Notification queued for retry
- Other providers deliver immediately

### 11.3 Retry Strategies

**Transient Failure Retry Logic:**

**Exponential Backoff:**
- Initial retry after 1 second
- Subsequent retries double interval: 2s, 4s, 8s, 16s
- Maximum retry interval: 60 seconds
- Maximum retry attempts: 5 (configurable)

**Jitter Addition:**
- Random jitter added to backoff interval to prevent thundering herd
- Jitter range: ±20% of calculated interval

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
- Prevents resource waste on persistently failing providers

### 11.4 Graceful Degradation

**Monitoring Continuation Despite Failures:**

**Notification Delivery Failures:**
- If all providers fail, monitoring continues
- Progress tracking and calculations continue normally
- Notification attempts continue at next threshold
- Detailed failure logging for post-mortem analysis

**Disk Sampling Failures:**
- If single disk sample fails, use previous sample data
- Log warning but don't halt monitoring
- Multiple consecutive failures trigger error notification (if any provider healthy)
- Configurable failure threshold before alerting

**Configuration Validation Failures:**
- Invalid provider config disables that provider only
- Application starts with healthy providers
- Disabled provider logged for administrator attention
- Hot-reload capability for config fixes without restart

**Mover Process Anomalies:**

**Mover Never Starts:**
- Timeout detection after configurable wait period
- Warning notification sent if providers healthy
- Monitoring resets to waiting state
- Logged for investigation (parity check running? mover disabled?)

**Mover Hung/Stalled:**
- No disk usage change for extended period
- Warning notification sent
- Monitoring continues (may resume)
- Configurable stall detection threshold

**Mover Crashed:**
- Unexpected process termination detected
- Error notification with last known state
- Clean up monitoring resources
- Return to waiting state for next run

---

## 12. Testing Strategy

### 12.1 Architecture Testability

**Testability by Design:**

The architecture prioritizes testability through:
- **Pure Functions**: Calculation logic implemented as pure functions with no side effects
- **Protocol-Based Interfaces**: Easy mocking via Protocol implementations
- **Dependency Injection**: Components receive dependencies rather than creating them
- **Immutable Data**: Dataclasses with slots=True for predictable test data
- **Small, Focused Modules**: Each module testable in isolation

**Test Structure:**

Following the guideline to mirror project structure (`.claude/python-313-pro.md:292-308`):

```
tests/
├── unit/
│   ├── core/
│   │   ├── test_monitoring.py
│   │   ├── test_calculation.py
│   │   └── test_orchestrator.py
│   ├── plugins/
│   │   ├── test_discord.py
│   │   └── test_telegram.py
│   └── utils/
│       ├── test_formatting.py
│       └── test_template.py
├── integration/
│   ├── test_plugin_loading.py
│   ├── test_notification_flow.py
│   └── test_configuration.py
└── property/
    ├── test_calculation_properties.py
    └── test_formatting_properties.py
```

### 12.2 Mock Provider Patterns

**Protocol-Based Mocking:**

**Mock NotificationProvider:**
- Implements NotificationProvider Protocol
- Records all invocations for assertion
- Configurable responses (success, failure, timeout)
- No actual HTTP requests made

**Mock HTTPClient:**
- Implements HTTPClient Protocol
- Returns predefined responses
- Simulates network conditions (latency, timeouts, errors)
- Captures request data for verification

**Mock Configuration:**
- Minimal valid configuration for fast test execution
- Predefined configuration variants (all providers enabled, single provider, no providers)
- Invalid configurations for testing validation logic

**Testing Provider Isolation:**
- Verify single provider failure doesn't affect others
- Concurrent notification delivery with mixed success/failure
- Exception group handling validation

### 12.3 Fixture-Based Testing

Following pytest fixture best practices (`.claude/python-313-pro.md:292-308`):

**Fixture Scopes:**

**Session-Scoped Fixtures:**
- Mock Unraid environment setup (PID file location, cache path)
- Test configuration file creation
- Expensive initialization performed once

**Module-Scoped Fixtures:**
- Plugin registry initialization
- Provider mock instances
- Configuration loader instances

**Function-Scoped Fixtures:**
- Notification data instances (fresh per test)
- Monitoring state objects
- Progress calculation inputs

**Fixture Composition:**
- Higher-level fixtures compose lower-level fixtures
- Example: `notification_system` fixture composes `plugin_registry`, `config_loader`, and `http_client`
- Reduces test setup duplication

**Fixture Examples:**

**monitoring_engine fixture:**
- Provides fully initialized monitoring engine
- Mock PID file watching
- Configurable mover start delay

**provider_registry fixture:**
- Provides plugin registry with mock providers
- Configurable provider health states
- Captured notification history

**disk_usage_tracker fixture:**
- Provides tracker with mock disk usage data
- Configurable usage progression
- Deterministic sampling for reproducible tests

### 12.4 Parametrized Testing

Using pytest parametrization (`.claude/python-313-pro.md:303-308`):

**Progress Calculation Tests:**
- Parametrize over various progress percentages (0%, 25%, 50%, 75%, 100%)
- Edge cases: negative movement, zero movement, overflow
- Boundary conditions: exactly at threshold, just below, just above

**Message Formatting Tests:**
- Parametrize over different notification types (start, progress, completion)
- Multiple provider formats (Discord, Telegram, future providers)
- Various template placeholder combinations

**Configuration Validation Tests:**
- Parametrize over valid configurations
- Parametrize over invalid configurations with expected error messages
- Combinations of enabled/disabled providers

### 12.5 Property-Based Testing

Using Hypothesis for invariant testing (`.claude/python-313-pro.md:310-318`):

**Progress Calculation Invariants:**
- Progress percentage always between 0 and 100
- Remaining data always non-negative
- ETC always in future (not past)
- Rate calculation never produces NaN or Infinity

**Hypothesis Strategies:**
- Generate arbitrary disk usage values within realistic ranges
- Generate random sampling intervals
- Generate edge case inputs (zero, very large, very small)

**Invariant Examples:**

**Reversibility:**
- Converting bytes to human-readable and back yields original value (within precision)

**Monotonicity:**
- As moved data increases, progress percentage increases (or stays same)
- As time progresses, ETC approaches completion time

**Boundary Conditions:**
- 0% moved → 0% progress
- 100% moved → 100% progress
- No movement → ETC = infinity or undefined

### 12.6 Type Checking Integration

Following multi-checker CI pipeline (`.claude/python-313-pro.md:430-439`):

**basedpyright Configuration:**
- `typeCheckingMode = "recommended"` (`.claude/python-313-pro.md:364-377`)
- `failOnWarnings = true` for strict enforcement
- Covers entire codebase including tests

**ty for Fast Feedback:**
- Used in watch mode during development (`.claude/python-313-pro.md:379-390`)
- Pre-commit hook for fast type checking
- CI integration for ultra-fast validation

**Type Checking in Tests:**
- Test code fully type-annotated
- Mock objects properly typed with Protocol conformance
- Fixture return types explicitly annotated
- Parametrized test inputs typed

---

## 13. Deployment & Packaging Considerations

### 13.1 Distribution Strategy

**Packaging Format:**
- Standard Python package with `pyproject.toml` following PEP 621 (`.claude/python-313-pro.md:328-343`)
- Entry point script for command-line execution
- Packaged via uv build backend (`.claude/python-313-pro.md:258-270`)

**Dependency Management:**
- Minimal runtime dependencies (async HTTP client, Pydantic, PyYAML)
- Development dependencies separated in optional-dependencies
- uv for dependency resolution and locking (`.claude/python-313-pro.md:246-256`)

**Version Compatibility:**
- `requires-python = ">=3.14"` for access to all modern features
- SPEC 0 support policy: 3-year minimum support (`.claude/python-313-pro.md:541-546`)

### 13.2 Dependency Management with uv

Following uv best practices (`.claude/python-313-pro.md:246-256`):

**Development Workflow:**
- `uv init` for project initialization
- `uv add` for dependency addition with automatic locking
- `uv run` for executing application in managed environment
- `uv sync` for reproducible development environment setup

**Lock File:**
- `uv.lock` provides reproducible builds across environments
- Cross-platform lock file for Linux (Unraid), macOS (development), Windows (testing)
- Hash verification for supply chain security (`.claude/python-313-pro.md:465-474`)

**Production Requirements:**
- `uv export --frozen --generate-hashes > requirements.txt` for deployment
- Hash-verified installation: `pip install --require-hashes -r requirements.txt`
- Minimal attack surface: only runtime dependencies included

### 13.3 Configuration Deployment

**Configuration File Locations:**

**Development:**
- Configuration in project root or `config/` directory
- `.env` file for local secrets
- Git-ignored sensitive configuration

**Production (Unraid):**
- Configuration in persistent location (e.g., `/boot/config/plugins/mover-status/`)
- Survives Unraid reboots and updates
- Backed up with Unraid flash drive

**Configuration Initialization:**
- First run: detect missing configuration files
- Generate template configuration files with commented examples
- Prompt user to populate required fields
- Validate before allowing application to run

### 13.4 Unraid Integration Approach

**User Scripts Plugin Integration:**

**Installation:**
- User Scripts plugin provides scheduled and manual execution
- Application installed in persistent location
- Python 3.14 installed via Nerd Tools or standalone

**Execution Mode:**
- Background script execution for continuous monitoring
- User Scripts manages process lifecycle (start, stop, restart)
- Application logs to syslog for integration with Unraid logging

**Environment Variables:**
- User Scripts supports environment variable definition
- Secrets configured via User Scripts UI
- Variables available to Python application at runtime

**Startup Behavior:**
- Application starts automatically with array start (configurable)
- Graceful shutdown on array stop
- Status reporting via User Scripts UI

**Resource Considerations:**
- Minimal CPU usage: async I/O with efficient disk sampling
- Minimal memory footprint: dataclasses with slots=True
- Configurable sampling intervals for resource tuning
- Nice/ionice levels configurable for priority management

### 13.5 Logging and Observability

**Logging Infrastructure:**

**Syslog Integration:**
- Python logging configured to send to Unraid syslog
- Standard syslog severity levels (DEBUG, INFO, WARNING, ERROR)
- Structured logging with contextual information

**Log Levels:**
- DEBUG: Detailed diagnostic information (disk samples, calculation details)
- INFO: Operational events (mover started, notifications sent, thresholds crossed)
- WARNING: Unexpected but handled situations (provider failures, retries)
- ERROR: Serious problems requiring attention (configuration errors, all providers failed)

**Contextual Logging:**
- Each log entry includes relevant context (provider name, notification type, progress percentage)
- Correlation IDs for tracking notifications across providers
- Timestamp, module, and function information

**Log Rotation:**
- Leverage Unraid's syslog rotation
- Configurable verbosity to control log volume
- Debug mode for troubleshooting

**Observability Features:**
- Health check endpoint (optional) for monitoring tools
- Metrics export (optional) for monitoring systems
- Status file for current monitoring state (useful for dashboard integration)

---

## 14. Extensibility & Future Growth

### 14.1 Adding New Providers Without Core Changes

**Zero-Modification Extension:**

Adding a new notification provider (e.g., Slack, Microsoft Teams, PagerDuty, email) requires:

1. **Create Provider Plugin Package:**
   - Create new directory: `src/plugins/new_provider/`
   - Implement NotificationProvider Protocol
   - Implement provider-specific MessageFormatter
   - Define provider-specific configuration schema (Pydantic model)
   - Create provider API client for webhook delivery

2. **Provider Configuration:**
   - Create YAML template: `config/providers/new_provider.yaml.template`
   - Document required configuration fields
   - Define validation rules in Pydantic schema

3. **Enable Provider:**
   - Add boolean flag to main config: `new_provider_enabled: true`
   - Populate provider-specific YAML with required fields
   - Restart application

**No Core Code Changes Required:**
- Plugin discovery automatically finds new provider
- Notification dispatcher includes new provider in TaskGroup
- Configuration loader validates new provider config
- Template system works with new provider's formatter

**Provider Interface Stability:**
- NotificationProvider Protocol remains stable
- New providers implement current protocol version
- Protocol versioning for future breaking changes

### 14.2 Extension Points

**Custom Message Formatters:**
- New formatters can be added by implementing MessageFormatter Protocol
- Formatters can be swapped per provider via configuration
- Custom formatting logic for specialized use cases

**Alternative HTTP Clients:**
- HTTPClient Protocol allows alternative implementations
- Example: HTTP/2-specific client, client with custom authentication
- Swap via configuration without affecting providers

**Additional Monitoring Metrics:**
- Extensible calculation module for new metrics
- Examples: average movement rate, peak rate, predicted completion window
- New metrics available to all providers via notification data

**Plugin Hook System:**
- Optional hooks for plugin lifecycle events
- Pre-notification hooks for data enrichment
- Post-notification hooks for logging or integration

**Custom Notification Triggers:**
- Beyond threshold-based notifications
- Time-based triggers (e.g., notification every hour)
- Rate-change triggers (e.g., notify if movement rate drops significantly)
- Custom trigger implementations via configuration

### 14.3 Provider-Specific Features

**Rich Content Support:**

**Discord:**
- Embed customization: custom colors, thumbnail images, author fields
- Multiple embeds per notification
- File attachments (e.g., progress graphs)
- Interactive components (buttons, select menus) in future

**Telegram:**
- Inline keyboards for interaction
- Message editing for live progress updates
- Photo/document attachments
- Bot commands for querying current status

**Future Providers:**
- Email: HTML formatting, inline images, attachments
- Slack: Rich blocks, interactive components
- Microsoft Teams: Adaptive cards
- PagerDuty: Incident creation and updates

**Provider Capability Declaration:**
- Providers declare supported features via metadata
- Core application queries capabilities before requesting features
- Graceful degradation: unsupported features omitted

### 14.4 Backward Compatibility Considerations

**Configuration Compatibility:**
- New configuration fields added with sensible defaults
- Old configuration files continue working
- Deprecation warnings for breaking changes

**API Compatibility:**
- Semantic versioning for application and Protocol versions
- Breaking changes increment major version
- Providers declare minimum/maximum compatible application versions
- Runtime compatibility checks prevent incompatible combinations

**Message Template Compatibility:**
- New placeholders added without breaking existing templates
- Unknown placeholders logged as warnings
- Templates validated against provider capabilities

**Data Format Stability:**
- Notification data structure versioned
- Backward-compatible additions to data structure
- Providers handle missing fields gracefully (use defaults)

---

## 15. Migration Path from Bash Script

### 15.1 Feature Parity Requirements

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
- ✓ Version checking against GitHub releases

**Configuration Parity:**
- ✓ All bash script variables mapped to YAML configuration
- ✓ Exclusion paths support (unlimited, not just 02 paths)
- ✓ Customizable notification messages (templates)
- ✓ Provider enable/disable flags
- ✓ Notification threshold configuration

**Behavioral Parity:**
- ✓ Same notification timing (at same progress percentages)
- ✓ Same message content and formatting
- ✓ Same ETC calculation logic
- ✓ Continuous monitoring loop (wait → monitor → wait cycle)
- ✓ Process priority respect (nice/ionice) via Unraid User Scripts

### 15.2 Behavioral Preservation

**Notification Timing:**
- Identical threshold evaluation logic
- Same default thresholds (0%, 25%, 50%, 75%, 100%)
- Notification sent at exact threshold crossing (not before or after)

**Progress Calculation:**
- Same calculation algorithm: `(baseline - current) / baseline * 100`
- Same rounding behavior for percentage display
- Same handling of edge cases (negative movement, overflow)

**ETC Calculation:**
- Same rate calculation: delta size / delta time
- Same ETC projection: remaining / rate
- Same time formatting per provider (Unix timestamp for Discord, datetime string for Telegram)

**Message Content:**
- Default templates produce identical output to bash script
- Placeholder values formatted identically
- Provider-specific formatting preserved (colors, bold, etc.)

**Monitoring Loop:**
- Same waiting → started → monitoring → completed cycle
- Same PID file watching behavior
- Same process detection validation
- Same sampling interval defaults

**Error Handling:**
- Similar resilience to provider failures
- Same logging verbosity levels
- Same dry-run behavior (logging without sending)

### 15.3 Incremental Migration Approach

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

**Rollback Strategy:**
- Bash script preserved during migration
- Quick re-enable if Python application issues arise
- Configuration migration reversible (keep bash config backup)
- Documented rollback procedure

---

## 16. Development Tooling & Standards

### 16.1 Package Management: uv

Following uv best practices (`.claude/python-313-pro.md:246-256`):

**Project Initialization:**
- `uv init mover-status --lib` for project structure
- Generates `pyproject.toml` with PEP 621 metadata
- Creates `src/` layout for proper packaging

**Dependency Management:**
- `uv add` for runtime dependencies (automatic version resolution)
- `uv add --dev` for development dependencies
- `uv lock` for reproducible builds
- `uv sync` for environment synchronization

**Performance Benefits:**
- 10-100x faster than pip for dependency resolution
- Unified tooling: package management + Python version management
- Cross-platform compatibility (Linux, macOS, Windows)

**Integration:**
- CI/CD uses uv for fast, reproducible builds
- Pre-commit hooks use uv for tool execution
- Development environment setup simplified: single `uv sync` command

### 16.2 Linting & Formatting: ruff

Following ruff configuration (`.claude/python-313-pro.md:272-290`):

**Configuration in pyproject.toml:**
- `line-length = 88` (Black compatibility)
- `target-version = "py314"` for Python 3.14+ features
- Select rules: E (pycodestyle errors), F (pyflakes), B (bugbear), I (isort), N (naming), UP (pyupgrade), C90 (complexity)

**Auto-Fixing:**
- `ruff check . --fix` for automatic issue resolution
- `ruff format .` for code formatting
- 10-100x faster than Black+isort+Flake8 combined

**Pre-Commit Integration:**
- ruff runs on every commit
- Auto-fix applied when possible
- Formatting enforced consistently

**CI Integration:**
- ruff check in CI pipeline (fails on violations)
- ruff format --check for formatting validation
- Fast feedback: milliseconds vs. seconds for traditional tools

### 16.3 Type Checking: basedpyright & ty

**basedpyright Configuration:**

Following recommended mode (`.claude/python-313-pro.md:364-377`):

- `typeCheckingMode = "recommended"` for comprehensive checking
- `failOnWarnings = true` for strict enforcement
- `reportUnreachable = "warning"` for dead code detection
- `reportAny = "warning"` for Any usage tracking
- `enableTypeIgnoreComments = false` for explicit rule-scoped ignores

**ty for Fast Feedback:**

Following ty best practices (`.claude/python-313-pro.md:379-390`):

- Watch mode during development: `ty check --watch`
- Pre-commit hook for fast type checking (10-100x faster than basedpyright)
- Concise output for quick issue identification

**Multi-Checker CI:**

Following multi-checker pipeline (`.claude/python-313-pro.md:430-439`):

- CI runs both ty (fast) and basedpyright (comprehensive)
- ty provides quick feedback on common issues
- basedpyright catches subtle type errors
- Both must pass for merge approval

**Type Ignore Comments:**

Following explicit ignore guideline (`.claude/python-313-pro.md:392-400`):

- Rule-scoped ignores only: `# pyright: ignore[reportUnknownVariableType]`
- Never bare `# type: ignore`
- Every ignore accompanied by comment explaining why

### 16.4 Testing: pytest, Hypothesis, memray

**pytest Configuration:**

- Fixture-based testing (`.claude/python-313-pro.md:292-308`)
- Parametrization for reducing duplication
- Coverage reporting with pytest-cov
- Parallel test execution with pytest-xdist

**Hypothesis for Property-Based Testing:**

Following Hypothesis integration (`.claude/python-313-pro.md:310-318`):

- Properties for calculation invariants
- Automatic edge case generation
- Shrinking for minimal failing examples

**Memory Profiling with memray:**

Following memray usage (`.claude/python-313-pro.md:210-221`):

- Memory limit tests: `@pytest.mark.limit_memory("100 MB")`
- Leak detection for long-running operations
- Peak memory analysis for optimization targets

**Performance Testing:**

- pytest-benchmark for regression detection (`.claude/python-313-pro.md:320-326`)
- Baseline establishment for critical paths (disk usage calculation, notification dispatch)
- CI integration for performance regression detection

### 16.5 Multi-Environment Testing: Nox

Following Nox best practices (`.claude/python-313-pro.md:345-360`):

**Noxfile Sessions:**

**tests session:**
- Run across Python 3.14 (and future 3.15+)
- Standard and free-threaded builds (`.claude/python-313-pro.md:598-615`)
- Full test suite with coverage

**lint session:**
- ruff check for linting
- ruff format --check for formatting validation
- Fast feedback loop

**typecheck session:**
- basedpyright for comprehensive type checking
- ty for fast validation
- Both must pass

**Security session:**
- pip-audit for dependency vulnerability scanning (`.claude/python-313-pro.md:452-463`)
- bandit for code security analysis
- safety check for additional scanning

**Integration with uv:**
- Nox sessions use uv for 10-100x faster execution
- Reproducible environments via uv's dependency locking
- Cross-platform consistency

### 16.6 CI/CD Pipeline

**GitHub Actions Workflow:**

**On Pull Request:**
1. Fast checks (ty type checking, ruff linting)
2. Comprehensive checks (basedpyright type checking)
3. Test suite across Python versions and free-threading variants
4. Security scanning (pip-audit, bandit)
5. Coverage reporting

**On Main Branch:**
- All PR checks plus:
- Documentation generation
- Package building with uv build
- Optional deployment to test environment

**On Release Tag:**
- All main branch checks plus:
- Version verification
- Package building with hash verification (`.claude/python-313-pro.md:465-474`)
- GitHub release creation
- Optional PyPI publishing with Trusted Publishing (`.claude/python-313-pro.md:476-490`)

**Performance:**
- uv provides 10-100x faster dependency installation
- ty provides fast type checking for quick feedback
- Parallel test execution with pytest-xdist
- Cached dependencies for faster subsequent runs

---

## 17. Security Considerations

### 17.1 Secret Management

Following security best practices (`.claude/python-313-pro.md:516-537`):

**Never Hardcode Secrets:**
- No tokens, API keys, or webhook URLs in source code
- No secrets in configuration files committed to version control
- No secrets in logs or error messages

**Environment Variable Strategy:**
- All secrets stored in environment variables
- Naming convention: `MOVER_STATUS_<PROVIDER>_<SECRET_NAME>`
- Configuration files reference environment variables
- Runtime resolution with clear errors for missing variables

**Unraid Integration:**
- User Scripts plugin supports environment variable configuration
- Secrets configured via User Scripts UI (not in script file)
- Environment variables isolated per script
- No accidental leakage to other scripts

**Development Workflow:**
- `.env` file for local development (git-ignored)
- `.env.template` committed with dummy values
- Documentation for required environment variables
- Validation at startup for missing secrets

**Secret Rotation:**
- No application restart required for secret rotation (via environment variable update)
- Graceful handling of authentication failures post-rotation
- Logging for authentication issues without exposing secrets

### 17.2 Webhook URL Validation

**Discord Webhook Validation:**
- Regex pattern matching Discord webhook URL format
- Scheme validation (HTTPS only)
- Domain validation (discord.com or discordapp.com)
- Path validation (webhook ID and token format)
- Reject malformed URLs at configuration validation time

**Telegram Validation:**
- Bot token format validation (numeric ID:alphanumeric token)
- Chat ID format validation (numeric or @username)
- No HTTPS URL needed (API endpoint hardcoded)

**General URL Security:**
- Prevent SSRF attacks: reject private IP ranges if URL-based providers added
- Scheme allowlist: HTTPS only (no HTTP, file://, etc.)
- DNS rebinding protection for future URL-based providers

### 17.3 Input Sanitization

Following Pydantic validation (`.claude/python-313-pro.md:504-514`):

**Configuration Validation:**
- All configuration fields validated against Pydantic schemas
- Type validation (strings, integers, booleans)
- Format validation (URLs, paths, percentages)
- Range validation (thresholds between 0-100, intervals positive)
- Reject invalid configurations before application starts

**Message Template Validation:**
- Placeholder validation: only known placeholders allowed
- No arbitrary code execution in templates
- No user-provided template evaluation
- Safe string substitution only

**User-Provided Data:**
- Custom message templates validated for injection risks
- Exclusion paths validated for existence and accessibility
- No shell command execution with user-provided data

### 17.4 Dependency Security

Following multi-tool scanning strategy (`.claude/python-313-pro.md:452-463`):

**Vulnerability Scanning:**

**pip-audit:**
- Scans against PyPI advisory database
- Daily runs in CI/CD
- Fails build on high/critical vulnerabilities

**bandit:**
- Static code analysis for security issues
- Detects common security anti-patterns
- Pre-commit hook for early detection

**safety:**
- Additional vulnerability database
- Complementary to pip-audit for broader coverage

**Hash Verification:**

Following hash verification guideline (`.claude/python-313-pro.md:465-474`):

- Production requirements generated with hashes: `uv export --generate-hashes`
- Installation with hash verification: `pip install --require-hashes`
- Prevents dependency confusion and typosquatting attacks
- Supply chain security post-2024 PyPI compromises

**Dependency Pinning:**
- Exact version pinning in production via uv.lock
- Dependabot or Renovate for automated update PRs
- Reviewed updates with changelog inspection
- Test suite validation before accepting updates

### 17.5 Network Security

**TLS/HTTPS Enforcement:**
- All webhook URLs must use HTTPS
- Certificate validation enabled (no certificate pinning needed for public APIs)
- Reject self-signed certificates (production)
- Configurable certificate validation for testing environments only

**Timeout Protection:**
- All HTTP requests have timeouts (`.claude/python-313-pro.md:147-155`)
- Prevent hung connections from resource exhaustion
- Configurable timeouts per provider

**Rate Limiting:**
- Respect provider rate limits (Discord, Telegram)
- Exponential backoff on rate limit responses
- Circuit breaker for persistently rate-limited providers
- Prevent accidental DoS of provider APIs

**Request Size Limits:**
- Maximum message size validation per provider
- Truncation strategy for oversized messages
- Prevent memory exhaustion from large payloads

---

## 18. Performance Optimization Strategies

### 18.1 Free-Threading Performance

Following free-threading guidance (`.claude/python-313-pro.md:168-179`):

**Applicable Scenarios:**
- CPU-bound disk usage calculations with multiple exclusion paths
- Parallel calculation of progress metrics
- Concurrent provider notification formatting

**Expected Performance Gains:**
- 2.2-3.1x speedup on multi-core systems for parallel operations
- Negligible benefit for I/O-bound webhook delivery (already parallel via asyncio)
- ~5-10% single-thread overhead in Python 3.14

**Detection and Adaptation:**
- Runtime detection: `sys._is_gil_enabled()` (`.claude/python-313-pro.md:113-123`)
- No code changes required: TaskGroup automatically benefits
- Built-in types (dict, list, set) automatically thread-safe

**When to Leverage:**
- Monitoring multiple mover instances simultaneously
- Parallel disk scanning across multiple paths
- Batch notification delivery with CPU-bound formatting

**When NOT to Rely On:**
- Single-threaded Unraid environments (most common)
- Pure I/O-bound operations (use asyncio)
- Until Python 3.14 Phase II maturity (October 2025)

### 18.2 Memory Optimization

**Dataclasses with Slots:**

Following memory efficiency guideline (`.claude/python-313-pro.md:64`):

- All dataclasses defined with `slots=True`
- 40% memory savings for data-intensive structures
- Particularly important for:
  - Progress data samples (many instances over time)
  - Notification data structures
  - Configuration objects

**Efficient Data Structures:**
- Use built-in types (list, dict, set) for automatic free-threading safety
- Avoid unnecessary data copying
- Generator expressions for large iterations
- Streaming disk usage calculation (no full tree in memory)

**Memory Profiling:**

Following memray usage (`.claude/python-313-pro.md:210-221`):

- Periodic profiling during development
- Memory limit tests for critical paths
- Leak detection for long-running monitoring loop
- Peak memory analysis for optimization targets

### 18.3 CPU Profiling

Following py-spy best practices (`.claude/python-313-pro.md:194-208`):

**Profiling Strategy:**
- Profile production-like workloads (full mover cycle)
- Identify CPU hotspots (disk usage calculation, progress calculation)
- Flamegraph visualization for optimization targets
- GIL contention analysis for free-threading candidates

**Optimization Targets:**
- Disk usage calculation: most CPU-intensive operation
- Progress calculation: frequent operation, optimize for speed
- Message formatting: concurrent operations, optimize for parallelism

**Continuous Profiling:**
- Periodic profiling in CI/CD for regression detection
- Baseline performance metrics for critical paths
- Performance tests with pytest-benchmark

### 18.4 Async I/O Optimization

**Connection Pooling:**
- HTTP client connection pooling for webhook reuse
- Persistent connections across notifications
- Configurable pool size limits

**Concurrent Operations:**
- TaskGroup for concurrent webhook delivery (`.claude/python-313-pro.md:91-98`)
- Parallel provider notifications reduce total latency
- Total notification time = max(provider latencies), not sum

**Timeout Tuning:**
- Aggressive timeouts prevent slow providers from blocking
- Per-provider timeout configuration
- Overall notification timeout as backstop

**Backpressure Handling:**
- Notification queue with maximum size
- Discard or coalesce notifications under extreme load
- Prevent memory exhaustion from notification backlog

---

## 19. Observability & Monitoring

### 19.1 Structured Logging

**Log Structure:**
- JSON-formatted logs for machine parsing (optional)
- Contextual fields: timestamp, level, module, function, provider, correlation_id
- Human-readable syslog format for Unraid integration
- Configurable format via configuration

**Log Levels:**

**DEBUG:**
- Disk usage samples
- Progress calculation details
- Configuration loading steps
- Provider health check results

**INFO:**
- Mover lifecycle events (started, completed)
- Notifications sent (provider, type, success)
- Threshold crossings
- Configuration changes (hot-reload)

**WARNING:**
- Provider delivery failures (with retry)
- Disk sampling errors (with retry)
- Stalled mover detection
- Configuration deprecation warnings

**ERROR:**
- All providers failed
- Configuration validation failures
- Unrecoverable errors requiring intervention

**Correlation IDs:**
- Each notification event assigned unique correlation ID
- All provider delivery attempts tagged with same ID
- Trace notification flow across logs
- Context variables for automatic correlation (`.claude/python-313-pro.md:100-111`)

### 19.2 Metrics and Health Checks

**Health Check Endpoint:**
- Optional HTTP endpoint for monitoring tools
- Reports application health, enabled providers, provider health
- Returns 200 OK if healthy, 503 Service Unavailable if unhealthy
- Lightweight: no side effects, fast response

**Metrics Export:**
- Optional Prometheus-compatible metrics endpoint
- Metrics:
  - Notifications sent (counter, labeled by provider and type)
  - Notification delivery latency (histogram, labeled by provider)
  - Provider health status (gauge, labeled by provider)
  - Disk usage sampling duration (histogram)
  - Mover monitoring duration (histogram)

**Status File:**
- Current monitoring state written to file
- JSON format for easy parsing
- Useful for dashboard integration (Grafana, custom Unraid dashboard)
- Fields: current progress, ETC, last notification time, provider status

### 19.3 Error Tracking

**Exception Logging:**
- Full stack traces for unhandled exceptions
- Context capture: mover state, progress, configuration snapshot
- Exception grouping for concurrent failures (`.claude/python-313-pro.md:70-79`)

**Error Aggregation:**
- Similar errors grouped by type and provider
- Frequency tracking for recurring issues
- Alert on error rate thresholds

**Provider Failure Tracking:**
- Per-provider failure counters
- Consecutive failure detection
- Circuit breaker status logging

---

## 20. Documentation Strategy

### 20.1 Code Documentation

**Docstrings:**
- All public functions, classes, and modules have docstrings
- Google-style or NumPy-style docstrings for consistency
- Type annotations reduce need for type documentation in docstrings
- Focus on intent, behavior, and edge cases

**Protocol Documentation:**
- Each Protocol extensively documented with:
  - Purpose and responsibility
  - Method contracts (inputs, outputs, side effects)
  - Usage examples (in docstring, no separate code examples)
  - Implementation requirements

**Module Documentation:**
- Module-level docstrings explaining purpose and organization
- Cross-references to related modules
- Architectural context for the module

### 20.2 User Documentation

**README:**
- Installation instructions (Unraid-specific)
- Quick start guide
- Configuration overview (link to detailed docs)
- Troubleshooting common issues

**Configuration Guide:**
- Detailed documentation for all configuration fields
- Examples for common scenarios (Discord only, Telegram only, both)
- Environment variable setup instructions
- Migration guide from bash script

**Provider-Specific Guides:**
- Discord setup: creating webhook, configuring colors, embed customization
- Telegram setup: creating bot, obtaining chat ID, message formatting
- Future provider guides as providers added

**Troubleshooting Guide:**
- Common issues and solutions
- Log interpretation guide
- Debugging steps for notification delivery failures
- FAQ

### 20.3 Developer Documentation

**Architecture Documentation:**
- This document serves as primary architectural reference
- Component interaction diagrams
- Data flow diagrams
- Extension guides

**Contributing Guide:**
- Development environment setup
- Code style guidelines (enforced by ruff)
- Testing requirements
- Pull request process

**Plugin Development Guide:**
- How to create new provider plugin
- NotificationProvider Protocol implementation guide
- Configuration schema definition
- Testing provider plugins
- Example provider as template

---

## 21. Architectural Decision Records (ADRs)

### 21.1 Why Plugin Architecture Over Hardcoded Providers

**Decision:** Implement notification providers as dynamically loaded plugins rather than hardcoded implementations.

**Context:**
- Bash script has hardcoded Discord and Telegram with if/else blocks
- Future providers require core code modification
- Testing difficult with hardcoded dependencies

**Consequences:**
- ✅ New providers added without modifying core code
- ✅ Providers tested in isolation
- ✅ Configuration-driven provider enablement
- ✅ Clear separation of concerns
- ❌ Slight complexity increase for simple cases
- ❌ Plugin discovery adds minimal startup overhead

**References:**
- SOLID Open/Closed Principle
- Plugin pattern for extensibility

### 21.2 Why Two-Tier YAML Configuration

**Decision:** Use two-tier YAML configuration (main app config + provider-specific configs) rather than single unified YAML.

**Context:**
- Single YAML becomes unwieldy with many providers
- Provider-specific settings pollute main configuration namespace
- Secrets management easier with separate files (different permissions)

**Consequences:**
- ✅ Clear separation: app settings vs. provider settings
- ✅ Provider configs can be version-controlled separately (or not, if secrets)
- ✅ Adding provider doesn't clutter main config
- ✅ Provider-specific validation schemas isolated
- ❌ Multiple files to manage
- ❌ Auto-creation complexity for missing provider configs

**References:**
- Configuration management best practices
- Separation of concerns principle

### 21.3 Why Pydantic for Configuration Validation

**Decision:** Use Pydantic for all configuration validation rather than manual validation or simpler libraries.

**Context:**
- Configuration errors are common source of runtime failures
- Need comprehensive validation with clear error messages
- Type safety at configuration boundaries

**Consequences:**
- ✅ Runtime validation prevents invalid configurations
- ✅ Type-safe configuration access
- ✅ Clear, actionable error messages
- ✅ IDE support for configuration editing
- ❌ Pydantic dependency (though minimal)
- ❌ Slight startup overhead for validation

**References:**
- `.claude/python-313-pro.md:504-514` (Pydantic validation at API boundaries)
- Fail-fast principle

### 21.4 Why TaskGroup Over gather/create_task

**Decision:** Use asyncio.TaskGroup for concurrent operations rather than gather() or create_task().

**Context:**
- Multiple providers need concurrent notification delivery
- Resource cleanup critical (HTTP connections, etc.)
- Error handling for multi-provider failures

**Consequences:**
- ✅ Structured concurrency with automatic cleanup
- ✅ Proper cancellation propagation
- ✅ Exception group handling for multi-provider errors
- ✅ No orphaned tasks
- ✅ True parallelism in free-threaded Python
- ❌ Python 3.11+ requirement (acceptable for Python 3.14+ target)

**References:**
- `.claude/python-313-pro.md:91-98` (TaskGroup for structured concurrency)
- Structured concurrency principles

### 21.5 Why Python 3.14+ Target

**Decision:** Target Python 3.14+ rather than maintaining compatibility with older versions.

**Context:**
- Modern type system features (PEP 695, TypeIs, type statement)
- Free-threading for performance on multi-core
- Tail-call interpreter optimizations
- Structured concurrency maturity

**Consequences:**
- ✅ Access to all modern Python features
- ✅ Best type safety capabilities
- ✅ Free-threading performance potential
- ✅ Simpler codebase (no compatibility shims)
- ❌ Requires Python 3.14 installation on Unraid (via Nerd Tools or manual)
- ❌ Smaller ecosystem initially (maturity over time)

**References:**
- `.claude/python-313-pro.md:541-546` (SPEC 0 version support policy)
- Modernization goals

---

## Conclusion

This architectural design document provides a comprehensive blueprint for converting the legacy `moverStatus.sh` bash script into a modern, modular Python 3.14+ application. The architecture emphasizes:

- **Modularity**: Complete provider isolation with plugin-based architecture
- **Type Safety**: Comprehensive type hints using modern Python 3.14+ features
- **Extensibility**: Zero-modification provider addition via plugin system
- **Maintainability**: Clear separation of concerns, SOLID principles, DRY philosophy
- **Testability**: Pure functions, Protocol-based interfaces, comprehensive test strategy
- **Performance**: Structured concurrency, async I/O, free-threading readiness
- **Security**: Defense-in-depth with secret management, input validation, dependency scanning
- **Observability**: Structured logging, health checks, metrics export

The two-tier YAML configuration system (main app config + provider-specific configs) provides clear separation while enabling seamless provider extension. The plugin architecture ensures that future providers (Slack, email, PagerDuty, etc.) can be added without touching core application code.

By strictly adhering to the Python 3.14+ best practices outlined in [`.claude/python-313-pro.md`](.claude/python-313-pro.md), this architecture delivers a production-ready, maintainable, and performant monitoring solution for the Unraid Mover process.

**Next Steps:**
1. Review and approve this architectural design
2. Begin implementation following the module structure outlined
3. Develop core monitoring and calculation modules first (no provider dependencies)
4. Implement plugin system and provider plugins
5. Create comprehensive test suite alongside implementation
6. Document configuration and usage
7. Perform migration testing with parallel deployment
8. Deploy to production with rollback capability

This architecture serves as the foundation for a scalable, maintainable, and extensible Mover monitoring solution that will serve the project for years to come.
