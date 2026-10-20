"""Simulated input handler for development/testing."""
import asyncio
import random
from typing import Optional

from agent.input.base import InputHandler
from agent.logger import ContextLogger


class SimulateInputHandler(InputHandler):
    """Simulates trigger events at random intervals for testing."""

    def __init__(self, logger: ContextLogger):
        super().__init__(logger)
        self._task: Optional[asyncio.Task] = None
        self._running = False

    async def _simulate(self):
        """Fire a trigger every 15-45 seconds."""
        while self._running:
            await asyncio.sleep(random.uniform(15, 45))
            if self._running:
                self._logger.info("Simulated trigger")
                self._fire_trigger()

    async def start(self):
        self._running = True
        self._task = asyncio.create_task(self._simulate())
        self._logger.info("Simulated input handler started")

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._logger.info("Simulated input handler stopped")
