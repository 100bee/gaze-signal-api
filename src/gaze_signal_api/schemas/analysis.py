from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from gaze_signal_api.schemas.common import GazeZone, SignalState, utc_now


class HeadPose(BaseModel):
    yaw: float = 0.0
    pitch: float = 0.0
    roll: float = 0.0


class FrameSignals(BaseModel):
    """Derived values from one frame before temporal state classification."""

    timestamp: datetime = Field(default_factory=utc_now)
    face_present: bool
    face_analysis_available: bool = True
    gaze_zone: GazeZone = GazeZone.UNKNOWN
    gaze_feature_x: float | None = None
    gaze_feature_y: float | None = None
    head_yaw: float = 0.0
    head_pitch: float = 0.0
    head_roll: float = 0.0
    blink_detected: bool = False
    phone_visible: bool = False
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    processing_latency_ms: float = Field(default=0.0, ge=0.0)


class AnalysisEvent(FrameSignals):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "session_id": "8bf3de9a-f0d8-45c2-a719-07bcb8962fb4",
                "timestamp": "2026-09-04T01:23:45.123Z",
                "face_present": True,
                "face_analysis_available": True,
                "gaze_zone": "center",
                "gaze_feature_x": 0.51,
                "gaze_feature_y": 0.48,
                "head_yaw": -4.2,
                "head_pitch": 7.1,
                "head_roll": 0.8,
                "blink_detected": False,
                "phone_visible": False,
                "state": "screen_facing",
                "confidence": 0.87,
                "processing_latency_ms": 38.4,
            }
        }
    )

    session_id: UUID
    state: SignalState


class StateTransition(BaseModel):
    session_id: UUID
    timestamp: datetime
    from_state: SignalState
    to_state: SignalState


class EventPage(BaseModel):
    items: list[AnalysisEvent]
    total: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)
