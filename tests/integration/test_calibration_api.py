from __future__ import annotations

from fastapi.testclient import TestClient


def _calibration_payload() -> dict[str, object]:
    points = [(0, 0), (1, 0), (0, 1), (1, 1), (0.5, 0.5)]
    return {
        "label": "test setup",
        "pattern_points": 5,
        "camera_index": 0,
        "camera_width": 640,
        "camera_height": 480,
        "screen_width": 1920,
        "screen_height": 1080,
        "samples": [
            {
                "target_x": x,
                "target_y": y,
                "feature_x": x,
                "feature_y": y,
                "confidence": 0.9,
            }
            for x, y in points
        ],
    }


def test_calibration_create_list_reuse_and_delete(client: TestClient) -> None:
    created = client.post("/calibrations", json=_calibration_payload())
    assert created.status_code == 201
    calibration = created.json()
    assert calibration["parameters"]["root_mean_squared_error"] < 1e-8
    assert client.get("/calibrations").json()["total"] == 1

    session = client.post(
        "/sessions",
        json={
            "consent_given": True,
            "camera_index": 0,
            "frame_width": 640,
            "frame_height": 480,
            "screen_width": 1920,
            "screen_height": 1080,
            "target_fps": 15,
            "yolo_enabled": False,
            "calibration_id": calibration["id"],
        },
    )
    assert session.status_code == 201

    mismatch = client.post(
        "/sessions",
        json={
            "consent_given": True,
            "camera_index": 0,
            "frame_width": 1280,
            "frame_height": 720,
            "screen_width": 1920,
            "screen_height": 1080,
            "target_fps": 15,
            "yolo_enabled": False,
            "calibration_id": calibration["id"],
        },
    )
    assert mismatch.status_code == 409
    assert "geometry" in mismatch.json()["error"]["message"]

    assert client.delete(f"/calibrations/{calibration['id']}").status_code == 204
    assert client.get("/calibrations").json()["total"] == 0
