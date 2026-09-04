from __future__ import annotations

import math

import numpy as np
import pytest

from gaze_signal_api.schemas.common import GazeZone
from gaze_signal_api.vision.gaze_estimator import classify_screen_point
from gaze_signal_api.vision.head_pose import (
    FACE_MODEL_POINTS,
    HeadPoseEstimator,
    rotation_matrix_to_euler,
)


@pytest.mark.parametrize(
    ("point", "expected"),
    [
        ((0.5, 0.5), GazeZone.CENTER),
        ((0.1, 0.5), GazeZone.LEFT),
        ((0.9, 0.5), GazeZone.RIGHT),
        ((0.5, 0.1), GazeZone.UP),
        ((0.5, 0.9), GazeZone.DOWN),
        ((1.2, 0.5), GazeZone.AWAY),
    ],
)
def test_classify_screen_point(point: tuple[float, float], expected: GazeZone) -> None:
    assert classify_screen_point(*point) == expected


def test_identity_rotation_has_zero_angles() -> None:
    pose = rotation_matrix_to_euler(np.eye(3))
    assert pose.yaw == pytest.approx(0.0)
    assert pose.pitch == pytest.approx(0.0)
    assert pose.roll == pytest.approx(0.0)


def test_y_axis_rotation_converts_to_yaw_degrees() -> None:
    angle = math.radians(20)
    matrix = np.asarray(
        [
            [math.cos(angle), 0.0, math.sin(angle)],
            [0.0, 1.0, 0.0],
            [-math.sin(angle), 0.0, math.cos(angle)],
        ]
    )
    pose = rotation_matrix_to_euler(matrix)
    assert pose.yaw == pytest.approx(20.0)


@pytest.mark.parametrize(
    ("axis", "angle"),
    [("yaw", 20.0), ("yaw", -20.0), ("pitch", 15.0), ("pitch", -15.0), ("roll", 10.0)],
)
def test_solve_pnp_recovers_projected_pose_sign(axis: str, angle: float) -> None:
    cv2 = pytest.importorskip("cv2")
    radians = math.radians(angle)
    cosine, sine = math.cos(radians), math.sin(radians)
    if axis == "yaw":
        rotation = np.asarray([(cosine, 0.0, sine), (0.0, 1.0, 0.0), (-sine, 0.0, cosine)])
    elif axis == "pitch":
        rotation = np.asarray([(1.0, 0.0, 0.0), (0.0, cosine, -sine), (0.0, sine, cosine)])
    else:
        rotation = np.asarray([(cosine, -sine, 0.0), (sine, cosine, 0.0), (0.0, 0.0, 1.0)])

    camera_matrix = np.asarray([(640.0, 0.0, 320.0), (0.0, 640.0, 240.0), (0.0, 0.0, 1.0)])
    rotation_vector, _ = cv2.Rodrigues(rotation)
    image_points, _ = cv2.projectPoints(
        FACE_MODEL_POINTS,
        rotation_vector,
        np.asarray([[0.0], [0.0], [1400.0]]),
        camera_matrix,
        None,
    )
    landmarks = [(0.0, 0.0, 0.0) for _ in range(478)]
    estimator = HeadPoseEstimator()
    for index, (x, y) in zip(
        estimator.landmark_indices,
        image_points.reshape(-1, 2),
        strict=True,
    ):
        landmarks[index] = (x / 640.0, y / 480.0, 0.0)

    pose = estimator.estimate(tuple(landmarks), 640, 480)
    assert pose is not None
    assert getattr(pose, axis) == pytest.approx(angle, abs=0.05)
    for other_axis in {"yaw", "pitch", "roll"} - {axis}:
        assert getattr(pose, other_axis) == pytest.approx(0.0, abs=0.05)
