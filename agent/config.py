"""Configuration management for the agent."""
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


def _camel_to_snake(name: str) -> str:
    """Convert camelCase JSON keys to snake_case dataclass attributes."""
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def load_dotenv(path: str = ".env") -> None:
    """Minimal .env loader (no external dependency).

    Real environment variables always win, so systemd/env-file setups are
    not overridden by a stray .env in the working directory.
    """
    env_path = Path(path)
    if not env_path.exists():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


@dataclass
class CameraConfig:
    name: str = "DAFU-CAMERA"
    ip: str = "192.168.3.100"
    user: str = ""
    password: str = ""
    rtsp_url: str = ""


@dataclass
class BufferConfig:
    segment_seconds: int = 2
    pre_event_seconds: int = 15
    post_event_seconds: int = 15
    clip_duration_seconds: int = 30
    max_buffer_segments: int = 60


@dataclass
class StorageConfig:
    base_path: str = "./storage"
    buffer_path: str = "./storage/buffer"
    clips_path: str = "./storage/clips"
    metadata_path: str = "./storage/metadata"
    max_storage_gb: int = 50


@dataclass
class ServerConfig:
    host: str = "127.0.0.1"
    port: int = 8765
    shared_secret: str = ""
    timeout: int = 30000
    timestamp_tolerance: int = 300000


@dataclass
class CleanupConfig:
    enabled: bool = True
    hour: int = 0
    minute: int = 0
    timezone: str = "America/Sao_Paulo"


@dataclass
class LoggingConfig:
    level: str = "info"
    format: str = "structured"
    file: str = "./logs/agent.log"


@dataclass
class Config:
    camera: CameraConfig = field(default_factory=CameraConfig)
    buffer: BufferConfig = field(default_factory=BufferConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    server: ServerConfig = field(default_factory=ServerConfig)
    cleanup: CleanupConfig = field(default_factory=CleanupConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    agent_simulate: bool = False
    timezone: str = "America/Sao_Paulo"

    @classmethod
    def load(cls, path: str = "config.json") -> "Config":
        # Load .env first so its values are available to _load_env()
        load_dotenv()

        config = cls()
        config_path = Path(path)

        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            config._merge_dict(data)

        # Override with environment variables
        config._load_env()

        # Make "now" independent of the OS timezone (see agent/timeutil.py).
        from agent import timeutil
        timeutil.configure(config.timezone)
        return config

    def _merge_section(self, section_obj, data: dict) -> None:
        """Apply JSON keys (camelCase or snake_case) onto a dataclass section."""
        for key, value in data.items():
            attr = _camel_to_snake(key)
            if hasattr(section_obj, attr):
                setattr(section_obj, attr, value)

    def _merge_dict(self, data: dict):
        if "camera" in data:
            self._merge_section(self.camera, data["camera"])
        if "buffer" in data:
            self._merge_section(self.buffer, data["buffer"])
        if "storage" in data:
            self._merge_section(self.storage, data["storage"])
        if "notebookAgent" in data:
            na = data["notebookAgent"]
            self.server.host = na.get("host", self.server.host)
            self.server.port = na.get("port", self.server.port)
            self.server.shared_secret = na.get("sharedSecret", self.server.shared_secret)
            self.server.timeout = na.get("timeout", self.server.timeout)
        if "security" in data:
            sec = data["security"]
            self.server.timestamp_tolerance = sec.get(
                "timestampTolerance", self.server.timestamp_tolerance
            )
        if "cleanup" in data:
            self._merge_section(self.cleanup, data["cleanup"])
        if "logging" in data:
            self._merge_section(self.logging, data["logging"])

    def _load_env(self):
        if v := os.getenv("CAMERA_USER"):
            self.camera.user = v
        if v := os.getenv("CAMERA_PASSWORD"):
            self.camera.password = v
        if v := os.getenv("CAMERA_RTSP_URL"):
            self.camera.rtsp_url = v
        if v := os.getenv("NOTEBOOK_SHARED_SECRET"):
            self.server.shared_secret = v
        if v := os.getenv("AGENT_PORT"):
            self.server.port = int(v)
        if v := os.getenv("AGENT_HOST"):
            self.server.host = v
        if v := os.getenv("AGENT_SIMULATE"):
            self.agent_simulate = v.lower() in ("true", "1", "yes")
        if v := os.getenv("TZ"):
            self.timezone = v
            self.cleanup.timezone = v
