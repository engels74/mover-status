"""Application runner for Mover Status Monitor."""

from __future__ import annotations

import asyncio
import logging
import signal
from pathlib import Path
from typing import TYPE_CHECKING
from collections.abc import Sequence

from pydantic import ValidationError

from ..config.loader.config_loader import ConfigLoader
from ..config.models.main import AppConfig

if TYPE_CHECKING:
    from ..core.monitor.orchestrator import MonitorOrchestrator
    from ..core.monitor.lifecycle import LifecycleManager
    from ..core.monitor.state_machine import StateMachine

logger = logging.getLogger(__name__)


class ApplicationRunner:
    """Main application runner that coordinates all components."""
    
    def __init__(
        self,
        config_path: Path,
        dry_run: bool = False,
        log_level: str = "INFO",
        run_once: bool = False,
    ) -> None:
        """Initialize the application runner.

        Args:
            config_path: Path to the configuration file
            dry_run: Whether to run in dry-run mode (no notifications sent)
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
            run_once: Whether to run once and exit instead of continuous monitoring
        """
        self.config_path: Path = config_path
        self.dry_run: bool = dry_run
        self.log_level: str = log_level
        self.run_once: bool = run_once
        
        # Load and validate configuration
        # If config_path is just a filename, use current directory as config dir
        config_dir = config_path.parent if config_path.parent != Path('.') else Path.cwd()
        
        # If the config file doesn't exist, try to find it using discovery logic
        if not config_path.exists():
            discovered_path = self._discover_config_file()
            if not discovered_path.exists():
                # No configuration file found anywhere
                self._handle_missing_configuration(config_path)
            config_path = discovered_path
            config_dir = config_path.parent if config_path.parent != Path('.') else Path.cwd()
        
        self.config_loader: ConfigLoader = ConfigLoader(config_dir)
        
        # Load complete configuration (main config + provider configs + env overrides)
        try:
            complete_config = self.config_loader.load_complete_config()
        except Exception as e:
            raise ValueError(f"Failed to load configuration from '{config_dir}': {e}")
        
        try:
            self.config: AppConfig = AppConfig.model_validate(complete_config)
        except Exception as e:
            # Re-raise with more context about which directory failed
            # For ValidationError, we want to preserve the original error
            if isinstance(e, ValidationError):
                raise e  # Preserve the original ValidationError
            else:
                raise type(e)(f"Configuration validation failed for '{config_dir}': {e}") from e
        
        # Override with CLI flags
        if dry_run:
            self.config.monitoring.dry_run = True
        
        # Set up logging based on config and CLI
        self._setup_logging()
        
        # Components (initialized in _setup_components)
        self.orchestrator: MonitorOrchestrator | None = None
        self.lifecycle_manager: LifecycleManager | None = None
        
        # Application state
        self._shutdown_requested: bool = False
    
    def _discover_config_file(self) -> Path:
        """Discover configuration file in standard locations.
        
        Searches for configuration files in the following order of precedence:
        1. Current directory (config.yaml, config.yml, config.json, config.toml)
        2. User home directory (~/.mover-status.yaml, etc.)
        3. System directories (/etc/mover-status/, etc.)
        
        Returns:
            Path to the first configuration file found, or default 'config.yaml'
            if no configuration file is discovered.
        """
        # Configuration file discovery paths in order of precedence
        # 1. Current directory
        current_dir_config_files = [
            'config.yaml',
            'config.yml',
            'config.json',
            'config.toml',
        ]
        
        # 2. User home directory
        home_config_files = [
            '.mover-status.yaml',
            '.mover-status.yml',
            '.mover-status.json',
            '.mover-status.toml',
        ]
        
        # 3. System configuration directories
        system_config_paths = [
            Path('/etc/mover-status/config.yaml'),
            Path('/etc/mover-status.yaml'),
            Path('/usr/local/etc/mover-status/config.yaml'),
            Path('/usr/local/etc/mover-status.yaml'),
        ]
        
        # 1. Check current directory
        for config_file in current_dir_config_files:
            config_path = Path(config_file)
            if config_path.exists() and config_path.is_file():
                return config_path
        
        # 2. Check user home directory
        try:
            home_dir = Path.home()
            for config_file in home_config_files:
                config_path = home_dir / config_file
                if config_path.exists() and config_path.is_file():
                    return config_path
        except (OSError, RuntimeError):
            # Path.home() can fail in some environments
            pass
        
        # 3. Check system directories
        for config_path in system_config_paths:
            if config_path.exists() and config_path.is_file():
                return config_path
        
        # Default fallback
        return Path('config.yaml')
    
    def _handle_missing_configuration(self, requested_path: Path) -> None:
        """Handle missing configuration file with helpful error message.
        
        Args:
            requested_path: The configuration file path that was requested
            
        Raises:
            FileNotFoundError: Always raises with helpful guidance
        """
        error_message = f"Configuration file not found: {requested_path}\n"
        error_message += "\nSearched in the following locations:\n"
        
        # Show current directory search
        error_message += f"  • Current directory: {Path.cwd()}\n"
        for config_file in ['config.yaml', 'config.yml', 'config.json', 'config.toml']:
            error_message += f"    - {config_file}\n"
        
        # Show home directory search
        try:
            home_dir = Path.home()
            error_message += f"  • Home directory: {home_dir}\n"
            for config_file in ['.mover-status.yaml', '.mover-status.yml', '.mover-status.json', '.mover-status.toml']:
                error_message += f"    - {config_file}\n"
        except (OSError, RuntimeError):
            error_message += "  • Home directory: (unavailable)\n"
        
        # Show system directories
        error_message += "  • System directories:\n"
        system_paths = [
            '/etc/mover-status/config.yaml',
            '/etc/mover-status.yaml',
            '/usr/local/etc/mover-status/config.yaml',
            '/usr/local/etc/mover-status.yaml',
        ]
        for path in system_paths:
            error_message += f"    - {path}\n"
        
        error_message += "\nTo get started:\n"
        error_message += "  1. Copy the example configuration to 'config.yaml' in your current directory\n"
        error_message += "  2. Edit the configuration file to add your credentials\n"
        error_message += "  3. Run 'mover-status --validate-config' to check your configuration\n"
        
        # Check if there's an example config nearby
        example_configs = [
            'configs/examples/config.yaml.example',
            'config.yaml.example',
            'example-config.yaml'
        ]
        
        found_example = None
        for example in example_configs:
            example_path = Path(example)
            if example_path.exists():
                found_example = example_path
                break
        
        if found_example:
            error_message += f"\nExample configuration found at: {found_example}\n"
            error_message += f"Copy it with: cp {found_example} config.yaml\n"
        
        raise FileNotFoundError(error_message)
    
    def _setup_logging(self) -> None:
        """Set up logging based on configuration and CLI options."""
        # Use CLI log level if provided, otherwise use config
        log_level = self.log_level or self.config.logging.level
        
        # Get numeric log level
        numeric_level = getattr(logging, log_level.upper(), logging.INFO)
        
        # Configure root logger
        logging.basicConfig(
            level=numeric_level,
            format=self.config.logging.format,
            force=True  # Override any existing configuration
        )
        
        # If config specifies a log file, set it up
        if self.config.logging.file:
            file_handler = logging.FileHandler(self.config.logging.file)
            file_handler.setLevel(numeric_level)
            formatter = logging.Formatter(self.config.logging.format)
            file_handler.setFormatter(formatter)
            logging.getLogger().addHandler(file_handler)
        
        logger.info(f"Logging initialized at level: {log_level}")
    
    def _setup_components(self) -> None:
        """Initialize and configure all application components."""
        from ..core.process import UnraidMoverDetector
        from ..core.progress import ProgressCalculator
        from ..notifications.manager import AsyncDispatcher
        from ..core.monitor.state_machine import StateMachine, MonitorState
        from ..core.monitor.event_bus import EventBus
        from ..core.monitor.orchestrator import MonitorOrchestrator
        from ..core.monitor.lifecycle import LifecycleManager
        
        logger.info("Initializing application components")
        
        # Initialize core components
        process_detector = UnraidMoverDetector()
        
        progress_calculator = ProgressCalculator(
            window_size=self.config.progress.estimation_window
        )
        
        async_dispatcher = AsyncDispatcher(
            max_workers=5,
            queue_size=1000
        )
        
        state_machine = StateMachine(initial_state=MonitorState.IDLE)
        
        # Set up state transitions
        self._setup_state_transitions(state_machine)
        
        event_bus = EventBus()
        
        # Initialize orchestrator with all components
        self.orchestrator = MonitorOrchestrator(
            detector=process_detector,
            calculator=progress_calculator,
            dispatcher=async_dispatcher,
            state_machine=state_machine,
            event_bus=event_bus
        )
        
        # Initialize lifecycle manager
        self.lifecycle_manager = LifecycleManager(self.orchestrator)
        self.lifecycle_manager.set_config_path(self.config_path)
        
        # Configure notification providers
        self._configure_notification_providers()
        
        # Wire event handlers
        self._setup_event_handlers()
        
        logger.info("All components initialized successfully")
    
    def _setup_state_transitions(self, state_machine: "StateMachine") -> None:
        """Set up valid state transitions for the state machine."""
        from ..core.monitor.state_machine import StateTransition, MonitorState
        
        # Define valid transitions
        transitions = [
            # From IDLE
            StateTransition(MonitorState.IDLE, MonitorState.DETECTING),
            StateTransition(MonitorState.IDLE, MonitorState.ERROR),
            StateTransition(MonitorState.IDLE, MonitorState.SHUTDOWN),
            StateTransition(MonitorState.IDLE, MonitorState.SUSPENDED),
            
            # From DETECTING
            StateTransition(MonitorState.DETECTING, MonitorState.IDLE),
            StateTransition(MonitorState.DETECTING, MonitorState.MONITORING),
            StateTransition(MonitorState.DETECTING, MonitorState.ERROR),
            StateTransition(MonitorState.DETECTING, MonitorState.SHUTDOWN),
            
            # From MONITORING
            StateTransition(MonitorState.MONITORING, MonitorState.IDLE),
            StateTransition(MonitorState.MONITORING, MonitorState.DETECTING),
            StateTransition(MonitorState.MONITORING, MonitorState.COMPLETING),
            StateTransition(MonitorState.MONITORING, MonitorState.ERROR),
            StateTransition(MonitorState.MONITORING, MonitorState.SHUTDOWN),
            StateTransition(MonitorState.MONITORING, MonitorState.SUSPENDED),
            
            # From COMPLETING
            StateTransition(MonitorState.COMPLETING, MonitorState.IDLE),
            StateTransition(MonitorState.COMPLETING, MonitorState.ERROR),
            StateTransition(MonitorState.COMPLETING, MonitorState.SHUTDOWN),
            
            # From ERROR
            StateTransition(MonitorState.ERROR, MonitorState.IDLE),
            StateTransition(MonitorState.ERROR, MonitorState.RECOVERING),
            StateTransition(MonitorState.ERROR, MonitorState.SHUTDOWN),
            
            # From RECOVERING
            StateTransition(MonitorState.RECOVERING, MonitorState.IDLE),
            StateTransition(MonitorState.RECOVERING, MonitorState.ERROR),
            StateTransition(MonitorState.RECOVERING, MonitorState.SHUTDOWN),
            
            # From SUSPENDED
            StateTransition(MonitorState.SUSPENDED, MonitorState.IDLE),
            StateTransition(MonitorState.SUSPENDED, MonitorState.SHUTDOWN),
            
            # From SHUTDOWN (should be terminal, but allow restart)
            StateTransition(MonitorState.SHUTDOWN, MonitorState.IDLE),
        ]
        
        # Add all transitions to the state machine
        for transition in transitions:
            state_machine.add_transition(transition)
    
    def _configure_notification_providers(self) -> None:
        """Configure and register notification providers using dynamic plugin loading."""
        if not self.orchestrator:
            return
            
        logger.info("Configuring notification providers using dynamic plugin loading")
        
        # Import plugin loader
        from ..plugins.loader import PluginLoader
        
        # Initialize plugin loader
        plugin_loader = PluginLoader()
        
        # Load plugins for enabled providers
        enabled_providers = list(self.config.notifications.enabled_providers)
        load_results = plugin_loader.load_enabled_plugins(enabled_providers)
        
        # Log load results
        for plugin_name, success in load_results.items():
            if success:
                logger.info("Successfully loaded plugin: %s", plugin_name)
            else:
                logger.error("Failed to load plugin: %s", plugin_name)
        
        # Create and register provider instances using dynamic configuration extraction
        provider_configs = self._extract_provider_configurations(enabled_providers)
        
        for provider_name in enabled_providers:
            try:
                # Get provider configuration dynamically
                provider_config = provider_configs.get(provider_name)
                
                if provider_config is None:
                    logger.warning("No configuration found for provider: %s", provider_name)
                    continue
                
                # Create provider instance
                provider_instance = plugin_loader.create_provider_instance(
                    provider_name, 
                    provider_config
                )
                
                if provider_instance:
                    # Register with dispatcher
                    self.orchestrator.dispatcher.register_provider(provider_name, provider_instance)
                    logger.info("Provider registered with dispatcher: %s", provider_name)
                else:
                    logger.error("Failed to create instance for provider: %s", provider_name)
                    
            except Exception as e:
                logger.error("Failed to configure provider %s: %s", provider_name, e)
        
        # Log final status
        loader_status = plugin_loader.get_loader_status()
        logger.info("Plugin loading completed. Loaded %d plugins, registered %d providers", 
                   loader_status["loaded_plugins"], loader_status["registered_providers"])
    
    def _extract_provider_configurations(self, enabled_providers: Sequence[object]) -> dict[str, dict[str, object]]:
        """Extract provider configurations dynamically from the config object.
        
        This method provides a provider-agnostic way to extract configuration
        by using reflection to find provider-specific config sections.
        
        Args:
            enabled_providers: List of enabled provider names
            
        Returns:
            Dictionary mapping provider names to their configurations
        """
        provider_configs: dict[str, dict[str, object]] = {}
        
        # Get all provider configurations from the providers object using reflection
        providers_config = self.config.providers
        
        for provider_name_raw in enabled_providers:
            provider_name = str(provider_name_raw)
            try:
                # Use the new dynamic provider config method
                provider_config = providers_config.get_provider_config(provider_name)
                
                if provider_config is not None:
                    provider_configs[provider_name] = provider_config
                    logger.debug("Extracted configuration for provider: %s", provider_name)
                else:
                    # Try to load from the config loader's raw configuration
                    fallback_config = self._load_provider_config_from_file(provider_name)
                    if fallback_config:
                        provider_configs[provider_name] = fallback_config
                    
            except Exception as e:
                logger.error("Failed to extract configuration for provider %s: %s", provider_name, e)
        
        return provider_configs
    
    def _load_provider_config_from_file(self, provider_name: str) -> dict[str, object]:
        """Load provider configuration directly from config files.
        
        This method looks for provider-specific configuration files and loads them directly.
        This is a fallback when the provider config is not in the main config structure.
        
        Args:
            provider_name: Name of the provider
            
        Returns:
            Provider configuration dictionary
        """
        try:
            # Try to load provider-specific config file
            config_file_patterns = [
                f"config_{provider_name}.yaml",
                f"config_{provider_name}.yml", 
                f"config_{provider_name}.json",
                f"{provider_name}.yaml",
                f"{provider_name}.yml",
                f"{provider_name}.json"
            ]
            
            config_dir = self.config_path.parent if self.config_path.parent != Path('.') else Path.cwd()
            
            for pattern in config_file_patterns:
                config_file = config_dir / pattern
                if config_file.exists():
                    logger.debug("Loading provider config from file: %s", config_file)
                    
                    # Import the yaml loader
                    from ..config.loader.yaml_loader import YamlLoader
                    yaml_loader = YamlLoader()
                    
                    config_data = yaml_loader.load(config_file)
                    
                    # The config file might have the provider as root key or direct config
                    if isinstance(config_data, dict):
                        if provider_name in config_data:
                            provider_config = config_data[provider_name]
                            return provider_config if isinstance(provider_config, dict) else {}
                        else:
                            return config_data
                    
                    break
            
            logger.warning("No configuration file found for provider: %s", provider_name)
            return {}
            
        except Exception as e:
            logger.error("Error loading provider config file for %s: %s", provider_name, e)
            return {}
    
    def _setup_event_handlers(self) -> None:
        """Wire event handlers between components."""
        if not self.orchestrator:
            return
            
        logger.info("Setting up event handlers")
        
        # Event handlers will be integrated later when the exact EventBus API is confirmed
        # For now, the orchestrator handles its own event publishing
        # The dispatcher is already registered with providers and ready to send notifications
        
        logger.info("Event handlers configured")
    
    def run(self) -> None:
        """Run the application."""
        logger.info(f"Starting Mover Status Monitor with config: {self.config_path}")
        
        if self.dry_run:
            logger.info("Running in dry-run mode (no notifications will be sent)")
        
        if self.run_once:
            logger.info("Running in single-shot mode")
        else:
            logger.info("Running in continuous monitoring mode")
        
        try:
            # Set up signal handlers for graceful shutdown
            self._setup_signal_handlers()
            
            # Initialize components
            self._setup_components()
            
            # Run the monitoring loop
            asyncio.run(self._async_run())
            
        except KeyboardInterrupt:
            logger.info("Shutdown requested by user (Ctrl+C)")
        except Exception as e:
            logger.error(f"Application error: {e}")
            raise
        finally:
            logger.info("Mover Status Monitor shutdown complete")
    
    def _setup_signal_handlers(self) -> None:
        """Set up signal handlers for graceful shutdown."""
        def signal_handler(signum: int, _frame: object) -> None:
            logger.info(f"Received signal {signum}, requesting shutdown...")
            self._shutdown_requested = True
        
        _ = signal.signal(signal.SIGINT, signal_handler)
        _ = signal.signal(signal.SIGTERM, signal_handler)
    
    async def _async_run(self) -> None:
        """Main async monitoring loop."""
        if not self.lifecycle_manager or not self.orchestrator:
            raise RuntimeError("Components not properly initialized")
        
        try:
            # Start lifecycle manager and all components
            await self.lifecycle_manager.startup()
            
            logger.info("All components started successfully")
            
            if self.run_once:
                # Single-shot execution
                await self._run_once()
            else:
                # Continuous monitoring
                await self._run_continuous()
                
        except Exception as e:
            logger.error(f"Error in monitoring loop: {e}")
            raise
        finally:
            # Always ensure clean shutdown
            if self.lifecycle_manager:
                await self.lifecycle_manager.shutdown()
    
    async def _run_once(self) -> None:
        """Run a single detection and monitoring cycle."""
        if not self.orchestrator:
            return
            
        logger.info("Starting single-shot monitoring cycle")
        
        # Run detection cycle
        await self.orchestrator.run_detection_cycle()
        
        # If we found a process, monitor it briefly
        if self.orchestrator.current_process:
            logger.info("Process detected, running brief monitoring cycle")
            await self.orchestrator.run_monitoring_cycle()
        else:
            logger.info("No mover process detected")
    
    async def _run_continuous(self) -> None:
        """Run continuous monitoring with configurable intervals."""
        if not self.orchestrator:
            return
            
        logger.info("Starting continuous monitoring loop")
        
        while not self._shutdown_requested:
            try:
                # Run detection cycle
                await self.orchestrator.run_detection_cycle()
                
                # If monitoring, run monitoring cycle
                if (self.orchestrator.current_process and 
                    self.orchestrator.state_machine.current_state.name in ['MONITORING']):
                    await self.orchestrator.run_monitoring_cycle()
                
                # Wait for configured interval before next cycle
                interval = self.config.monitoring.interval
                logger.debug(f"Waiting {interval} seconds before next cycle")
                
                # Use a loop to allow early exit on shutdown
                for _ in range(int(interval)):
                    if self._shutdown_requested:
                        break
                    await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"Error in monitoring cycle: {e}")
                # Continue after error, but wait a bit longer
                await asyncio.sleep(min(30, self.config.monitoring.interval * 2))
        
        logger.info("Continuous monitoring loop stopped")
