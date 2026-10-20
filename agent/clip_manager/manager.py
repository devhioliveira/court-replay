"""Clip manager - handles trigger events and clip generation."""
import asyncio
import hashlib
import json
import os
import subprocess
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from agent.config import Config
from agent.logger import ContextLogger
from agent.state import AgentState, StateManager
from agent.storage.manager import StorageManager
from agent.ffmpeg.manager import FFmpegManager


class ClipManager:
    """Manages clip creation from buffer segments."""

    def __init__(
        self,
        config: Config,
        storage: StorageManager,
        ffmpeg: FFmpegManager,
        state: StateManager,
        logger: ContextLogger,
    ):
        self._config = config
        self._storage = storage
        self._ffmpeg = ffmpeg
        self._state = state
        self._logger = logger
        self._processing = False
        self._clip_counter = 0

    async def handle_trigger(self):
        """Handle a trigger event - create a clip from buffer segments."""
        if self._processing:
            self._logger.warning("Clip creation already in progress, skipping trigger")
            return

        self._processing = True
        self._state.set(AgentState.CREATING_CLIP)
        self._logger.info("Clip creation started")

        try:
            trigger_time = datetime.now()
            clip_id = self._generate_clip_id(trigger_time)

            # The clip covers the last ``pre_event_seconds`` BEFORE the button
            # press (default 30s) plus ``post_event_seconds`` after it
            # (default 0: nothing recorded after the press).
            pre_seconds = self._config.buffer.pre_event_seconds
            post_seconds = self._config.buffer.post_event_seconds
            duration = pre_seconds + post_seconds
            start_time = trigger_time - timedelta(seconds=pre_seconds)
            end_time = trigger_time + timedelta(seconds=post_seconds)

            self._logger.info(
                "Trigger registered",
                clip_id=clip_id,
                start=start_time.isoformat(),
                end=end_time.isoformat(),
                duration=duration,
            )

            # The segment that contains the press is still being written by
            # FFmpeg. Wait for it to be closed (plus a small margin) so the
            # final seconds before the press are fully on disk. With
            # post_event_seconds = 0 this is the only wait.
            wait_seconds = post_seconds + self._config.buffer.segment_seconds + 1
            self._logger.info(f"Waiting {wait_seconds}s for the last segment to close...")
            await asyncio.sleep(wait_seconds)

            # Find relevant segments
            segments = self._find_segments_for_range(start_time, end_time)
            if not segments:
                self._logger.warning("No segments found for clip", clip_id=clip_id)
                return

            self._logger.info(f"Found {len(segments)} segments for clip")

            # Create clip
            clip_path = await self._create_clip(clip_id, segments, start_time, end_time)
            if not clip_path:
                self._logger.error("Failed to create clip", clip_id=clip_id)
                return

            # Save metadata
            metadata = self._build_metadata(clip_id, clip_path, trigger_time, start_time, end_time)
            self._storage.save_metadata(clip_id, metadata)

            self._logger.info("Clip stored", clip_id=clip_id, path=str(clip_path))
            self._logger.info("Clip creation completed", clip_id=clip_id)

        except Exception as e:
            self._logger.error("Clip creation failed", error=str(e))
        finally:
            self._processing = False
            if self._state.current == AgentState.CREATING_CLIP:
                self._state.set(AgentState.RECORDING)

    def _generate_clip_id(self, trigger_time: datetime) -> str:
        """Generate a unique clip ID based on timestamp and random component."""
        time_str = trigger_time.strftime("%Y%m%d%H%M%S")
        random_part = uuid.uuid4().hex[:6]
        return f"{time_str}_{random_part}"

    def _find_segments_for_range(
        self, start_time: datetime, end_time: datetime
    ) -> list[Path]:
        """Find buffer segments covering the requested time range.

        FFmpeg sets a segment's mtime when it closes the file, so mtime is
        effectively the segment's END time. The start is that minus the segment
        duration. A segment is kept when its estimated span overlaps the window.
        """
        segments = self._storage.get_buffer_segments()
        if not segments:
            return []

        seg_delta = timedelta(seconds=self._config.buffer.segment_seconds)

        result = []
        for seg in segments:
            seg_end = datetime.fromtimestamp(seg.stat().st_mtime)
            seg_start = seg_end - seg_delta
            # Overlap test between [seg_start, seg_end] and [start_time, end_time]
            if seg_end >= start_time and seg_start <= end_time:
                result.append(seg)

        return result

    async def _create_clip(
        self,
        clip_id: str,
        segments: list[Path],
        start_time: datetime,
        end_time: datetime,
    ) -> Optional[Path]:
        """Create a clip file from segments using the FFmpeg concat demuxer.

        The clip is trimmed with ``-t`` so it ends at ``end_time`` (the moment
        of the press when post_event_seconds = 0). Combined with ``-c:v copy``
        this needs no re-encoding. The audio stream is never mapped, so it is
        not even decoded.
        """
        if not segments:
            return None

        # Segments are cut on keyframes, so the first one starts a bit before
        # ``start_time``. Start the clip at that segment's beginning (exact, no
        # re-encode) and stop exactly at ``end_time``: the clip may carry up to
        # one segment of extra footage at the START, but never runs past the
        # button press.
        seg_delta = timedelta(seconds=self._config.buffer.segment_seconds)
        first_seg_start = datetime.fromtimestamp(segments[0].stat().st_mtime) - seg_delta
        duration = (end_time - min(first_seg_start, start_time)).total_seconds()
        duration = max(duration, 1.0)

        # Build concat file list
        concat_file = self._storage.buffer_path / f"concat_{clip_id}.txt"
        with open(concat_file, "w", encoding="utf-8") as f:
            for seg in segments:
                f.write(f"file '{seg.absolute()}'\n")

        # Output filename
        date_str = start_time.strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"{date_str}_{clip_id}.mp4"
        output_path = self._storage.clips_path / filename

        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel", "warning",
            "-nostdin",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_file),
            "-t", f"{duration:.3f}",  # ends at the press (+ post, if any)
            "-map", "0:v:0",          # video only - audio is never decoded
            "-an",
            "-c:v", "copy",           # no re-encode
            "-movflags", "+faststart",
            "-y",
            str(output_path),
        ]

        self._logger.info("Creating clip with FFmpeg", clip_id=clip_id, segments=len(segments))

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=60)

            if process.returncode != 0:
                self._logger.error(
                    "FFmpeg clip creation failed",
                    clip_id=clip_id,
                    stderr=stderr.decode("utf-8", errors="replace"),
                )
                return None

            # Clean up concat file
            concat_file.unlink(missing_ok=True)

            self._logger.info("Clip file created", clip_id=clip_id, size=output_path.stat().st_size)
            return output_path

        except asyncio.TimeoutError:
            self._logger.error("Clip creation timed out", clip_id=clip_id)
            concat_file.unlink(missing_ok=True)
            return None
        except Exception as e:
            self._logger.error("Clip creation error", clip_id=clip_id, error=str(e))
            concat_file.unlink(missing_ok=True)
            return None

    def _probe_duration(self, clip_path: Path) -> float:
        """Read the real duration of the produced clip with ffprobe."""
        try:
            out = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "csv=p=0", str(clip_path)],
                capture_output=True, text=True, timeout=15,
            )
            return round(float(out.stdout.strip()), 3)
        except Exception:
            return float(self._config.buffer.pre_event_seconds + self._config.buffer.post_event_seconds)

    def _build_metadata(
        self,
        clip_id: str,
        clip_path: Path,
        trigger_time: datetime,
        start_time: datetime,
        end_time: datetime,
    ) -> dict:
        """Build metadata for a clip."""
        return {
            "id": clip_id,
            "filename": clip_path.name,
            "createdAt": trigger_time.isoformat(),
            # Measured from the file itself, not assumed from the config.
            "duration": self._probe_duration(clip_path),
            "size": clip_path.stat().st_size,
            "triggerTime": trigger_time.isoformat(),
            "startTime": start_time.isoformat(),
            "endTime": end_time.isoformat(),
        }

    def get_clip_info(self, clip_id: str) -> Optional[dict]:
        """Get information about a specific clip."""
        metadata = self._storage.get_metadata(clip_id)
        if not metadata:
            return None

        clip_path = self._storage.get_clip_path(clip_id)
        if not clip_path or not clip_path.exists():
            return None

        return metadata

    def list_clips(self, start_time: Optional[str] = None, end_time: Optional[str] = None) -> list[dict]:
        """List all clips, optionally filtered by time range."""
        all_metadata = self._storage.get_all_metadata()

        if start_time:
            all_metadata = [m for m in all_metadata if m.get("triggerTime", "") >= start_time]
        if end_time:
            all_metadata = [m for m in all_metadata if m.get("triggerTime", "") <= end_time]

        # Sort by trigger time descending
        all_metadata.sort(key=lambda m: m.get("triggerTime", ""), reverse=True)
        return all_metadata

    def delete_clip(self, clip_id: str) -> bool:
        """Delete a clip by ID."""
        return self._storage.delete_clip(clip_id)
