# Requirements Document

## Introduction

This document specifies the requirements for converting the legacy moverStatus.sh bash script into a modern, modular Python 3.14+ application. The conversion transforms a monolithic bash implementation with hardcoded notification providers into a well-structured, type-safe Python application following industry best practices with a plugin-based architecture.

## Glossary

- **Mover Process**: The Unraid system process that moves data from cache drives to array drives
- **Application Core**: The main monitoring and orchestration logic independent of notification providers
- **Provider Plugin**: A self-contained module implementing notification delivery for a specific platform (Discord, Telegram, etc.)
- **Plugin System**: The infrastructure for discovering, loading, and managing provider plugins
- **Notification Dispatcher**: Component responsible for routing notifications to all enabled provider plugins
- **Configuration Validator**: Component that validates YAML configuration files using Pydantic schemas
- **Monitoring Engine**: Component that detects and tracks the mover process lifecycle
- **Progress Calculator**: Component that calculates completion percentage and estimated time of completion
- **HTTP Client**: Abstraction for delivering webhook notifications with timeout and retry logic
- **Message Formatter**: Component that transforms generic notification data into provider-specific formats
- **PID File**: Process identifier file at /var/run/mover.pid used to detect mover execution
- **TaskGroup**: Python asyncio construct for structured concurrent task execution
- **Protocol**: Python structural subtyping mechanism for defining interfaces without inheritance

## Requirements

### Requirement 1

**User Story:** As a system administrator, I want the application to monitor the Unraid mover process lifecycle, so that I can track when data movement begins and ends

#### Acceptance Criteria

1. WHEN the PID file at /var/run/mover.pid is created, THE Monitoring Engine SHALL detect the mover process start within 5 seconds
2. WHEN the mover process starts, THE Monitoring Engine SHALL validate process existence in the system process table
3. WHEN the mover process terminates, THE Monitoring Engine SHALL detect the termination within 5 seconds
4. WHEN the mover process is detected as started, THE Application Core SHALL capture a baseline disk usage snapshot
5. WHILE the mover process is running, THE Monitoring Engine SHALL maintain process state tracking

### Requirement 2

**User Story:** As a system administrator, I want to receive progress notifications at configurable thresholds, so that I can monitor data movement without constantly checking the system

#### Acceptance Criteria

1. WHEN disk usage changes indicate progress crossing a configured threshold, THE Application Core SHALL trigger a notification event
2. THE Application Core SHALL calculate progress percentage as (baseline minus current) divided by baseline times 100
3. THE Application Core SHALL support configurable threshold percentages between 0 and 100
4. WHEN a threshold is crossed, THE Notification Dispatcher SHALL deliver notifications to all enabled provider plugins concurrently
5. THE Application Core SHALL calculate estimated time of completion based on data movement rate

### Requirement 3

**User Story:** As a system administrator, I want to add new notification providers without modifying core application code, so that I can integrate with additional platforms as needed

#### Acceptance Criteria

1. THE Plugin System SHALL discover provider plugins from a designated plugins directory at application startup
2. THE Plugin System SHALL load only provider plugins that are enabled in the main configuration
3. WHEN a new provider plugin is added to the plugins directory and enabled in configuration, THE Plugin System SHALL load and register the provider without requiring core code changes
4. THE Plugin System SHALL validate each provider plugin implements the NotificationProvider Protocol
5. IF a provider plugin fails to load, THEN THE Plugin System SHALL log the failure and continue loading remaining providers

### Requirement 4

**User Story:** As a system administrator, I want configuration validation at startup, so that I can identify and fix configuration errors before the application runs

#### Acceptance Criteria

1. WHEN the application starts, THE Configuration Validator SHALL load and validate the main YAML configuration file
2. WHEN the application starts, THE Configuration Validator SHALL load and validate provider-specific YAML files for each enabled provider
3. IF any configuration file fails validation, THEN THE Configuration Validator SHALL halt application startup and display actionable error messages
4. THE Configuration Validator SHALL resolve environment variable references for secrets at startup
5. IF a required environment variable is missing, THEN THE Configuration Validator SHALL halt startup with a clear error message indicating which variable is required

