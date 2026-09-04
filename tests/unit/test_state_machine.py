from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from gaze_signal_api.analytics.state_machine import TemporalStateMachine
from gaze_signal_api.schemas.analysis import FrameSignals
from gaze_signal_api.schemas.common import GazeZone, SignalState

START = datetime(2026, 1, 1, tzinfo=UTC)


def signal(
    at_ms: int,
    *,
    face: bool = True,
    zone: GazeZone = GazeZone.CENTER,
    confidence: float = 0.9,
    available: bool = True,
) -> FrameSignals:
    return FrameSignals(
        timestamp=START + timedelta(milliseconds=at_ms),
        face_present=face,
        face_analysis_available=available,
        gaze_zone=zone,
        confidence=confidence,
    )


def test_debounce_and_away_minimum_duration() -> None:
    machine = TemporalStateMachine(
        uuid4(), confidence_threshold=0.5, debounce_ms=100, away_min_duration_ms=500
    )
    assert machine.update(signal(0))[0] == SignalState.UNKNOWN
    assert machine.update(signal(100))[0] == SignalState.SCREEN_FACING
    assert machine.update(signal(200, zone=GazeZone.AWAY))[0] == SignalState.SCREEN_FACING
    assert machine.update(signal(600, zone=GazeZone.AWAY))[0] == SignalState.SCREEN_FACING
    state, transition = machine.update(signal(700, zone=GazeZone.AWAY))
    assert state == SignalState.LOOKING_AWAY
    assert transition is not None
    assert transition.from_state == SignalState.SCREEN_FACING


def test_short_away_signal_does_not_change_state() -> None:
    machine = TemporalStateMachine(uuid4(), debounce_ms=100, away_min_duration_ms=500)
    machine.update(signal(0))
    machine.update(signal(100))
    machine.update(signal(200, zone=GazeZone.AWAY))
    state, _ = machine.update(signal(300, zone=GazeZone.CENTER))
    assert state == SignalState.SCREEN_FACING


def test_face_missing_and_analysis_unavailable_are_distinct() -> None:
    machine = TemporalStateMachine(uuid4(), debounce_ms=0, away_min_duration_ms=0)
    machine.update(signal(0, face=False))
    assert machine.update(signal(1, face=False))[0] == SignalState.FACE_MISSING

    machine.update(signal(2, face=False, available=False))
    state, _ = machine.update(signal(3, face=False, available=False))
    assert state == SignalState.UNKNOWN
