from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from gaze_signal_api.capture.camera import OpenCVCapture
from gaze_signal_api.errors import ResourceUnavailableError
from gaze_signal_api.runtime.manager import SessionRuntimeManager
from gaze_signal_api.schemas.common import SessionStatus


class NoopRunner:
    def __init__(self, **_kwargs: Any) -> None:
        self.started = False

    def start(self) -> None:
        self.started = True

    def stop(self, timeout: float = 5.0) -> None:
        self.started = False

    @property
    def is_alive(self) -> bool:
        return self.started


class StuckRunner(NoopRunner):
    def stop(self, timeout: float = 5.0) -> None:
        pass


def _session_payload(consent: bool = True) -> dict[str, object]:
    return {
        "consent_given": consent,
        "camera_index": 0,
        "frame_width": 640,
        "frame_height": 480,
        "target_fps": 15,
        "yolo_enabled": False,
    }


def test_session_lifecycle_with_mocked_camera_runner(client: TestClient) -> None:
    app = client.app
    app.state.runtime = SessionRuntimeManager(
        app.state.repository,
        app.state.event_hub,
        app.state.settings,
        runner_factory=NoopRunner,
    )
    created = client.post("/sessions", json=_session_payload()).json()
    session_id = created["id"]
    assert created["status"] == "created"

    started = client.post(f"/sessions/{session_id}/start")
    assert started.status_code == 200
    assert started.json()["status"] == "running"

    duplicate = client.post(f"/sessions/{session_id}/start")
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "invalid_state_transition"

    stopped = client.post(f"/sessions/{session_id}/stop")
    assert stopped.status_code == 200
    assert stopped.json()["status"] == "stopped"

    assert client.delete(f"/sessions/{session_id}").status_code == 204
    assert client.get(f"/sessions/{session_id}").status_code == 404


def test_stop_timeout_is_not_reported_as_clean_stop(client: TestClient) -> None:
    app = client.app
    app.state.runtime = SessionRuntimeManager(
        app.state.repository,
        app.state.event_hub,
        app.state.settings,
        runner_factory=StuckRunner,
    )
    created = client.post("/sessions", json=_session_payload()).json()
    assert client.post(f"/sessions/{created['id']}/start").status_code == 200

    stopped = client.post(f"/sessions/{created['id']}/stop")
    assert stopped.status_code == 200
    assert stopped.json()["status"] == "failed"
    assert stopped.json()["failure_code"] == "runner_stop_timeout"


def test_deleting_another_session_keeps_the_camera_reserved(client: TestClient) -> None:
    app = client.app
    app.state.runtime = SessionRuntimeManager(
        app.state.repository,
        app.state.event_hub,
        app.state.settings,
        runner_factory=NoopRunner,
    )
    running = client.post("/sessions", json=_session_payload()).json()
    assert client.post(f"/sessions/{running['id']}/start").status_code == 200

    unrelated = client.post("/sessions", json=_session_payload()).json()
    assert client.delete(f"/sessions/{unrelated['id']}").status_code == 204

    contender = client.post("/sessions", json=_session_payload()).json()
    response = client.post(f"/sessions/{contender['id']}/start")
    assert response.status_code == 409

    assert client.post(f"/sessions/{running['id']}/stop").status_code == 200
    assert client.post(f"/sessions/{contender['id']}/start").status_code == 200


def test_consent_is_required_before_camera_start(client: TestClient) -> None:
    created = client.post("/sessions", json=_session_payload(consent=False)).json()
    response = client.post(f"/sessions/{created['id']}/start")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "camera_consent_required"


def test_camera_failure_returns_sanitized_error(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail_to_open(_capture: OpenCVCapture) -> None:
        raise ResourceUnavailableError("camera is unavailable or permission was denied")

    monkeypatch.setattr(OpenCVCapture, "open", fail_to_open)
    created = client.post("/sessions", json=_session_payload()).json()
    response = client.post(f"/sessions/{created['id']}/start")
    assert response.status_code == 503
    assert response.json() == {
        "error": {
            "code": "resource_unavailable",
            "message": "camera is unavailable or permission was denied",
        }
    }
    saved = client.get(f"/sessions/{created['id']}").json()
    assert saved["status"] == SessionStatus.FAILED.value
    assert saved["failure_code"] == "camera_unavailable"


def test_list_pagination_and_validation(client: TestClient) -> None:
    for _ in range(3):
        assert client.post("/sessions", json=_session_payload()).status_code == 201
    page = client.get("/sessions?limit=2&offset=1")
    assert page.status_code == 200
    assert page.json()["total"] == 3
    assert len(page.json()["items"]) == 2
    assert client.get("/sessions?limit=0").status_code == 422


def test_health_and_dashboard(client: TestClient) -> None:
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["components"]["database"] == "ok"
    dashboard = client.get("/")
    assert dashboard.status_code == 200
    assert "집중도를 판정하지 않고" in dashboard.text


def test_camera_probe_requires_explicit_consent(client: TestClient) -> None:
    response = client.get("/cameras")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "camera_consent_required"
