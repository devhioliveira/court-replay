"""Storage manager - owns every file the agent writes to disk.

Three things live under ``storage/``:

    buffer/     rotating 2s FFmpeg segments (segment_YYYYMMDD_HHMMSS.ts)
    clips/      final .mp4 clips produced by ClipManager
    metadata/   one <clip_id>.json per clip

This module was rebuilt after being lost to an over-broad ``.gitignore``
rule (see the note in the project's ``.gitignore``). Its public interface
is dictated by every other module that already depends on it
(``__main__.py``, ``clip_manager/manager.py``, ``cleanup/scheduler.py``,
``api/server.py``) - keep this file's method names and return shapes in
sync with those call sites if you change anything here.
"""
import json
import re
import shutil
from pathlib import Path
from typing import Optional

from agent.config import Config

# Only files that actually look like FFmpeg segments are ever touched by
# the buffer-pruning logic - this keeps stray files (e.g. a half-written
# concat_<clip_id>.txt from ClipManager) out of harm's way.
SEGMENT_GLOB = "segment_*.ts"

# Clip IDs are generated internally (see ClipManager._generate_clip_id) as
# "<14-digit timestamp>_<6 hex chars>", but every public API also accepts
# one coming from the Node.js panel over HTTP. Validate it before ever
# turning it into a path, so a malicious/mistaken ID can't escape
# metadata_path/clips_path (defense in depth - the Node.js side already
# rejects anything outside [a-zA-Z0-9_-] in server/src/routes/api.js).
_SAFE_CLIP_ID = re.compile(r"^[a-zA-Z0-9_-]+$")


class StorageManager:
    """Manages the buffer, clips and metadata directories on disk."""

    def __init__(self, config: Config):
        self._config = config
        self.base_path = Path(config.storage.base_path)
        self.buffer_path = Path(config.storage.buffer_path)
        self.clips_path = Path(config.storage.clips_path)
        self.metadata_path = Path(config.storage.metadata_path)

    async def initialize(self) -> None:
        """Create the storage directory tree if it doesn't exist yet."""
        for path in (self.base_path, self.buffer_path, self.clips_path, self.metadata_path):
            path.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Buffer segments
    # ------------------------------------------------------------------

    def get_buffer_segments(self) -> list[Path]:
        """Return buffer segments, oldest first.

        Sorted by mtime (the time FFmpeg closed the file), which is the
        same ordering ClipManager relies on when it maps a segment back
        to the time range it covers.
        """
        if not self.buffer_path.exists():
            return []
        segments = [p for p in self.buffer_path.glob(SEGMENT_GLOB) if p.is_file()]
        segments.sort(key=lambda p: p.stat().st_mtime)
        return segments

    def cleanup_old_segments(self, max_segments: int) -> int:
        """Keep only the newest ``max_segments`` buffer segments.

        Called once a second from the main loop (see ``agent/__main__.py``)
        so the buffer never grows unbounded even if FFmpeg falls behind,
        gets restarted, or a clip takes a while to be assembled.
        """
        segments = self.get_buffer_segments()
        excess = len(segments) - max_segments
        if excess <= 0:
            return 0

        deleted = 0
        for segment in segments[:excess]:
            try:
                segment.unlink(missing_ok=True)
                deleted += 1
            except OSError:
                pass
        return deleted

    # ------------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------------

    def _metadata_file(self, clip_id: str) -> Optional[Path]:
        if not _SAFE_CLIP_ID.match(clip_id):
            return None
        return self.metadata_path / f"{clip_id}.json"

    def save_metadata(self, clip_id: str, metadata: dict) -> None:
        metadata_file = self._metadata_file(clip_id)
        if metadata_file is None:
            raise ValueError(f"Invalid clip id: {clip_id!r}")
        metadata_file.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def get_metadata(self, clip_id: str) -> Optional[dict]:
        metadata_file = self._metadata_file(clip_id)
        if metadata_file is None or not metadata_file.exists():
            return None
        try:
            return json.loads(metadata_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

    def get_all_metadata(self) -> list[dict]:
        if not self.metadata_path.exists():
            return []
        result = []
        for metadata_file in self.metadata_path.glob("*.json"):
            try:
                result.append(json.loads(metadata_file.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, OSError):
                continue
        return result

    # ------------------------------------------------------------------
    # Clips
    # ------------------------------------------------------------------

    def get_clip_path(self, clip_id: str) -> Optional[Path]:
        """Resolve a clip ID to its .mp4 path, via the clip's own metadata
        (so the actual on-disk filename is never guessed)."""
        metadata = self.get_metadata(clip_id)
        if not metadata or "filename" not in metadata:
            return None
        clip_path = self.clips_path / metadata["filename"]
        return clip_path if clip_path.exists() else None

    def delete_clip(self, clip_id: str) -> bool:
        """Delete a clip's .mp4 and its metadata. Returns False if the
        clip was already gone (e.g. double delete)."""
        metadata = self.get_metadata(clip_id)
        if not metadata:
            return False

        filename = metadata.get("filename")
        if filename:
            (self.clips_path / filename).unlink(missing_ok=True)

        metadata_file = self._metadata_file(clip_id)
        if metadata_file is not None:
            metadata_file.unlink(missing_ok=True)

        return True

    def cleanup_daily(self) -> dict:
        """Delete every clip and every metadata file. Runs once a day at
        midnight (see ``cleanup/scheduler.py``).

        Buffer segments are left untouched here - they are pruned
        continuously by ``cleanup_old_segments`` and FFmpeg may still be
        writing to the newest ones.
        """
        deleted_clips = 0
        if self.clips_path.exists():
            for clip_file in self.clips_path.iterdir():
                if clip_file.is_file():
                    clip_file.unlink(missing_ok=True)
                    deleted_clips += 1

        deleted_metadata = 0
        if self.metadata_path.exists():
            for metadata_file in self.metadata_path.glob("*.json"):
                metadata_file.unlink(missing_ok=True)
                deleted_metadata += 1

        return {"deletedClips": deleted_clips, "deletedMetadata": deleted_metadata}

    # ------------------------------------------------------------------
    # Usage
    # ------------------------------------------------------------------

    def get_storage_usage(self) -> dict:
        """Summary used by GET /api/internal/status (and, from there, the
        Node.js panel's /api/status)."""
        used_bytes = self._dir_size(self.base_path)
        max_bytes = self._config.storage.max_storage_gb * 1024 ** 3

        try:
            _total, _used, disk_free = shutil.disk_usage(self.base_path)
        except OSError:
            disk_free = 0

        clips_count = 0
        if self.clips_path.exists():
            clips_count = sum(1 for p in self.clips_path.glob("*.mp4"))

        return {
            "usedBytes": used_bytes,
            "usedGb": round(used_bytes / 1024 ** 3, 2),
            "maxGb": self._config.storage.max_storage_gb,
            "percentUsed": round((used_bytes / max_bytes) * 100, 1) if max_bytes else 0,
            "clipsCount": clips_count,
            "diskFreeGb": round(disk_free / 1024 ** 3, 2),
        }

    def _dir_size(self, path: Path) -> int:
        if not path.exists():
            return 0
        return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
