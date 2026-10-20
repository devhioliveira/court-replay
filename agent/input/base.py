"""Input abstraction for trigger detection."""
from abc import ABC, abstractmethod
from typing import Callable, Optional


class InputHandler(ABC):
    """Abstract base class for input handlers."""

    def __init__(self, logger):
        self._logger = logger
        self._trigger_callbacks: list[Callable] = []
        self._running = False

    def on_trigger(self, callback: Callable):
        """Register a callback for trigger events."""
        self._trigger_callbacks.append(callback)

    def _fire_trigger(self):
        """Fire all registered trigger callbacks."""
        self._logger.info("CLIP TRIGGER")
        for cb in self._trigger_callbacks:
            try:
                cb()
            except Exception as e:
                self._logger.error("Trigger callback failed", error=str(e))

    @abstractmethod
    async def start(self):
        """Start listening for input events."""
        pass

    @abstractmethod
    async def stop(self):
        """Stop listening for input events."""
        pass

    @property
    def is_running(self) -> bool:
        return self._running
