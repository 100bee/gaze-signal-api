from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Validated application settings.

    Environment variables use the ``GAZE_SIGNAL_`` prefix. Raw-frame storage is
    intentionally rejected; this MVP has no implementation path that writes frames.
    """

    model_config = SettingsConfigDict(
        env_prefix="GAZE_SIGNAL_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "GazeSignal API"
    database_url: str = "sqlite:///./data/gaze_signal_api.db"
    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)
    log_level: str = "INFO"
    allowed_origins: list[str] = [
        "http://127.0.0.1:8000",
        "http://localhost:8000",
    ]

    camera_index: int = Field(default=0, ge=0, le=32)
    frame_width: int = Field(default=640, ge=160, le=3840)
    frame_height: int = Field(default=480, ge=120, le=2160)
    target_fps: float = Field(default=15.0, ge=1.0, le=60.0)
    camera_reconnect_attempts: int = Field(default=3, ge=0, le=20)

    face_model_path: Path = Path("models/face_landmarker.task")
    face_detection_confidence: float = Field(default=0.55, ge=0.0, le=1.0)
    gaze_confidence_threshold: float = Field(default=0.45, ge=0.0, le=1.0)
    blink_ear_threshold: float = Field(default=0.20, gt=0.0, lt=1.0)
    head_yaw_away_degrees: float = Field(default=30.0, ge=5.0, le=90.0)
    head_pitch_away_degrees: float = Field(default=25.0, ge=5.0, le=90.0)

    yolo_enabled: bool = False
    yolo_model_path: str = "models/yolo11n.pt"
    yolo_confidence: float = Field(default=0.45, ge=0.0, le=1.0)
    yolo_every_n_frames: int = Field(default=10, ge=1, le=300)

    ema_alpha: float = Field(default=0.35, gt=0.0, le=1.0)
    debounce_ms: int = Field(default=350, ge=0, le=10_000)
    away_min_duration_ms: int = Field(default=1000, ge=0, le=60_000)
    event_batch_size: int = Field(default=15, ge=1, le=300)
    store_raw_frames: bool = False

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        normalized = value.upper()
        if normalized not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError("must be a standard Python log level")
        return normalized

    @model_validator(mode="after")
    def reject_raw_frame_storage(self) -> Settings:
        if self.store_raw_frames:
            raise ValueError("raw frame storage is not supported by this privacy-first MVP")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
