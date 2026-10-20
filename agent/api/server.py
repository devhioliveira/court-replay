"""Internal API server for the Python agent with HMAC authentication."""
import asyncio
import hashlib
import hmac
import json
import time
from datetime import datetime
from typing import Optional

from aiohttp import web

from agent.config import Config
from agent.logger import ContextLogger
from agent.state import AgentState, StateManager
from agent.clip_manager.manager import ClipManager
from agent.ffmpeg.manager import FFmpegManager


@web.middleware
async def hmac_middleware(request: web.Request, handler):
    """Verify HMAC signature from the Node.js server on every request."""
    config: Config = request.app["config"]

    # Health endpoint still requires auth (Node is the only caller)
    auth_header = request.headers.get("X-Auth-Signature", "")
    timestamp = request.headers.get("X-Auth-Timestamp", "")
    nonce = request.headers.get("X-Auth-Nonce", "")

    if not auth_header or not timestamp or not nonce:
        return web.json_response({"error": "Missing authentication headers"}, status=401)

    # Reject replayed/stale requests
    try:
        ts = int(timestamp)
    except (ValueError, TypeError):
        return web.json_response({"error": "Invalid timestamp"}, status=401)

    tolerance = config.server.timestamp_tolerance
    if abs(time.time() * 1000 - ts) > tolerance:
        return web.json_response({"error": "Timestamp out of tolerance"}, status=401)

    # Read the raw body once (aiohttp caches it for the handler)
    body = await request.read()

    # Signed payload must match the Node.js side exactly:
    #   method|path+query|timestamp|nonce|hex(body)
    signed_path = request.path_qs
    payload = f"{request.method}|{signed_path}|{timestamp}|{nonce}|{body.hex()}"
    expected = hmac.new(
        config.server.shared_secret.encode(),
        payload.encode(),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(auth_header, expected):
        return web.json_response({"error": "Invalid signature"}, status=401)

    return await handler(request)


class APIServer:
    """Internal HTTP API server for the Python agent."""

    def __init__(
        self,
        config: Config,
        state: StateManager,
        clip_manager: ClipManager,
        ffmpeg: FFmpegManager,
        logger: ContextLogger,
    ):
        self._config = config
        self._state = state
        self._clip_manager = clip_manager
        self._ffmpeg = ffmpeg
        self._logger = logger
        self._app: Optional[web.Application] = None
        self._runner: Optional[web.AppRunner] = None

    async def start(self):
        """Start the API server."""
        self._app = web.Application(middlewares=[hmac_middleware])
        self._app["config"] = self._config
        self._setup_routes()

        self._runner = web.AppRunner(self._app)
        await self._runner.setup()

        site = web.TCPSite(
            self._runner,
            self._config.server.host,
            self._config.server.port,
        )
        await site.start()
        self._logger.info(
            "API server started",
            host=self._config.server.host,
            port=self._config.server.port,
        )

    async def stop(self):
        """Stop the API server."""
        if self._runner:
            await self._runner.cleanup()
        self._logger.info("API server stopped")

    def _setup_routes(self):
        """Setup API routes."""
        self._app.router.add_get("/health", self._handle_health)
        self._app.router.add_get("/api/internal/status", self._handle_status)
        self._app.router.add_get("/api/internal/clips", self._handle_list_clips)
        self._app.router.add_get("/api/internal/clips/{id}", self._handle_get_clip)
        self._app.router.add_get("/api/internal/clips/{id}/download", self._handle_download)
        self._app.router.add_post("/api/internal/clips/{id}/delete", self._handle_delete)
        self._app.router.add_post("/api/internal/trigger", self._handle_trigger)

    async def _handle_health(self, request: web.Request) -> web.Response:
        """Health check endpoint."""
        return web.json_response({
            "status": "ok",
            "state": self._state.current.value,
            "ffmpegRunning": self._ffmpeg.is_running,
            "timestamp": datetime.now().isoformat(),
        })

    async def _handle_status(self, request: web.Request) -> web.Response:
        """Get detailed agent status."""
        storage = self._clip_manager._storage
        usage = storage.get_storage_usage()

        return web.json_response({
            "state": self._state.current.value,
            "ffmpegRunning": self._ffmpeg.is_running,
            "storage": usage,
            "bufferSegments": len(storage.get_buffer_segments()),
            "timestamp": datetime.now().isoformat(),
        })

    async def _handle_list_clips(self, request: web.Request) -> web.Response:
        """List all clips with optional time filtering."""
        start_time = request.query.get("start")
        end_time = request.query.get("end")

        clips = self._clip_manager.list_clips(start_time, end_time)
        return web.json_response({"clips": clips, "count": len(clips)})

    async def _handle_get_clip(self, request: web.Request) -> web.Response:
        """Get information about a specific clip."""
        clip_id = request.match_info["id"]
        clip_info = self._clip_manager.get_clip_info(clip_id)

        if not clip_info:
            return web.json_response({"error": "Clip not found"}, status=404)

        return web.json_response(clip_info)

    async def _handle_download(self, request: web.Request) -> web.StreamResponse:
        """Stream a clip file for download."""
        clip_id = request.match_info["id"]
        clip_path = self._clip_manager._storage.get_clip_path(clip_id)

        if not clip_path or not clip_path.exists():
            return web.json_response({"error": "Clip not found"}, status=404)

        # Support HTTP Range requests
        range_header = request.headers.get("Range")
        file_size = clip_path.stat().st_size

        if range_header:
            # Parse range header
            range_str = range_header.replace("bytes=", "")
            parts = range_str.split("-")
            start = int(parts[0]) if parts[0] else 0
            end = int(parts[1]) if parts[1] else file_size - 1

            if start >= file_size or end >= file_size or start > end:
                return web.Response(status=416)

            content_length = end - start + 1
            status = 206
        else:
            start = 0
            end = file_size - 1
            content_length = file_size
            status = 200

        response = web.StreamResponse(
            status=status,
            headers={
                "Content-Type": "video/mp4",
                "Content-Length": str(content_length),
                "Content-Disposition": f'attachment; filename="{clip_path.name}"',
                "Accept-Ranges": "bytes",
            },
        )

        if range_header:
            response.headers["Content-Range"] = f"bytes {start}-{end}/{file_size}"

        await response.prepare(request)

        # Stream file in chunks
        chunk_size = 64 * 1024  # 64KB chunks
        with open(clip_path, "rb") as f:
            f.seek(start)
            remaining = content_length
            while remaining > 0:
                chunk_size = min(chunk_size, remaining)
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                await response.write(chunk)
                remaining -= len(chunk)

        await response.write_eof()
        return response

    async def _handle_delete(self, request: web.Request) -> web.Response:
        """Delete a clip."""
        clip_id = request.match_info["id"]
        success = self._clip_manager.delete_clip(clip_id)

        if not success:
            return web.json_response({"error": "Clip not found"}, status=404)

        self._logger.info("Clip deleted", clip_id=clip_id)
        return web.json_response({"success": True, "id": clip_id})

    async def _handle_trigger(self, request: web.Request) -> web.Response:
        """Manually trigger a clip creation."""
        self._logger.info("Manual trigger received via API")
        asyncio.create_task(self._clip_manager.handle_trigger())
        return web.json_response({"success": True, "message": "Trigger received"})
