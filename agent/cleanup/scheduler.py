"""Daily cleanup scheduler - runs at midnight to remove old clips."""
import asyncio
from datetime import datetime, timedelta
from typing import Optional

from agent.config import Config
from agent.logger import ContextLogger
from agent.storage.manager import StorageManager
from agent.clip_manager.manager import ClipManager


class CleanupScheduler:
    """Schedules and executes daily cleanup at midnight."""

    def __init__(
        self,
        config: Config,
        storage: StorageManager,
        clip_manager: ClipManager,
        logger: ContextLogger,
    ):
        self._config = config
        self._storage = storage
        self._clip_manager = clip_manager
        self._logger = logger
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self):
        """Start the cleanup scheduler."""
        if not self._config.cleanup.enabled:
            self._logger.info("Cleanup scheduler disabled")
            return

        self._running = True
        self._task = asyncio.create_task(self._scheduler_loop())
        self._logger.info(
            "Cleanup scheduler started",
            hour=self._config.cleanup.hour,
            minute=self._config.cleanup.minute,
        )

    async def stop(self):
        """Stop the cleanup scheduler."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._logger.info("Cleanup scheduler stopped")

    async def _scheduler_loop(self):
        """Main scheduler loop that waits until midnight."""
        while self._running:
            try:
                now = datetime.now()
                target = now.replace(
                    hour=self._config.cleanup.hour,
                    minute=self._config.cleanup.minute,
                    second=0,
                    microsecond=0,
                )

                # If target time has passed today, schedule for tomorrow
                if target <= now:
                    target += timedelta(days=1)

                wait_seconds = (target - now).total_seconds()
                self._logger.info(
                    "Next cleanup scheduled",
                    target=target.isoformat(),
                    wait_seconds=wait_seconds,
                )

                # Wait until midnight
                while wait_seconds > 0 and self._running:
                    sleep_time = min(wait_seconds, 60)
                    await asyncio.sleep(sleep_time)
                    wait_seconds -= sleep_time

                if self._running:
                    await self._execute_cleanup()

            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.error("Cleanup scheduler error", error=str(e))
                await asyncio.sleep(60)

    async def _execute_cleanup(self):
        """Execute the daily cleanup."""
        self._logger.info("Daily cleanup started", timestamp=datetime.now().isoformat())

        try:
            result = self._storage.cleanup_daily()
            self._logger.info(
                "Daily cleanup completed",
                deleted_clips=result["deletedClips"],
                deleted_metadata=result["deletedMetadata"],
            )
        except Exception as e:
            self._logger.error("Daily cleanup failed", error=str(e))

    async def run_now(self):
        """Force run cleanup immediately (for testing)."""
        self._logger.info("Manual cleanup triggered")
        await self._execute_cleanup()
