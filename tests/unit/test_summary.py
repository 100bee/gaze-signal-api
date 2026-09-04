from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from gaze_signal_api.analytics.summary import calculate_summary
from gaze_signal_api.schemas.analysis import AnalysisEvent
from gaze_signal_api.schemas.common import GazeZone, SessionStatus, SignalState
from gaze_signal_api.schemas.session import SessionRead


def test_summary_integrates_state_durations_and_events() -> None:
    session_id = uuid4()
    start = datetime(2026, 1, 1, tzinfo=UTC)
    session = SessionRead(
        id=session_id,
        consent_given=True,
        camera_index=0,
        frame_width=640,
        frame_height=480,
        target_fps=2,
        yolo_enabled=False,
        status=SessionStatus.STOPPED,
        created_at=start,
        started_at=start,
        stopped_at=start + timedelta(seconds=10),
    )
    states = [
        (0, SignalState.SCREEN_FACING, GazeZone.CENTER, False, False),
        (4, SignalState.LOOKING_AWAY, GazeZone.AWAY, True, False),
        (7, SignalState.FACE_MISSING, GazeZone.UNKNOWN, True, True),
        (9, SignalState.UNKNOWN, GazeZone.UNKNOWN, False, False),
    ]
    events = [
        AnalysisEvent(
            session_id=session_id,
            timestamp=start + timedelta(seconds=second),
            face_present=state != SignalState.FACE_MISSING,
            gaze_zone=zone,
            state=state,
            phone_visible=phone,
            blink_detected=blink,
            confidence=0.8,
            processing_latency_ms=20,
        )
        for second, state, zone, phone, blink in states
    ]
    summary = calculate_summary(session, events)
    assert summary.session_duration_seconds == 10
    assert summary.screen_facing_ratio == pytest.approx(0.4)
    assert summary.looking_away_ratio == pytest.approx(0.3)
    assert summary.face_missing_ratio == pytest.approx(0.2)
    assert summary.unknown_ratio == pytest.approx(0.1)
    assert summary.away_event_count == 1
    assert summary.total_away_duration_seconds == pytest.approx(3.0)
    assert summary.phone_visible_duration_seconds == pytest.approx(5.0)
    assert summary.blink_count == 1
    assert summary.average_processing_latency_ms == 20
    assert summary.effective_fps == pytest.approx(0.4)


def test_unstarted_session_has_zero_duration() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    session = SessionRead(
        id=uuid4(),
        consent_given=False,
        status=SessionStatus.CREATED,
        camera_index=0,
        frame_width=640,
        frame_height=480,
        target_fps=15,
        yolo_enabled=False,
        created_at=now,
    )
    summary = calculate_summary(session, [], now=now + timedelta(hours=1))
    assert summary.session_duration_seconds == 0
