from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from gaze_signal_api.schemas.calibration import CalibrationParameters
from gaze_signal_api.schemas.common import SessionStatus, utc_now


class Base(DeclarativeBase):
    pass


class SessionRow(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    status: Mapped[str] = mapped_column(String(20), default=SessionStatus.CREATED.value)
    consent_given: Mapped[bool] = mapped_column(Boolean, nullable=False)
    camera_index: Mapped[int] = mapped_column(Integer, nullable=False)
    frame_width: Mapped[int] = mapped_column(Integer, nullable=False)
    frame_height: Mapped[int] = mapped_column(Integer, nullable=False)
    target_fps: Mapped[float] = mapped_column(Float, nullable=False)
    screen_width: Mapped[int | None] = mapped_column(Integer)
    screen_height: Mapped[int | None] = mapped_column(Integer)
    yolo_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    calibration_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("calibrations.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    stopped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_code: Mapped[str | None] = mapped_column(String(50))

    events: Mapped[list[AnalysisEventRow]] = relationship(
        cascade="all, delete-orphan", passive_deletes=True
    )
    transitions: Mapped[list[StateTransitionRow]] = relationship(
        cascade="all, delete-orphan", passive_deletes=True
    )


class AnalysisEventRow(Base):
    __tablename__ = "analysis_events"
    __table_args__ = (Index("ix_analysis_events_session_timestamp", "session_id", "timestamp"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False
    )
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    face_present: Mapped[bool] = mapped_column(Boolean, nullable=False)
    face_analysis_available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    gaze_zone: Mapped[str] = mapped_column(String(20), nullable=False)
    gaze_feature_x: Mapped[float | None] = mapped_column(Float)
    gaze_feature_y: Mapped[float | None] = mapped_column(Float)
    head_yaw: Mapped[float] = mapped_column(Float, nullable=False)
    head_pitch: Mapped[float] = mapped_column(Float, nullable=False)
    head_roll: Mapped[float] = mapped_column(Float, nullable=False)
    blink_detected: Mapped[bool] = mapped_column(Boolean, nullable=False)
    phone_visible: Mapped[bool] = mapped_column(Boolean, nullable=False)
    state: Mapped[str] = mapped_column(String(20), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    processing_latency_ms: Mapped[float] = mapped_column(Float, nullable=False)


class StateTransitionRow(Base):
    __tablename__ = "state_transitions"
    __table_args__ = (Index("ix_state_transitions_session_timestamp", "session_id", "timestamp"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False
    )
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    from_state: Mapped[str] = mapped_column(String(20), nullable=False)
    to_state: Mapped[str] = mapped_column(String(20), nullable=False)


class CalibrationRow(Base):
    __tablename__ = "calibrations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    label: Mapped[str | None] = mapped_column(String(100))
    pattern_points: Mapped[int] = mapped_column(Integer, nullable=False)
    camera_index: Mapped[int] = mapped_column(Integer, nullable=False)
    camera_width: Mapped[int] = mapped_column(Integer, nullable=False)
    camera_height: Mapped[int] = mapped_column(Integer, nullable=False)
    screen_width: Mapped[int] = mapped_column(Integer, nullable=False)
    screen_height: Mapped[int] = mapped_column(Integer, nullable=False)
    parameters_json: Mapped[str] = mapped_column(Text, nullable=False)
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    @property
    def parameters(self) -> CalibrationParameters:
        return CalibrationParameters.model_validate(json.loads(self.parameters_json))

    def set_parameters(self, value: CalibrationParameters | dict[str, Any]) -> None:
        if isinstance(value, CalibrationParameters):
            value = value.model_dump(mode="json")
        self.parameters_json = json.dumps(value, separators=(",", ":"))
