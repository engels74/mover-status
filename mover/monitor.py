# mover/monitor.py
import asyncio
import logging
from datetime import datetime
from typing import List, Dict, Any
from ..notifiers.base import BaseNotifier
from .utils import human_readable_size, calculate_etc

logger = logging.getLogger(__name__)

class MoverMonitor:
    """
    Monitors the mover process and sends notifications about its progress.
    """

    def __init__(self, config: Dict[str, Any], notifiers: List[BaseNotifier]):
        self.config = config
        self.notifiers = notifiers
        self.mover_executable = config['mover']['executable']
        self.cache_path = config['mover']['cache_path']
        self.exclude_paths = config['exclude_paths']
        self.notification_increment = config['notifications']['increment']
        self.dry_run = config['debug']['dry_run']

    async def run(self):
        """Main method to run the mover monitoring process."""
        logger.info("Starting Mover Status Monitor...")
        
        while True:
            logger.info("Waiting for mover process to start...")
            await self._wait_for_mover_process()
            
            logger.info("Mover process found, starting monitoring...")
            initial_size = await self._get_cache_size()
            initial_readable = human_readable_size(initial_size)
            logger.info(f"Initial total size of data: {initial_readable}")

            start_time = datetime.now()
            percent = 0
            total_data_moved = 0
            last_notified = -1

            await self._send_notifications(percent, initial_readable, "Calculating...")

            while True:
                current_size = await self._get_cache_size()
                remaining_readable = human_readable_size(current_size)

                total_data_moved = initial_size - current_size
                percent = int((total_data_moved * 100) / (total_data_moved + current_size))

                if not await self._is_mover_running():
                    logger.info("Mover process is no longer running.")
                    await self._send_completion_notifications()
                    break

                rounded_percent = (percent // self.notification_increment) * self.notification_increment
                if rounded_percent >= last_notified + self.notification_increment:
                    etc = calculate_etc(percent, start_time, total_data_moved, current_size, "discord")
                    await self._send_notifications(percent, remaining_readable, etc)
                    last_notified = rounded_percent
                    logger.info(f"Notification sent for {percent}% completion.")

                await asyncio.sleep(1)

            logger.info("Restarting monitoring after completion...")
            await asyncio.sleep(10)

    async def _wait_for_mover_process(self):
        """Wait for the mover process to start."""
        while not await self._is_mover_running():
            await asyncio.sleep(10)

    async def _is_mover_running(self):
        """Check if the mover process is currently running."""
        if self.dry_run:
            return True
        
        process = await asyncio.create_subprocess_shell(
            f"pgrep -x {self.mover_executable}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await process.communicate()
        return bool(stdout)

    async def _get_cache_size(self):
        """Calculate the current size of the cache, excluding specified paths."""
        if self.dry_run:
            return 1000000000  # 1 GB for testing
        
        exclude_params = ' '.join(f"--exclude={path}" for path in self.exclude_paths)
        process = await asyncio.create_subprocess_shell(
            f"du -sb {exclude_params} {self.cache_path} | cut -f1",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await process.communicate()
        return int(stdout.decode().strip())

    async def _send_notifications(self, percent: int, remaining_data: str, etc: str):
        """Send notifications to all configured notifiers."""
        for notifier in self.notifiers:
            try:
                await notifier.send_notification(percent, remaining_data, etc)
            except Exception as e:
                logger.error(f"Failed to send notification via {type(notifier).__name__}: {str(e)}")

    async def _send_completion_notifications(self):
        """Send completion notifications to all configured notifiers."""
        for notifier in self.notifiers:
            try:
                await notifier.send_completion_notification()
            except Exception as e:
                logger.error(f"Failed to send completion notification via {type(notifier).__name__}: {str(e)}")