# Implementation Plan

This implementation plan breaks down the bash-to-Python conversion into discrete, manageable coding tasks. Each task builds incrementally on previous tasks, with all code integrated into the application by the end.

## Task List

- [x] 1. Set up project structure and tooling
  - Create src/ layout with mover_status package
  - Configure pyproject.toml with PEP 621 metadata and uv_build backend
  - Set up ruff for linting/formatting with Python 3.14 target
  - Configure basedpyright for type checking in recommended mode with failOnWarnings
  - Set up pytest with coverage reporting
  - Create noxfile.py for multi-environment testing
  - _Requirements: 17.1, 17.2, 17.3, 17.4, 17.5_

- [x] 2. Implement core type definitions and protocols
  - [x] 2.1 Create Protocol definitions for component interfaces
    - Define NotificationProvider Protocol with send_notification, validate_config, health_check methods
    - Define MessageFormatter Protocol with format_message and format_time methods
    - Define HTTPClient Protocol with post and post_with_retry methods
    - Use small, composable Protocols (1-3 methods each)
    - Use keyword-only arguments for optional parameters
    - _Requirements: 7.2, 15.2_
  
  - [x] 2.2 Create data models with dataclasses
    - Implement DiskSample dataclass with slots=True for memory efficiency
    - Implement ProgressData dataclass with slots=True
    - Implement NotificationData dataclass
    - Implement NotificationResult dataclass
    - Implement HealthStatus dataclass
    - Use frozen=True for immutable data structures where appropriate
    - _Requirements: 7.1, 15.1_
  
  - [x] 2.3 Create type aliases using modern syntax
    - Define type aliases using `type` statement (PEP 695)
    - Create ProviderConfig union type for all provider configs
    - Create NotificationEvent type alias
    - Use built-in generic collections (list, dict, Mapping)
    - _Requirements: 7.1_

- [ ] 3. Implement utility modules
  - [x] 3.1 Create formatting utilities
    - Implement format_size function for bytes to human-readable conversion (GB/TB/MB/KB)
    - Implement format_duration function for time formatting
    - Implement format_rate function for data rate formatting
    - Use pure functions with comprehensive type annotations
    - _Requirements: 16.1, 16.4_
  
  - [x] 3.2 Implement HTTP client abstraction
    - Create HTTPClient implementation using aiohttp
    - Implement async post method with timeout support using asyncio.timeout
    - Implement post_with_retry with exponential backoff and jitter
    - Add circuit breaker pattern for persistent failures
    - Use async context managers for resource management
    - _Requirements: 8.3, 14.1, 14.2, 14.3, 14.4, 16.2_
  
  - [x] 3.3 Create message template system
    - Implement template loading from configuration
    - Implement placeholder identification and validation
    - Implement safe placeholder replacement
    - Validate templates at load time
    - _Requirements: 16.3_
  
  - [x] 3.4 Set up structured logging infrastructure
    - Configure Python logging to integrate with Unraid syslog
    - Implement correlation ID tracking using ContextVar
    - Create log formatters for structured output
    - Set up log level configuration
    - _Requirements: 13.1, 13.2, 13.3_

- [ ] 4. Implement configuration system
  - [x] 4.1 Create Pydantic models for main configuration
    - Define MainConfig BaseModel with monitoring, notifications, providers, application sections
    - Add field validators for path existence, percentage ranges, positive intervals
    - Use ReadOnly TypedDict fields for immutable runtime config sections
    - Implement default values for optional settings
    - _Requirements: 4.1, 4.2, 4.3, 7.4_
  
  - [x] 4.2 Implement environment variable resolution
    - Create function to parse ${VARIABLE_NAME} syntax in YAML values
    - Implement environment variable resolution at startup
    - Add validation for missing required environment variables
    - Ensure no secret logging in error messages
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_
  
  - [x] 4.3 Create configuration loader
    - Implement main YAML loading and validation
    - Implement provider-specific YAML loading coordination
    - Add fail-fast validation with actionable error messages
    - Create configuration error reporting with field-level diagnostics
    - _Requirements: 4.1, 4.2, 4.3, 4.4_

