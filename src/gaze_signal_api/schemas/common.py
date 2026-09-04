from __future__ import annotations

from datetime import UTC, datetime
from enum import IntEnum, StrEnum


def utc_now() -> datetime:
    return datetime.now(UTC)


class GazeZone(StrEnum):
    CENTER = "center"
    LEFT = "left"
    RIGHT = "right"
    UP = "up"
    DOWN = "down"
    AWAY = "away"
    UNKNOWN = "unknown"


class SignalState(StrEnum):
    SCREEN_FACING = "screen_facing"
    LOOKING_AWAY = "looking_away"
    FACE_MISSING = "face_missing"
    UNKNOWN = "unknown"


class SessionStatus(StrEnum):
    CREATED = "created"
    RUNNING = "running"
    STOPPED = "stopped"
    FAILED = "failed"


class CalibrationPattern(IntEnum):
    FIVE = 5
    NINE = 9
