"""Agent state management."""
import asyncio
from enum import Enum
from typing import Callable, List


class AgentState(str, Enum):
    STARTING = "STARTING"
    READY = "READY"
    CAMERA_OFFLINE = "CAMERA_OFFLINE"
    FFMPEG_RECONNECTING = "FFMPEG_RECONNECTING"
    RECORDING = "RECORDING"
    CREATING_CLIP = "CREATING_CLIP"
    ERROR = "ERROR"


class StateManager:
    def __init__(self):
        self._state = AgentState.STARTING
        self._lock = asyncio.Lock()
        self._callbacks: List[Callable[[AgentState, AgentState], None]] = []

    @property
    def current(self) -> AgentState:
        return self._state

    def set(self, new_state: AgentState):
        old_state = self._state
        if old_state == new_state:
            return
        self._state = new_state
        for cb in self._callbacks:
            try:
                cb(old_state, new_state)
            except Exception:
                pass

    def on_change(self, callback: Callable[[AgentState, AgentState], None]):
        self._callbacks.append(callback)

    def is_healthy(self) -> bool:
        return self._state in (AgentState.READY, AgentState.RECORDING, AgentState.CREATING_CLIP)
