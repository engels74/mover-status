# MoverStatus Python Project Review Checklist

**Project Goals:**
- Ensure correct imports and dependency order
- Verify shared types usage across codebase
- Maintain consistency and type safety
- Follow DRY principles through careful cross-file analysis
  - Identify opportunities for code reuse across files
  - Ensure shared functionality is properly centralized
  - Verify files are efficiently using each other's capabilities
  - Balance code reuse with maintaining clear separation of concerns
  - For any changes:
    - Check existing usage in other files first
    - Document any breaking changes
    - Update review checklist with required follow-up changes
    - Consider impact on dependent files
- Properly structure configuration validation

**Breaking Changes & Follow-ups:**
1. From config/constants.py:
   - Changed constant access patterns - now requires class prefix
   - JsonDict type has explicit nesting limits
   - Error/success messages moved into classes
   - Changed constant names for consistency

2. From config/settings.py:
   - Settings structure now uses nested models
   - Changed environment variable format (using double underscores)
   - Excluded paths now uses Set instead of List
   - All path settings now return resolved Path objects

3. From config/providers/base.py:
   - Changed tags from List to Set
   - Updated to use Pydantic v2 ConfigDict
   - Made RateLimitSettings and ApiSettings immutable
   - Changed model_json_schema implementation
   - Modified header validation behavior

4. From notifications/base.py:
   - Added NotificationState class for state tracking
   - Changed error classes to include more context
   - Modified send_notification to include level parameter
   - Added automatic provider disabling after repeated errors
   - Changed rate limiting to use exponential backoff
   - Added thread-safe state management

5. From config/providers/discord/schemas.py:
   - Added new DiscordSchemaError exception class with field information
   - Changed embed length calculation to account for newlines
   - Modified validation logic to be stricter about whitespace
   - Added URL length validation for icon URLs
   - Made domain sets immutable and more efficient
   - Added new calculate_length() method to schema classes
   - Changed error message format to include field context

6. From config/providers/discord/settings.py:
   - Added new DiscordSettingsError exception class with setting context
   - Made domain sets immutable using frozenset and Final
   - Added URL length validation for all URLs
   - Added stricter thread name validation
   - Added image format validation for avatar URLs
   - Changed error message format to include setting context
   - Added validation for printable characters in thread names

7. From notifications/providers/discord/provider.py:
   - Added configurable request timeout with validation
   - Enhanced webhook URL validation using shared types
   - Added proper type hints for all parameters
   - Improved error handling and messages
   - Added validation in constructor
   - Fixed code style and import organization

8. From notifications/providers/discord/templates.py:
   - Embed creation now strictly validates against Discord API limits
   - All template functions now require explicit type annotations
   - Forum support added to webhook payloads
   - Progress embeds now use dynamic color based on completion percentage
   - Error embeds require non-empty error message

9. From config/providers/telegram/types.py:
   - Added new shared type imports from `shared.providers.telegram`
   - Introduced `MessagePriority` and `BotPermissions` enums
   - Added TypedDict classes for request/response structures
   - Added validation for chat ID formats
   - Added progress keyboard creation with API limits
   - Changed rate limiting configuration to use API constants
   - Added validation for message entities and content
   - Improved type safety with Union and Optional types

10. From config/providers/telegram/schemas.py:
    - Added Pydantic models for configuration validation
    - Introduced validation for message content and entities
    - Added inline keyboard markup validation
    - Added bot token format validation
    - Added HTTPS enforcement for API base URL
    - Added rate limiting and retry configuration
    - Changed error message format to use centralized messages
    - Added validation for chat ID formats

11. From config/providers/telegram/settings.py:
    - Added TelegramSettings class extending BaseProviderSettings
    - Added validation for bot tokens and chat IDs
    - Added HTTPS enforcement for API URLs
    - Added rate limiting configuration using API constants
    - Changed error messages to use centralized format
    - Added field constraints directly in Field definitions
    - Added proper type hints and docstrings
    - Updated example configuration with constants

12. From notifications/providers/telegram/types.py:
    - Added NotificationState for state tracking
    - Added request/response type definitions
    - Added improved message templates
    - Added validation for progress keyboard
    - Added truncate option to message length validation
    - Changed error messages to use centralized format
    - Improved type hints and docstrings
    - Removed duplicate types in favor of shared ones

13. From notifications/providers/telegram/provider.py:
    - Added NotificationState for provider status tracking
    - Changed to use exponential backoff for retries
    - Added proper error context and state management
    - Added automatic provider disabling after MAX_CONSECUTIVE_ERRORS
    - Changed tags from List to Set
    - Added thread-safe state management
    - Added new error handling with context
    - Split complex methods into smaller ones
    - Added proper type hints and annotations
    - Added message type support
    - Added automatic message editing for progress updates
    - Added priority handling for different message types
    - Added proper cleanup in finally blocks
    - Added better logging with structured context
    - Added proper parameter validation
    - Added proper session management
    - Changed error messages to use centralized format
    - Added exponential backoff for rate limiting
    - Added state tracking for rate limits and errors
    - Added proper docstrings with type information

14. From notifications/providers/telegram/templates.py:
    - Added default message templates with emojis and formatting
    - Added support for HTML and Markdown parsing modes
    - Added message length validation using shared types
    - Added proper escaping for HTML and Markdown
    - Added support for inline keyboards and progress bars
    - Added priority handling for different message types
    - Added support for optional debug information and statistics
    - Added HTML entity extraction for text formatting
    - Added proper type hints and docstrings
    - Added input validation for all message types
    - Added support for warning and status messages
    - Added proper error messages with context
    - Added support for custom message templates
    - Added proper message structure validation
    - Added support for message editing and updates
    - Added proper handling of UTF-16 encoding
    - Added support for rich text formatting
    - Added proper handling of API limits
    - Added support for interactive elements
    - Added proper documentation with examples

