from __future__ import annotations

import pytest

from gaze_signal_api.schemas.analysis import HeadPose
from gaze_signal_api.schemas.calibration import CalibrationParameters
from gaze_signal_api.schemas.common import GazeZone
from gaze_signal_api.vision.gaze_estimator import GazeEstimator, eye_aspect_ratio


def landmarks_with_centered_irises() -> tuple[tuple[float, float, float], ...]:
    values = [(0.0, 0.0, 0.0) for _ in range(478)]
    # left iris/corners/lids
    values[468] = (0.4, 0.5, 0.0)
    values[33] = (0.3, 0.5, 0.0)
    values[133] = (0.5, 0.5, 0.0)
    values[159] = (0.4, 0.46, 0.0)
    values[145] = (0.4, 0.54, 0.0)
    values[158] = (0.4, 0.46, 0.0)
    values[153] = (0.4, 0.54, 0.0)
    # right iris/corners/lids
    values[473] = (0.6, 0.5, 0.0)
    values[362] = (0.5, 0.5, 0.0)
    values[263] = (0.7, 0.5, 0.0)
    values[386] = (0.6, 0.46, 0.0)
    values[374] = (0.6, 0.54, 0.0)
    values[385] = (0.6, 0.46, 0.0)
    values[380] = (0.6, 0.54, 0.0)
    return tuple(values)


def test_uncalibrated_gaze_is_low_confidence() -> None:
    estimate = GazeEstimator().estimate(landmarks_with_centered_irises(), HeadPose(), 1.0)
    assert estimate.zone == GazeZone.CENTER
    assert estimate.feature_x == 0.5
    assert estimate.feature_y == pytest.approx(0.5)
    assert estimate.confidence == 0.4


def test_calibrated_gaze_uses_affine_mapping() -> None:
    parameters = CalibrationParameters(
        x_coefficients=(1.0, 0.0, 0.0),
        y_coefficients=(0.0, 1.0, 0.0),
        root_mean_squared_error=0.05,
    )
    estimate = GazeEstimator(parameters).estimate(landmarks_with_centered_irises(), HeadPose(), 1.0)
    assert estimate.zone == GazeZone.CENTER
    assert estimate.confidence == 0.95


def test_extreme_head_pose_is_away_without_iris_classification() -> None:
    estimate = GazeEstimator().estimate(landmarks_with_centered_irises(), HeadPose(yaw=40), 0.8)
    assert estimate.zone == GazeZone.AWAY
    assert estimate.feature_x == pytest.approx(0.5)
    assert estimate.confidence == 0.4


@pytest.mark.parametrize(
    ("iris_x", "expected"),
    [(0.32, GazeZone.RIGHT), (0.48, GazeZone.LEFT)],
)
def test_uncalibrated_horizontal_feature_converts_raw_image_to_screen_direction(
    iris_x: float, expected: GazeZone
) -> None:
    landmarks = list(landmarks_with_centered_irises())
    landmarks[468] = (iris_x, 0.5, 0.0)
    landmarks[473] = (iris_x + 0.2, 0.5, 0.0)
    estimate = GazeEstimator().estimate(tuple(landmarks), HeadPose(), 1.0)
    assert estimate.zone == expected


def test_eye_aspect_ratio_is_available() -> None:
    assert eye_aspect_ratio(landmarks_with_centered_irises()) is not None


def _normalized_eyes(width: int, height: int) -> tuple[tuple[float, float, float], ...]:
    """Both eyes 60 px wide and 18 px open in a frame of the given size."""
    values = [(0.0, 0.0, 0.0) for _ in range(478)]
    for outer, inner, upper_a, lower_a, upper_b, lower_b in (
        (33, 133, 159, 145, 158, 153),
        (362, 263, 386, 374, 385, 380),
    ):
        values[outer] = (290 / width, 200 / height, 0.0)
        values[inner] = (350 / width, 200 / height, 0.0)
        for upper, lower in ((upper_a, lower_a), (upper_b, lower_b)):
            values[upper] = (320 / width, 191 / height, 0.0)
            values[lower] = (320 / width, 209 / height, 0.0)
    return tuple(values)


@pytest.mark.parametrize(("width", "height"), [(640, 480), (1280, 720), (480, 640)])
def test_eye_aspect_ratio_matches_pixel_geometry_at_any_resolution(
    width: int, height: int
) -> None:
    ratio = eye_aspect_ratio(_normalized_eyes(width, height), width / height)
    assert ratio == pytest.approx(18 / 60)
