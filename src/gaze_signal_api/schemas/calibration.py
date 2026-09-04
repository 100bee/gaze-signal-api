from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from gaze_signal_api.schemas.common import utc_now


class CalibrationSample(BaseModel):
    """A derived gaze feature paired with a normalized screen target."""

    target_x: float = Field(ge=0.0, le=1.0)
    target_y: float = Field(ge=0.0, le=1.0)
    feature_x: float = Field(ge=-2.0, le=2.0)
    feature_y: float = Field(ge=-2.0, le=2.0)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    head_yaw: float | None = Field(default=None, ge=-180.0, le=180.0)
    head_pitch: float | None = Field(default=None, ge=-180.0, le=180.0)
    head_roll: float | None = Field(default=None, ge=-180.0, le=180.0)


class CalibrationCreate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "label": "MacBook desk setup",
                "pattern_points": 5,
                "camera_index": 0,
                "camera_width": 640,
                "camera_height": 480,
                "screen_width": 1512,
                "screen_height": 982,
                "samples": [
                    {
                        "target_x": 0.5,
                        "target_y": 0.5,
                        "feature_x": 0.51,
                        "feature_y": 0.49,
                        "confidence": 0.91,
                    },
                    {"target_x": 0.1, "target_y": 0.5, "feature_x": 0.31, "feature_y": 0.5},
                    {"target_x": 0.9, "target_y": 0.5, "feature_x": 0.69, "feature_y": 0.5},
                    {"target_x": 0.5, "target_y": 0.1, "feature_x": 0.5, "feature_y": 0.35},
                    {"target_x": 0.5, "target_y": 0.9, "feature_x": 0.5, "feature_y": 0.67},
                ],
            }
        }
    )

    label: str | None = Field(default=None, max_length=100)
    pattern_points: int = Field(default=5)
    camera_index: int = Field(ge=0, le=32)
    camera_width: int = Field(ge=160, le=3840)
    camera_height: int = Field(ge=120, le=2160)
    screen_width: int = Field(ge=320, le=16_384)
    screen_height: int = Field(ge=240, le=16_384)
    samples: list[CalibrationSample]

    @model_validator(mode="after")
    def validate_pattern(self) -> CalibrationCreate:
        if self.pattern_points not in {5, 9}:
            raise ValueError("pattern_points must be 5 or 9")
        targets = {(round(s.target_x, 3), round(s.target_y, 3)) for s in self.samples}
        if len(targets) < self.pattern_points:
            raise ValueError(f"at least {self.pattern_points} distinct targets are required")
        if len(self.samples) < self.pattern_points:
            raise ValueError("not enough calibration samples")
        return self


class CalibrationParameters(BaseModel):
    x_coefficients: tuple[float, float, float]
    y_coefficients: tuple[float, float, float]
    root_mean_squared_error: float = Field(ge=0.0)
    neutral_head_yaw: float = Field(default=0.0, ge=-180.0, le=180.0)
    neutral_head_pitch: float = Field(default=0.0, ge=-180.0, le=180.0)
    neutral_head_roll: float = Field(default=0.0, ge=-180.0, le=180.0)


class CalibrationRead(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "c4245575-7d9a-4ab2-88f3-ae93c4b1df36",
                "label": "MacBook desk setup",
                "pattern_points": 5,
                "camera_index": 0,
                "camera_width": 640,
                "camera_height": 480,
                "screen_width": 1512,
                "screen_height": 982,
                "parameters": {
                    "x_coefficients": [2.1, 0.02, -0.55],
                    "y_coefficients": [-0.01, 2.8, -0.88],
                    "root_mean_squared_error": 0.06,
                },
                "created_at": "2026-09-04T01:20:00Z",
            }
        },
    )

    id: UUID
    label: str | None
    pattern_points: int
    camera_index: int
    camera_width: int
    camera_height: int
    screen_width: int
    screen_height: int
    parameters: CalibrationParameters
    created_at: datetime = Field(default_factory=utc_now)


class CalibrationPage(BaseModel):
    items: list[CalibrationRead]
    total: int
    limit: int
    offset: int