- [ ] 5. Implement progress calculation engine
  - [x] 5.1 Create pure calculation functions
    - Implement calculate_progress function with edge case handling (zero baseline, negative deltas)
    - Implement calculate_etc function with rate validation
    - Implement calculate_rate function with moving average
    - Implement calculate_remaining function
    - Use immutable dataclasses for inputs and outputs
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 15.4_
  
  - [x] 5.2 Implement threshold evaluation logic
    - Create function to evaluate if notification threshold crossed
    - Track previously notified thresholds to avoid duplicates
    - Support configurable threshold percentages
    - _Requirements: 2.1, 2.2, 2.3_
  
  - [x] 5.3 Write property-based tests for calculation invariants
    - Use Hypothesis to test progress percentage always between 0-100
    - Test remaining data always non-negative
    - Test ETC always in future
    - Test rate calculation never produces NaN or Infinity
    - Test reversibility of size formatting
    - _Requirements: 12.1, 12.2_

- [x] 6. Implement disk usage tracker
  - [x] 6.1 Create disk usage calculation functions
    - Implement synchronous disk traversal with exclusion path filtering
    - Implement baseline capture function
    - Implement current usage sampling function
    - Add error handling for inaccessible paths
    - _Requirements: 1.4, 2.1_
  
  - [x] 6.2 Integrate with async coordination
    - Use asyncio.to_thread to offload CPU-bound disk calculations
    - Implement caching mechanism to prevent excessive disk I/O
    - Add configurable sampling intervals
    - Preserve context variables across thread boundary
    - _Requirements: 8.2, 8.3_
  
  - [x] 6.3 Write unit tests for disk usage calculations
    - Test exclusion path filtering
    - Test baseline and delta calculations
    - Test error handling for inaccessible paths
    - Use mock filesystem for deterministic tests
    - _Requirements: 12.1_

- [x] 7. Implement monitoring engine
  - [x] 7.1 Create PID file watcher
    - Implement async file watching for /var/run/mover.pid
    - Create async generator yielding PID file events
    - Add polling with configurable interval
    - Handle file creation, modification, deletion events
    - _Requirements: 1.1, 1.2, 1.3_
  
  - [x] 7.2 Implement process validation
    - Create function to validate process existence in process table
    - Handle process variants (mover.old vs. age_mover)
    - Add timeout for process detection
    - _Requirements: 1.1, 1.2, 1.5_
  
  - [x] 7.3 Create lifecycle state machine
    - Implement state machine for mover lifecycle (waiting → started → monitoring → completed)
    - Add state transition handlers
    - Integrate with syslog for operational events
    - Handle edge cases (mover never starts, unexpected termination)
    - _Requirements: 1.1, 1.2, 1.3, 1.5, 13.1_
  
  - [x] 7.4 Write unit tests for monitoring engine
    - Test PID file watching with mock filesystem
    - Test process validation with mock process table
    - Test state machine transitions
    - Test edge case handling
    - _Requirements: 12.1_


- [ ] 8. Implement plugin system
  - [x] 8.1 Create plugin discovery mechanism
    - Implement convention-based plugin discovery from src/plugins/ directory
    - Create plugin metadata registration system
    - Implement automatic scanning at startup
    - Add conditional loading (only enabled providers)
    - _Requirements: 3.1, 3.2, 3.3, 3.4_
  
  - [x] 8.2 Create plugin registry
    - Implement ProviderRegistry class using PEP 695 generic syntax
    - Add provider registration and retrieval methods
    - Implement health status tracking per provider
    - Add methods to get healthy providers only
    - _Requirements: 3.1, 3.2, 5.1, 5.2, 5.3, 5.4_
  
  - [x] 8.3 Implement plugin loader
    - Create dynamic plugin loading with validation
    - Implement lazy initialization (load only when enabled)
    - Add error handling for loading failures
    - Validate provider implements NotificationProvider Protocol
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_
  
  - [x] 8.4 Write integration tests for plugin system
    - Test plugin discovery from plugins directory
    - Test conditional loading based on configuration
    - Test provider registration and retrieval
    - Test health status tracking
    - _Requirements: 12.3_

