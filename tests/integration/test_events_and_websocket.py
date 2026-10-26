from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from gaze_signal_api.schemas.analysis import AnalysisEvent
from gaze_signal_api.schemas.common import GazeZone, SessionStatus, SignalState


def _create_session(client: TestClient) -> dict[str, object]:
    return client.post(
        "/sessions",
        json={
            "consent_given": True,
            "camera_index": 0,
            "frame_width": 640,
            "frame_height": 480,
            "target_fps": 15,
            "yolo_enabled": False,
        },
    ).json()


def _event(session_id: str, at: datetime) -> AnalysisEvent:
    return AnalysisEvent(
        session_id=UUID(session_id),
        timestamp=at,
        face_present=True,
        gaze_zone=GazeZone.CENTER,
        gaze_feature_x=0.5,
        gaze_feature_y=0.5,
        state=SignalState.SCREEN_FACING,
        confidence=0.9,
        processing_latency_ms=12.5,
    )


def test_database_event_round_trip_summary_and_cascade(client: TestClient) -> None:
    session = _create_session(client)
    session_id = session["id"]
    repository = client.app.state.repository
    started = datetime(2026, 1, 1, tzinfo=UTC)
    repository.set_session_status(session_id, SessionStatus.RUNNING, at=started)
    repository.add_events(
        [_event(session_id, started), _event(session_id, started + timedelta(seconds=1))]
    )
    repository.set_session_status(
        session_id, SessionStatus.STOPPED, at=started + timedelta(seconds=2)
    )

    response = client.get(f"/sessions/{session_id}/events?limit=1")
    assert response.status_code == 200
    assert response.json()["total"] == 2
    assert response.json()["items"][0]["gaze_feature_x"] == 0.5

    summary = client.get(f"/sessions/{session_id}/summary")
    assert summary.status_code == 200
    assert summary.json()["screen_facing_ratio"] == 1.0
    assert summary.json()["effective_fps"] == 1.0

    assert client.delete(f"/sessions/{session_id}").status_code == 204
    with repository.database.session_factory() as db:
        from sqlalchemy import func, select

        from gaze_signal_api.storage.models import AnalysisEventRow

        assert db.scalar(select(func.count()).select_from(AnalysisEventRow)) == 0


def test_restart_recovery_ends_session_at_last_event(client: TestClient) -> None:
    repository = client.app.state.repository
    started = datetime(2026, 1, 1, tzinfo=UTC)
    with_events = _create_session(client)["id"]
    without_events = _create_session(client)["id"]
    for session_id in (with_events, without_events):
        repository.set_session_status(session_id, SessionStatus.RUNNING, at=started)
    last = started + timedelta(minutes=30)
    repository.add_events([_event(with_events, started), _event(with_events, last)])

    assert repository.fail_stale_running_sessions() == 2

    recovered = repository.get_session(with_events)
    assert recovered.status == SessionStatus.FAILED
    assert recovered.failure_code == "server_restarted"
    assert recovered.stopped_at == last
    assert repository.get_session(without_events).stopped_at == started
    summary = client.get(f"/sessions/{with_events}/summary").json()
    assert summary["session_duration_seconds"] == 1800


def test_websocket_delivers_latest_analysis_event(client: TestClient) -> None:
    session = _create_session(client)
    session_id = session["id"]
    event = _event(session_id, datetime.now(UTC))
    with client.websocket_connect(f"/ws/sessions/{session_id}") as websocket:
        client.app.state.event_hub.publish(event)
        received = websocket.receive_json()
    assert received["session_id"] == session_id
    assert received["state"] == "screen_facing"
    assert received["gaze_zone"] == "center"


def test_websocket_rejects_unknown_session(client: TestClient) -> None:
    missing = "00000000-0000-0000-0000-000000000000"
    with (
        pytest.raises(WebSocketDisconnect) as exc_info,
        client.websocket_connect(f"/ws/sessions/{missing}"),
    ):
        pass
    assert exc_info.value.code == 4404


def test_websocket_rejects_unlisted_browser_origin(client: TestClient) -> None:
    session = _create_session(client)
    with (
        pytest.raises(WebSocketDisconnect) as exc_info,
        client.websocket_connect(
            f"/ws/sessions/{session['id']}",
            headers={"origin": "https://untrusted.example"},
        ),
    ):
        pass
    assert exc_info.value.code == 4403


def test_sqlite_wal_accepts_concurrent_event_batches(client: TestClient) -> None:
    session = _create_session(client)
    repository = client.app.state.repository
    started = datetime(2026, 1, 1, tzinfo=UTC)

    with repository.database.engine.connect() as connection:
        assert connection.exec_driver_sql("PRAGMA journal_mode").scalar_one().lower() == "wal"

    def write_batch(batch_index: int) -> None:
        repository.add_events(
            [
                _event(
                    str(session["id"]),
                    started + timedelta(milliseconds=batch_index * 100 + event_index),
                )
                for event_index in range(10)
            ]
        )

    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(write_batch, range(8)))

    assert len(repository.all_events(str(session["id"]))) == 80