### Requirement 5

**User Story:** As a system administrator, I want provider failures to be isolated, so that one provider's issues don't prevent other providers from receiving notifications

#### Acceptance Criteria

1. WHEN a provider plugin fails to deliver a notification, THE Notification Dispatcher SHALL log the failure and continue dispatching to remaining providers
2. THE Notification Dispatcher SHALL execute provider notification deliveries concurrently using TaskGroup
3. IF multiple providers fail simultaneously, THEN THE Application Core SHALL handle the exception group and log each failure separately
4. WHEN a provider experiences consecutive failures exceeding a threshold, THE Plugin System SHALL mark the provider as unhealthy
5. THE Application Core SHALL continue monitoring and notification operations with healthy providers when one or more providers are unhealthy

### Requirement 6

**User Story:** As a system administrator, I want the option to use environment variables for secrets, so that I can choose between direct YAML configuration or environment-based secret management

#### Acceptance Criteria

1. THE Configuration Validator SHALL support direct specification of secrets in YAML files as the default configuration method
2. THE Configuration Validator SHALL optionally support environment variable references in YAML files using ${VARIABLE_NAME} syntax
3. WHEN environment variable references are used, THE Configuration Validator SHALL resolve them at application startup
4. THE Application Core SHALL NOT log or expose secrets in error messages or diagnostic output regardless of configuration method
5. WHEN an authentication failure occurs, THE Application Core SHALL log the failure without including the secret value

### Requirement 7

**User Story:** As a system administrator, I want comprehensive type safety throughout the application, so that type errors are caught during development rather than at runtime

#### Acceptance Criteria

1. THE Application Core SHALL use Python 3.14+ PEP 695 generic syntax for all generic type definitions
2. THE Application Core SHALL define all component interfaces using Protocol-based structural subtyping
3. THE Application Core SHALL use TypedDict with ReadOnly fields for immutable configuration sections
4. THE Application Core SHALL pass type checking with basedpyright in recommended mode with failOnWarnings enabled
5. THE Application Core SHALL use explicit rule-scoped type ignore comments when type ignores are necessary

### Requirement 8

**User Story:** As a system administrator, I want the application to handle concurrent operations efficiently, so that notification delivery is fast and doesn't block monitoring

#### Acceptance Criteria

1. THE Notification Dispatcher SHALL use asyncio TaskGroup for concurrent provider notification delivery
2. THE Application Core SHALL offload CPU-bound disk usage calculations to thread pool using asyncio.to_thread
3. THE Application Core SHALL enforce timeout limits on all HTTP webhook requests using asyncio.timeout
4. WHEN all provider notifications complete or fail, THE Notification Dispatcher SHALL proceed to next monitoring cycle
5. THE Application Core SHALL use async context managers for HTTP client resource management

### Requirement 9

**User Story:** As a developer, I want each provider plugin to be completely self-contained, so that providers can be developed and tested independently

#### Acceptance Criteria

1. THE Plugin System SHALL enforce that each provider plugin contains its own API client implementation
2. THE Plugin System SHALL enforce that each provider plugin contains its own message formatter implementation
3. THE Plugin System SHALL enforce that each provider plugin defines its own configuration schema using Pydantic
4. THE Plugin System SHALL ensure provider plugins have zero dependencies on other provider plugins
5. THE Plugin System SHALL ensure provider plugins can be tested in isolation without loading other providers

### Requirement 10

**User Story:** As a system administrator, I want the application to maintain feature parity with the bash script, so that the migration doesn't lose existing functionality

#### Acceptance Criteria

