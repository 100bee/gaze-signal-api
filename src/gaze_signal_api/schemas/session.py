from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from gaze_signal_api.schemas.common import GazeZone, SessionStatus, utc_now


class SessionCreate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "consent_given": True,
                "camera_index": 0,
                "frame_width": 640,
                "frame_height": 480,
                "target_fps": 15,
                "screen_width": 1512,
                "screen_height": 982,
                "yolo_enabled": False,
                "calibration_id": None,
            }
        }
    )

    consent_given: bool
    camera_index: int = Field(default=0, ge=0, le=32)
    frame_width: int = Field(default=640, ge=160, le=3840)
    frame_height: int = Field(default=480, ge=120, le=2160)
    target_fps: float = Field(default=15.0, ge=1.0, le=60.0)
    screen_width: int | None = Field(default=None, ge=320, le=16_384)
    screen_height: int | None = Field(default=None, ge=240, le=16_384)
    yolo_enabled: bool = False
    calibration_id: UUID | None = None

    @model_validator(mode="after")
    def validate_screen_geometry(self) -> SessionCreate:
        if (self.screen_width is None) != (self.screen_height is None):
            raise ValueError("screen_width and screen_height must be provided together")
        return self


class SessionRead(SessionCreate):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "8bf3de9a-f0d8-45c2-a719-07bcb8962fb4",
                "status": "created",
                "consent_given": True,
                "camera_index": 0,
                "frame_width": 640,
                "frame_height": 480,
                "target_fps": 15.0,
                "screen_width": 1512,
                "screen_height": 982,
                "yolo_enabled": False,
                "calibration_id": None,
                "created_at": "2026-09-04T01:20:00Z",
                "started_at": None,
                "stopped_at": None,
                "failure_code": None,
            }
        },
    )

    id: UUID
    status: SessionStatus
    created_at: datetime = Field(default_factory=utc_now)
    started_at: datetime | None = None
    stopped_at: datetime | None = None
    failure_code: str | None = None


class SessionPage(BaseModel):
    items: list[SessionRead]
    total: int
    limit: int
    offset: int


class SessionSummary(BaseModel):
    session_id: UUID
    session_duration_seconds: float = Field(ge=0.0)
    detected_duration_seconds: float = Field(ge=0.0)
    screen_facing_ratio: float = Field(ge=0.0, le=1.0)
    looking_away_ratio: float = Field(ge=0.0, le=1.0)
    face_missing_ratio: float = Field(ge=0.0, le=1.0)
    unknown_ratio: float = Field(ge=0.0, le=1.0)
    gaze_zone_distribution: dict[GazeZone, float]
    away_event_count: int = Field(ge=0)
    total_away_duration_seconds: float = Field(ge=0.0)
    longest_away_duration_seconds: float = Field(ge=0.0)
    average_away_duration_seconds: float = Field(ge=0.0)
    phone_visible_duration_seconds: float = Field(ge=0.0)
    blink_count: int = Field(ge=0)
    average_processing_latency_ms: float = Field(ge=0.0)
    effective_fps: float = Field(ge=0.0)
