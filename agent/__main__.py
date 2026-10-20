"""Agent entry point."""
import argparse
import asyncio
import os
import sys

from agent.config import Config
from agent.logger import get_logger
from agent.state import AgentState, StateManager
from agent.input import create_input_handler
from agent.ffmpeg.manager import FFmpegManager
from agent.clip_manager.manager import ClipManager
from agent.storage.manager import StorageManager
from agent.cleanup.scheduler import CleanupScheduler
from agent.api.server import APIServer


async def main():
    parser = argparse.ArgumentParser(description="Court Replay Agent")
    parser.add_argument("--simulate", action="store_true", help="Run in simulation mode (no camera)")
    parser.add_argument("--config", default="config.json", help="Path to config file")
    args = parser.parse_args()

    config = Config.load(args.config)
    if args.simulate:
        config.agent_simulate = True

    logger = get_logger(config)
    logger.info("Agent starting", version="1.0.0", simulate=config.agent_simulate)

    state = StateManager()
    state.set(AgentState.STARTING)

    storage = StorageManager(config)
    await storage.initialize()

    ffmpeg = FFmpegManager(config, state, logger)
    clip_manager = ClipManager(config, storage, ffmpeg, state, logger)
    input_handler = create_input_handler(config, logger)
    cleanup = CleanupScheduler(config, storage, clip_manager, logger)
    api_server = APIServer(config, state, clip_manager, ffmpeg, logger)

    # The input handler fires from its own thread (Windows hook / evdev thread),
    # so hop back onto the event loop before creating the task.
    loop = asyncio.get_running_loop()

    def on_trigger():
        loop.call_soon_threadsafe(
            lambda: asyncio.ensure_future(clip_manager.handle_trigger())
        )

    input_handler.on_trigger(on_trigger)

    try:
        await ffmpeg.start()
        await input_handler.start()
        await cleanup.start()
        await api_server.start()

        state.set(AgentState.READY)
        logger.info("Agent ready")

        # Keep running
        while True:
            await asyncio.sleep(1)
            # Prune the buffer so it never grows unbounded.
            storage.cleanup_old_segments(config.buffer.max_buffer_segments)
    except asyncio.CancelledError:
        logger.info("Agent shutting down")
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    finally:
        state.set(AgentState.ERROR)
        await api_server.stop()
        await cleanup.stop()
        await input_handler.stop()
        await ffmpeg.stop()
        logger.info("Agent stopped")


if __name__ == "__main__":
    asyncio.run(main())