- [ ] 9. Implement Discord provider plugin
  - [x] 9.1 Create Discord configuration schema
    - Define DiscordConfig Pydantic model
    - Add webhook URL validation (format, HTTPS only)
    - Add optional fields (username, embed_color)
    - Implement field validators
    - _Requirements: 3.5, 4.1, 4.2, 4.3, 4.4, 9.1, 9.2, 9.3, 9.4_
  
  - [x] 9.2 Implement Discord message formatter
    - Create Discord embed builder
    - Implement placeholder replacement for Discord format
    - Convert ETC to Discord timestamp format (Unix timestamp with relative formatting)
    - Add color coding based on progress percentage
    - _Requirements: 9.1, 9.2, 9.3, 9.4_
  
  - [x] 9.3 Create Discord API client
    - Implement webhook POST to Discord API
    - Add Discord-specific error handling
    - Implement rate limiting logic
    - Parse Discord error responses
    - _Requirements: 9.1, 9.2, 9.3, 9.4_
  
  - [x] 9.4 Implement Discord NotificationProvider
    - Create DiscordProvider class implementing NotificationProvider Protocol
    - Implement send_notification method using Discord client
    - Implement validate_config method
    - Implement health_check method
    - Wire together formatter, client, and configuration
    - _Requirements: 3.5, 9.1, 9.2, 9.3, 9.4_
  
  - [x] 9.5 Write unit tests for Discord provider
    - Test embed formatting with mock data
    - Test webhook delivery with mock HTTP client
    - Test configuration validation
    - Test error handling
    - _Requirements: 12.1_

- [ ] 10. Implement Telegram provider plugin
  - [x] 10.1 Create Telegram configuration schema
    - Define TelegramConfig Pydantic model
    - Add bot token validation
    - Add chat ID validation
    - Add optional fields (parse_mode, message_threading)
    - _Requirements: 3.5, 4.1, 4.2, 4.3, 4.4, 9.1, 9.2, 9.3, 9.4_
  
  - [x] 10.2 Implement Telegram message formatter
    - Create HTML message builder
    - Implement placeholder replacement for Telegram format
    - Convert ETC to human-readable datetime string
    - Add HTML entity encoding
    - _Requirements: 9.1, 9.2, 9.3, 9.4_
  
  - [x] 10.3 Create Telegram API client
    - Implement sendMessage POST to Telegram Bot API
    - Add Telegram-specific error handling
    - Parse Telegram error responses (invalid chat_id, bot blocked)
    - _Requirements: 9.1, 9.2, 9.3, 9.4_
  
  - [x] 10.4 Implement Telegram NotificationProvider
    - Create TelegramProvider class implementing NotificationProvider Protocol
    - Implement send_notification method using Telegram client
    - Implement validate_config method
    - Implement health_check method
    - Wire together formatter, client, and configuration
    - _Requirements: 3.5, 9.1, 9.2, 9.3, 9.4_
  
  - [x] 10.5 Write unit tests for Telegram provider
    - Test HTML formatting with mock data
    - Test message delivery with mock HTTP client
    - Test configuration validation
    - Test error handling
    - _Requirements: 12.1_


- [ ] 11. Implement notification dispatcher
  - [ ] 11.1 Create notification dispatcher core
    - Implement NotificationDispatcher class
    - Create dispatch_notification method using TaskGroup for concurrent delivery
    - Implement per-provider timeout using asyncio.timeout
    - Add correlation ID generation and tracking using ContextVar
    - _Requirements: 2.4, 5.1, 5.2, 5.3, 5.4, 5.5, 8.1, 8.2_
  
  - [ ] 11.2 Implement exception group handling
    - Use except* for multi-provider error handling
    - Handle TimeoutError separately from other exceptions
    - Log each provider failure with context
    - Ensure failed providers don't block successful deliveries
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_
  
  - [ ] 11.3 Integrate with plugin registry
    - Retrieve healthy providers from registry
    - Mark providers for retry on transient failures
    - Mark providers unhealthy on permanent failures
    - _Requirements: 5.1, 5.2, 5.3, 5.4_
  
  - [ ] 11.4 Write integration tests for notification dispatch
    - Test concurrent delivery to multiple providers
    - Test exception group handling with mixed success/failure
    - Test timeout enforcement
    - Test correlation ID tracking
    - _Requirements: 12.3_