1. THE Application Core SHALL detect mover process start using PID file watching identical to the bash script
2. THE Application Core SHALL calculate progress percentage using the same algorithm as the bash script
3. THE Application Core SHALL calculate estimated time of completion using the same algorithm as the bash script
4. THE Application Core SHALL send notifications at the same threshold percentages as the bash script by default
5. THE Application Core SHALL support the same exclusion paths configuration as the bash script

### Requirement 11

**User Story:** As a developer, I want comprehensive test coverage with multiple testing strategies, so that I can confidently refactor and extend the application

#### Acceptance Criteria

1. THE Application Core SHALL include unit tests for all pure calculation functions using pytest
2. THE Application Core SHALL include property-based tests for calculation invariants using Hypothesis
3. THE Application Core SHALL include integration tests for plugin loading and notification flow
4. THE Application Core SHALL include parametrized tests for edge cases in progress calculation
5. THE Application Core SHALL achieve minimum 80% code coverage measured by pytest-cov

### Requirement 12

**User Story:** As a system administrator, I want structured logging with contextual information, so that I can troubleshoot issues effectively

#### Acceptance Criteria

1. THE Application Core SHALL log all mover lifecycle events at INFO level
2. THE Application Core SHALL log all notification delivery attempts with provider name and outcome
3. THE Application Core SHALL use correlation IDs to track notifications across multiple providers
4. THE Application Core SHALL integrate with Unraid syslog for operational transparency
5. THE Application Core SHALL log errors with full context without exposing secrets

### Requirement 13

**User Story:** As a system administrator, I want the application to retry transient failures automatically, so that temporary network issues don't cause missed notifications

#### Acceptance Criteria

1. WHEN a provider webhook request times out, THE HTTP Client SHALL retry with exponential backoff
2. WHEN a provider API returns a 5xx server error, THE HTTP Client SHALL retry with exponential backoff
3. THE HTTP Client SHALL implement a maximum of 5 retry attempts with configurable maximum interval
4. THE HTTP Client SHALL add random jitter to backoff intervals to prevent thundering herd
5. WHEN a provider returns a 4xx client error (except 429), THE HTTP Client SHALL NOT retry and SHALL mark the request as permanently failed

### Requirement 14

**User Story:** As a developer, I want high-level abstraction and modularity throughout the codebase, so that components are maintainable, testable, and extensible without tight coupling

#### Acceptance Criteria

1. THE Application Core SHALL separate monitoring logic, calculation logic, and notification dispatch into independent modules with clear interfaces
2. THE Application Core SHALL define Protocol-based abstractions for HTTP clients, message formatters, and configuration loaders
3. THE Application Core SHALL ensure no module has direct dependencies on provider-specific implementations
4. THE Application Core SHALL implement pure functions for all calculation logic to enable isolated testing
5. THE Application Core SHALL use dependency injection for all component interactions to enable easy mocking and testing

### Requirement 15

**User Story:** As a developer, I want utility functions and common infrastructure to be reusable across all components, so that code duplication is minimized and consistency is maintained

#### Acceptance Criteria

1. THE Application Core SHALL provide shared utility modules for disk usage calculation, time formatting, and data size formatting
2. THE Application Core SHALL provide a shared HTTP client abstraction that all provider plugins use via Protocol interface
3. THE Application Core SHALL provide a shared message template system that all providers use for placeholder replacement
4. THE Application Core SHALL ensure utility functions are pure and stateless to enable reuse without side effects
5. THE Application Core SHALL ensure no provider-specific logic exists in shared utility modules

### Requirement 16

**User Story:** As a developer, I want the application to use modern Python tooling, so that development is fast and maintainable

#### Acceptance Criteria

1. THE Application Core SHALL use uv for package management and dependency resolution
2. THE Application Core SHALL use ruff for linting and code formatting
3. THE Application Core SHALL use basedpyright for comprehensive type checking
4. THE Application Core SHALL use pytest with Hypothesis for testing
5. THE Application Core SHALL use Nox for multi-environment testing across Python versions
