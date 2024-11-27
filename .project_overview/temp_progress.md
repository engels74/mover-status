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

**Required Follow-up Tasks:**
1. Update all files that directly import constants to use new class prefix
2. Update all files that access settings to use new nested structure
3. Update notification providers to handle new message types
4. Update webhook provider to handle non-optional embeds
5. Update validation code to use new validation functions
6. Update type hints using the new enum types
7. Update environment variable documentation
8. Update example configurations
9. Add documentation for NotificationState usage
10. Update webhook implementations for new constraints
11. Update provider implementations for thread safety
12. Update Discord provider to handle new error types
13. Update documentation with new validation requirements
14. Update type hints in dependent files to use new domain sets
15. Consolidate Discord validation into shared types module
16. Remove redundant validation files
17. Update imports to use centralized Discord types
18. Document new Discord validation structure
19. Update configuration examples with timeout settings
20. Add timeout configuration to documentation

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
   - [ ] `notifications/providers/discord/templates.py` - Discord message templates

5. Telegram Provider Implementation
   - [ ] `config/providers/telegram/types.py` - Telegram provider type definitions
   - [ ] `config/providers/telegram/schemas.py` - Telegram configuration validation
   - [ ] `config/providers/telegram/settings.py` - Telegram settings management
   - [ ] `notifications/providers/telegram/types.py` - Telegram notification types
   - [ ] `notifications/providers/telegram/provider.py` - Telegram provider implementation
   - [ ] `notifications/providers/telegram/templates.py` - Telegram message templates

6. Utility Files
   - [ ] `utils/formatters.py` - Data formatting utilities
   - [ ] `utils/validators.py` - Configuration validation utilities
   - [ ] `utils/version.py` - Version checking and comparison

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
   - Added Discord integration structure to project overview
   - Updated file organization documentation
   - Added validation rules documentation
   - Documented type system improvements

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