- [ ] 12. Implement application orchestrator
  - [ ] 12.1 Create orchestrator core
    - Implement Orchestrator class coordinating all components
    - Initialize monitoring engine, progress calculator, disk tracker, plugin system
    - Create main monitoring loop using TaskGroup
    - Implement graceful shutdown handling
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 2.1, 2.2, 2.3, 2.4, 2.5, 8.1_
  
  - [ ] 12.2 Integrate monitoring and progress tracking
    - Connect monitoring engine events to progress calculator
    - Trigger baseline capture on mover start
    - Schedule periodic disk usage sampling
    - Evaluate thresholds and trigger notifications
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 2.1, 2.2, 2.3, 2.4, 2.5_
  
  - [ ] 12.3 Implement notification event handling
    - Create notification events for mover started, progress, completed
    - Populate notification data with current progress metrics
    - Dispatch to notification dispatcher
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_
  
  - [ ] 12.4 Write integration tests for orchestrator
    - Test full monitoring cycle (waiting → started → monitoring → completed)
    - Test notification triggering at thresholds
    - Test graceful shutdown
    - Use mock components for isolation
    - _Requirements: 12.3_

- [ ] 13. Create application entry point and CLI
  - [ ] 13.1 Implement __main__.py entry point
    - Create main() function as application entry point
    - Parse command-line arguments (config path, dry-run mode, log level)
    - Initialize configuration loader
    - Create and start orchestrator
    - Handle KeyboardInterrupt for graceful shutdown
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 4.1, 4.2, 4.3, 4.4_
  
  - [ ] 13.2 Add dry-run mode support
    - Implement dry-run flag that logs notifications without sending
    - Mock HTTP client in dry-run mode
    - Log all notification data for verification
    - _Requirements: 10.1_
  
  - [ ] 13.3 Create configuration templates
    - Generate mover-status.yaml.template with commented examples
    - Generate discord.yaml.template with commented examples
    - Generate telegram.yaml.template with commented examples
    - Include documentation for all configuration fields
    - _Requirements: 4.1, 4.2, 4.3, 4.4_

- [ ] 14. Implement configuration migration tool
  - [ ] 14.1 Create bash configuration parser
    - Implement parser for bash script variables
    - Extract USE_DISCORD, DISCORD_WEBHOOK_URL, etc.
    - Extract notification message templates
    - Extract exclusion paths
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5_
  
  - [ ] 14.2 Implement YAML generation
    - Transform bash variables to main YAML structure
    - Generate provider-specific YAML files for enabled providers
    - Transform message templates to new template format
    - Create backup of original bash configuration
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5_
  
  - [ ] 14.3 Add migration validation
    - Validate generated YAML against schemas
    - Verify all required fields present
    - Generate migration report with any manual actions needed
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5_
  
  - [ ] 14.4 Create migration CLI command
    - Implement `python -m mover_status.migrate` command
    - Add --from and --to arguments for paths
    - Display migration progress and results
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5_


- [ ] 15. Implement security hardening
  - [ ] 15.1 Add input validation at API boundaries
    - Validate all configuration fields with Pydantic
    - Validate webhook URLs (HTTPS only, format validation)
    - Validate file paths (existence, accessibility)
    - Validate percentage ranges and positive intervals
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_
  
  - [ ] 15.2 Implement secret protection
    - Ensure no secrets logged in error messages
    - Ensure no secrets in diagnostic output
    - Validate environment variable resolution
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_
  
  - [ ] 15.3 Set up dependency scanning
    - Configure pip-audit for PyPI advisory scanning
    - Configure bandit for code security analysis
    - Add pre-commit hooks for security scanning
    - _Requirements: 17.1, 17.2, 17.3, 17.4, 17.5_
  
  - [ ] 15.4 Implement hash verification for dependencies
    - Generate requirements.txt with hashes using uv export
    - Document hash verification installation process
    - _Requirements: 17.1, 17.2, 17.3, 17.4, 17.5_

