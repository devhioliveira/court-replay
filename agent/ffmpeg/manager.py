"""FFmpeg process manager with watchdog and automatic restart."""
import asyncio
import os
import signal
import subprocess
import time
from pathlib import Path
from typing import Optional

from agent.config import Config
from agent.logger import ContextLogger
from agent.state import AgentState, StateManager


class FFmpegManager:
    """Manages the FFmpeg process for continuous RTSP capture with segmentation."""

    def __init__(self, config: Config, state: StateManager, logger: ContextLogger):
        self._config = config
        self._state = state
        self._logger = logger
        self._process: Optional[asyncio.subprocess.Process] = None
        self._running = False
        self._restart_count = 0
        self._last_restart_time = 0
        self._segment_pattern: Optional[str] = None
        self._health_check_task: Optional[asyncio.Task] = None

    @property
    def is_running(self) -> bool:
        return self._process is not None and self._process.returncode is None

    @property
    def segment_pattern(self) -> Optional[str]:
        return self._segment_pattern

    def _build_command(self) -> list[str]:
        """Build the FFmpeg command for segmented RTSP capture."""
        buffer_path = Path(self._config.storage.buffer_path)
        buffer_path.mkdir(parents=True, exist_ok=True)

        # Timestamped names so a FFmpeg restart never overwrites segments that
        # are still inside the pre-event window. Sequential %04d would restart
        # at 0001 and clobber the newest files.
        self._segment_pattern = str(buffer_path / "segment_%Y%m%d_%H%M%S.ts")
        segment_seconds = self._config.buffer.segment_seconds

        if self._config.agent_simulate:
            # Synthetic 720p test pattern, so the whole pipeline
            # (segment -> clip -> download) can be exercised without a camera.
            input_args = [
                "-re",
                "-f", "lavfi",
                "-i", "testsrc=size=1280x720:rate=25",
                "-map", "0:v:0",
                "-an",
                "-c:v", "libx264",
                "-preset", "veryfast",
                "-tune", "zerolatency",
                "-g", str(segment_seconds * 25),
                "-f", "segment",
                "-segment_time", str(segment_seconds),
                "-segment_format", "mpegts",
                "-reset_timestamps", "1",
                "-strftime", "1",
                self._segment_pattern,
            ]
            return ["ffmpeg", "-hide_banner", "-loglevel", "warning", "-nostdin", *input_args]

        rtsp_url = self._config.camera.rtsp_url
        if not rtsp_url:
            user = self._config.camera.user
            password = self._config.camera.password
            auth = f"{user}:{password}@" if user else ""
            rtsp_url = f"rtsp://{auth}{self._config.camera.ip}:554/stream1"

        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel", "warning",
            "-nostdin",
            "-rtsp_transport", "tcp",
            "-timeout", "5000000",  # RTSP socket I/O timeout (microseconds)
            "-i", rtsp_url,
            # Video only. "-map 0:v:0" means the audio stream is never mapped,
            # so FFmpeg does not decode it at all (saves CPU). The video is
            # stream-copied, so there is no re-encoding cost either.
            "-map", "0:v:0",
            "-an",
            "-c:v", "copy",
            "-f", "segment",
            "-segment_time", str(segment_seconds),
            "-segment_format", "mpegts",
            "-reset_timestamps", "1",
            "-strftime", "1",
            self._segment_pattern,
        ]
        return cmd

    async def start(self):
        """Start the FFmpeg process."""
        self._running = True
        await self._start_ffmpeg()
        self._health_check_task = asyncio.create_task(self._health_check_loop())
        self._logger.info("FFmpeg manager started")

    async def stop(self):
        """Stop the FFmpeg process."""
        self._running = False
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
        await self._stop_ffmpeg()
        self._logger.info("FFmpeg manager stopped")

    async def _start_ffmpeg(self):
        """Start or restart the FFmpeg process."""
        if not self._running:
            return

        cmd = self._build_command()
        self._logger.info("FFmpeg started", command=" ".join(cmd[:3]) + " ...")

        try:
            self._process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            self._state.set(AgentState.RECORDING)
            self._logger.info("FFmpeg process started", pid=self._process.pid)

            # Start stderr reader
            asyncio.create_task(self._read_stderr())
        except Exception as e:
            self._logger.error("Failed to start FFmpeg", error=str(e))
            self._state.set(AgentState.FFMPEG_RECONNECTING)
            await self._schedule_restart()

    async def _stop_ffmpeg(self):
        """Stop the current FFmpeg process."""
        if self._process and self._process.returncode is None:
            self._logger.info("Stopping FFmpeg", pid=self._process.pid)
            try:
                self._process.send_signal(signal.SIGTERM)
                await asyncio.wait_for(self._process.wait(), timeout=5)
            except asyncio.TimeoutError:
                self._logger.warning("FFmpeg did not stop gracefully, killing")
                self._process.kill()
                await self._process.wait()
            except Exception as e:
                self._logger.error("Error stopping FFmpeg", error=str(e))
        self._process = None

    async def _read_stderr(self):
        """Read FFmpeg stderr for logging."""
        try:
            while self._process and self._process.returncode is None:
                line = await self._process.stderr.readline()
                if not line:
                    break
                msg = line.decode("utf-8", errors="replace").strip()
                if msg:
                    if "error" in msg.lower() or "failed" in msg.lower():
                        self._logger.warning("FFmpeg", message=msg)
                    else:
                        self._logger.debug("FFmpeg", message=msg)
        except Exception:
            pass

    async def _health_check_loop(self):
        """Periodically check FFmpeg health."""
        while self._running:
            await asyncio.sleep(5)
            await self.check_health()

    async def check_health(self):
        """Check if FFmpeg is healthy and restart if needed."""
        if not self._running:
            return

        if self._process is None or self._process.returncode is not None:
            self._logger.warning("FFmpeg process died, restarting")
            self._state.set(AgentState.FFMPEG_RECONNECTING)
            await self._schedule_restart()

    async def _schedule_restart(self):
        """Schedule a restart with exponential backoff."""
        now = time.time()
        if now - self._last_restart_time < 1:
            self._restart_count += 1
        else:
            self._restart_count = 0

        self._last_restart_time = now
        delay = min(2 ** self._restart_count, 60)

        self._logger.info(f"Reconnecting in {delay}s...", attempt=self._restart_count)
        await asyncio.sleep(delay)

        if self._running:
            await self._stop_ffmpeg()
            await self._start_ffmpeg()

    async def restart(self):
        """Force restart FFmpeg."""
        self._logger.info("FFmpeg restart requested")
        await self._stop_ffmpeg()
        await self._start_ffmpeg()
