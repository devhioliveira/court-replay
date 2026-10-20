"""Structured logging for the agent."""
import json
import logging
import os
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from agent import timeutil
from agent.config import LoggingConfig


class StructuredFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": timeutil.now().isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        if hasattr(record, "extra"):
            log_entry.update(record.extra)
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry, default=str, ensure_ascii=False)


class ContextLogger:
    def __init__(self, logger: logging.Logger):
        self._logger = logger

    def _log(self, level: int, msg: str, **kwargs):
        extra = {"extra": kwargs} if kwargs else {}
        self._logger.log(level, msg, extra=extra)

    def debug(self, msg: str, **kwargs):
        self._log(logging.DEBUG, msg, **kwargs)

    def info(self, msg: str, **kwargs):
        self._log(logging.INFO, msg, **kwargs)

    def warning(self, msg: str, **kwargs):
        self._log(logging.WARNING, msg, **kwargs)

    def warn(self, msg: str, **kwargs):
        self.warning(msg, **kwargs)

    def error(self, msg: str, **kwargs):
        self._log(logging.ERROR, msg, **kwargs)

    def critical(self, msg: str, **kwargs):
        self._log(logging.CRITICAL, msg, **kwargs)


def get_logger(config) -> ContextLogger:
    level = getattr(logging, config.logging.level.upper(), logging.INFO)
    logger = logging.getLogger("court_replay_agent")
    logger.setLevel(level)
    logger.handlers.clear()

    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(level)
    console.setFormatter(StructuredFormatter())
    logger.addHandler(console)

    # File handler
    log_path = Path(config.logging.file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(
        log_path, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(StructuredFormatter())
    logger.addHandler(file_handler)

    return ContextLogger(logger)
