"""Timezone-safe time helpers.

The agent must not depend on the operating system's idea of the local zone:
on Windows a ``TZ=America/Sao_Paulo`` environment variable is not understood by
the C runtime and silently turns "now" into UTC (3 hours ahead of Brasilia).
So every timestamp is created *aware*, in the zone configured via ``TZ`` /
``config.timezone``, and serialised with its offset (e.g. ``-03:00``). Browsers
then show the right local time no matter where they are.
"""
import re
from datetime import datetime, tzinfo
from typing import Optional

try:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
except ImportError:  # pragma: no cover - Python < 3.9
    ZoneInfo = None
    ZoneInfoNotFoundError = Exception

_tz: Optional[tzinfo] = None
_TIME_OF_DAY = re.compile(r"^\s*(\d{1,2}):(\d{2})\s*$")


def configure(name: str, logger=None) -> None:
    """Select the timezone by IANA name (e.g. America/Sao_Paulo)."""
    global _tz
    try:
        _tz = ZoneInfo(name)
    except Exception as e:  # unknown zone, or tzdata missing on Windows
        _tz = None
        if logger:
            logger.warning(
                "Timezone unavailable, using the system zone. On Windows run: "
                "pip install tzdata",
                timezone=name, error=str(e),
            )


def now() -> datetime:
    return datetime.now(_tz) if _tz else datetime.now().astimezone()


def from_timestamp(ts: float) -> datetime:
    return datetime.fromtimestamp(ts, _tz) if _tz else datetime.fromtimestamp(ts).astimezone()


def parse_iso(value: str) -> Optional[datetime]:
    """Parse an ISO timestamp; a value without offset is read as local time."""
    try:
        dt = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_tz) if _tz else dt.astimezone()
    return dt.astimezone(_tz) if _tz else dt


def parse_time_of_day(value: Optional[str]) -> Optional[int]:
    """'HH:MM' -> minutes since midnight, or None when not in that format."""
    if not value:
        return None
    m = _TIME_OF_DAY.match(value)
    if not m:
        return None
    h, mi = int(m.group(1)), int(m.group(2))
    if h > 23 or mi > 59:
        return None
    return h * 60 + mi