15. From utils/formatters.py:
    - Added ProgressStyle, SizeUnit, and TimeFormat enums
    - Added support for binary and decimal size units
    - Added multiple progress bar styles (ASCII, Unicode, blocks)
    - Added color support for progress bars
    - Added multiple time format options
    - Added locale support for timestamps
    - Added template validation against schemas
    - Added proper error messages and validation
    - Added comprehensive docstrings and examples
    - Added proper type hints and annotations
    - Added support for customizable formatting
    - Added support for relative time formatting
    - Added proper unit tests and examples
    - Added proper error handling
    - Added proper documentation
    - Added proper code organization
    - Added proper imports
    - Added proper constants
    - Added proper validation
    - Added proper testing

**Required Follow-up Tasks:**
1. Update all files that directly import constants to use new class prefix
2. Update all files that access settings to use new nested structure
3. Update notification providers to handle new message types
4. Update webhook provider to handle non-optional embeds
5. Update templates.py to handle JsonDict nesting limits in webhook payloads
6. ~~Ensure templates.py error messages align with new centralized error classes~~ ✅
   - Added centralized error messages in both Discord and Telegram templates
   - Updated all error messages to include proper context
   - Standardized error format across providers
7. Update type hints using the new enum types
8. Update provider implementations for thread safety
9. Update Discord provider to handle new error types
10. Update type hints in dependent files to use new domain sets
11. ~~Consolidate Discord validation into shared types module~~ ✅
12. ~~Remove redundant validation files~~ ✅
13. ~~Update imports to use centralized Discord types~~ ✅
14. ~~Document new Discord validation structure~~ ✅
15. ~~Update Telegram templates to handle new message types~~ ✅
16. ~~Update Telegram templates to use shared validation rules~~ ✅
17. ~~Add proper error context to Telegram templates~~ ✅
18. ~~Update Telegram template documentation~~ ✅
19. Add timeout configuration to Telegram templates
20. Update providers to use new progress bar styles
21. Update providers to use new time formats
22. Add color support to provider messages

**Review Order & Progress:**

1. Core Configuration
   - [x] `config/constants.py` - Core constants, types, and base configurations
   - [x] `config/settings.py` - Main settings management and environment handling

2. Shared Type Definitions
   - [x] `shared/types/discord/__init__.py` - Centralized Discord types, constants, and validation
   - [x] `shared/types/telegram.py` - Telegram-specific shared types

3. Base Provider Files
   - [x] `config/providers/base.py` - Base configuration models for providers
   - [x] `notifications/base.py` - Abstract notification provider implementation

4. Discord Provider Implementation
   - [x] `config/providers/discord/schemas.py` - Discord configuration validation using shared types
   - [x] `config/providers/discord/settings.py` - Discord settings management with shared validation
   - [x] `notifications/providers/discord/validators.py` - Discord message validation using shared rules
   - [x] `notifications/providers/discord/provider.py` - Discord provider implementation
   - [x] `notifications/providers/discord/templates.py` - Discord message templates and formatting utilities

5. Telegram Provider Implementation
   - [x] `config/providers/telegram/types.py` - Telegram provider type definitions
   - [x] `config/providers/telegram/schemas.py` - Telegram configuration validation
   - [x] `config/providers/telegram/settings.py` - Telegram settings management
   - [x] `notifications/providers/telegram/types.py` - Telegram notification types
   - [x] `notifications/providers/telegram/provider.py` - Telegram provider implementation
   - [x] `notifications/providers/telegram/templates.py` - Telegram message templates

6. Utility Files
   - [x] `utils/formatters.py` - Data formatting utilities
   - [x] `utils/validators.py` - Configuration validation utilities
   - [x] `utils/version.py` - Version checking and comparison

**Recent Changes:**
1. Discord Validation Consolidation
   - Created centralized `shared.types.discord` module
   - Moved all constants, types, and validation to `__init__.py`
   - Removed redundant validation files
   - Updated all imports to use new structure
   - Fixed ApiLimit typo to ApiLimits in templates.py
   - Consolidated type imports in Discord modules

2. Type System Improvements
   - Added comprehensive TypedDict definitions
   - Consolidated validation patterns and messages
   - Added immutable constants using Final and frozenset
   - Improved type safety across Discord provider

3. Documentation Updates
   - Added detailed docstrings for all validation methods
   - Updated configuration examples with timeout settings
   - Added timeout configuration documentation
   - Improved error message clarity and context

4. Version Utilities Enhancement
   - Added proper return type hints to all methods
   - Enhanced GitHub API response validation
   - Added detailed error handling for malformed version strings
   - Improved logging with error type information
   - Added cache status tracking and debug logs
   - Enhanced method documentation with detailed return types
   - Added notes about error handling behavior

**Each file review should focus on:**
1. Import correctness and ordering
2. Type safety and consistency
3. Proper use of shared types
4. Configuration validation
5. Error handling
6. Documentation completeness
7. Cross-file functionality analysis
   - Identify similar code across files
   - Check if existing shared components could be used
   - Look for opportunities to centralize common logic
   - Verify efficient use of shared utilities and types
   - Before making changes:
     - Search for current usage in other files
     - Document impact of changes
     - Update checklist with required follow-ups
     - Consider alternative approaches if impact is too broad
8. Remember to keep the "# folder/subfolder/filename.py" format at the top of the file