- [ ] 16. Create comprehensive documentation
  - [ ] 16.1 Write README.md
    - Add project overview and features
    - Add installation instructions for Unraid
    - Add quick start guide
    - Add configuration overview with links
    - Add troubleshooting section
    - _Requirements: 10.1, 10.2, 10.3_
  
  - [ ] 16.2 Create configuration guide
    - Document all main configuration fields with examples
    - Document provider-specific configuration
    - Document environment variable setup
    - Add common configuration scenarios
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 6.1, 6.2, 6.3, 6.4, 6.5_
  
  - [ ] 16.3 Write provider setup guides
    - Create Discord setup guide (webhook creation, configuration)
    - Create Telegram setup guide (bot creation, chat ID retrieval)
    - Document message formatting options per provider
    - _Requirements: 9.1, 9.2, 9.3, 9.4_
  
  - [ ] 16.4 Create migration guide
    - Document migration process from bash script
    - Provide step-by-step instructions
    - Include configuration field mapping table
    - Add troubleshooting for common migration issues
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5_
  
  - [ ] 16.5 Generate API documentation
    - Add comprehensive docstrings to all public functions and classes
    - Use Google-style or NumPy-style docstrings
    - Document Protocol interfaces with usage examples
    - _Requirements: 15.1, 15.2, 15.3, 15.4, 15.5_

- [ ] 17. Set up CI/CD pipeline
  - [ ] 17.1 Create GitHub Actions workflow
    - Set up workflow for pull requests and main branch
    - Add fast checks (ruff linting and formatting)
    - Add comprehensive checks (basedpyright type checking)
    - Add test suite with coverage reporting
    - Add security scanning (pip-audit, bandit)
    - _Requirements: 17.1, 17.2, 17.3, 17.4, 17.5_
  
  - [ ] 17.2 Configure multi-environment testing
    - Test on Python 3.14
    - Test on multiple platforms (Linux, macOS)
    - Use matrix strategy for combinations
    - _Requirements: 17.1, 17.2, 17.3, 17.4, 17.5_
  
  - [ ] 17.3 Add release automation
    - Create workflow for release tags
    - Build package with uv build
    - Generate requirements with hash verification
    - Create GitHub release with artifacts
    - _Requirements: 17.1, 17.2, 17.3, 17.4, 17.5_

- [ ] 18. Perform feature parity validation
  - [ ] 18.1 Create feature parity checklist
    - Verify mover process detection matches bash script
    - Verify progress calculation matches bash script
    - Verify ETC calculation matches bash script
    - Verify notification timing matches bash script
    - Verify message content matches bash script
    - _Requirements: 10.1, 10.2, 10.3_
  
  - [ ] 18.2 Perform parallel deployment testing
    - Run Python application alongside bash script
    - Compare notification outputs for consistency
    - Identify and document any behavioral differences
    - _Requirements: 10.1, 10.2, 10.3_
  
  - [ ] 18.3 Write end-to-end integration tests
    - Test full mover cycle with mock mover process
    - Test notification delivery to all providers
    - Test configuration loading and validation
    - Test error handling and recovery
    - _Requirements: 12.3_

## Implementation Notes

### Task Execution Order

Tasks should be executed in the order listed, as each task builds on previous tasks:
1. Project structure and tooling (Task 1)
2. Core types and protocols (Task 2)
3. Utility modules (Task 3)
4. Configuration system (Task 4)
5. Core calculation and monitoring logic (Tasks 5-7)
6. Plugin system and providers (Tasks 8-10)
7. Notification dispatch and orchestration (Tasks 11-12)
8. Application entry point (Task 13)
9. Migration tool (Task 14)
10. Security hardening (Task 15)
11. Documentation (Task 16)
12. CI/CD and validation (Tasks 17-18)

### Comprehensive Approach

All tasks are required for a production-ready implementation. This includes comprehensive testing (unit, integration, property-based, end-to-end) and complete documentation. This approach ensures high quality and maintainability from the start.

### Testing Strategy

- Unit tests should be written alongside implementation for immediate feedback
- Integration tests should be written after multiple components are complete
- Property-based tests validate calculation invariants
- End-to-end tests validate full system behavior

### Type Checking

All code must pass basedpyright type checking in recommended mode with failOnWarnings enabled. Use explicit rule-scoped type ignore comments (e.g., `# pyright: ignore[reportUnknownVariableType]`) when necessary, never bare `# type: ignore`.

### Code Quality

All code must pass ruff linting and formatting checks. Use `ruff check . --fix` and `ruff format .` before committing.
