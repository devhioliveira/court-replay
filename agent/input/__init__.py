"""Input handler factory."""
import platform

from agent.config import Config
from agent.input.base import InputHandler
from agent.input.windows import WindowsInputHandler
from agent.input.linux import LinuxInputHandler
from agent.logger import ContextLogger


def create_input_handler(config: Config, logger: ContextLogger) -> InputHandler:
    """Create the appropriate input handler for the current platform."""
    system = platform.system()

    if config.agent_simulate:
        from agent.input.simulate import SimulateInputHandler
        return SimulateInputHandler(logger)

    if system == "Windows":
        return WindowsInputHandler(logger)
    elif system == "Linux":
        return LinuxInputHandler(logger)
    else:
        raise RuntimeError(f"Unsupported platform: {system}")
