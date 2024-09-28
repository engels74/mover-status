# main.py
import asyncio
import logging
import yaml
from typing import Dict, Any, List
from mover.monitor import MoverMonitor
from notifiers.discord import DiscordNotifier
from notifiers.telegram import TelegramNotifier
from notifiers.base import BaseNotifier

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def load_config(config_path: str = 'config.yaml') -> Dict[str, Any]:
    """Load configuration from YAML file."""
    try:
        with open(config_path, 'r') as config_file:
            return yaml.safe_load(config_file)
    except Exception as e:
        logger.error(f"Failed to load configuration: {str(e)}")
        raise

def initialize_notifiers(config: Dict[str, Any]) -> List[BaseNotifier]:
    """Initialize notifier objects based on configuration."""
    notifiers = []
    if config['discord']['enabled']:
        notifiers.append(DiscordNotifier.from_config(config['discord']))
    if config['telegram']['enabled']:
        notifiers.append(TelegramNotifier.from_config(config['telegram']))
    return notifiers

async def main():
    """Main function to set up and run the Mover Status application."""
    try:
        config = load_config()
        notifiers = initialize_notifiers(config)
        
        if not notifiers:
            logger.error("No notifiers enabled. Please enable at least one notifier in the configuration.")
            return

        monitor = MoverMonitor(config, notifiers)
        await monitor.run()
    except Exception as e:
        logger.error(f"An error occurred in the main function: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main())
