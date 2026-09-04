from __future__ import annotations

import pytest

from gaze_signal_api.calibration.service import CalibrationService, apply_calibration
from gaze_signal_api.schemas.calibration import CalibrationCreate


def _payload() -> CalibrationCreate:
    points = [
        (0.0, 0.0),
        (1.0, 0.0),
        (0.0, 1.0),
        (1.0, 1.0),
        (0.5, 0.5),
    ]
    return CalibrationCreate(
        pattern_points=5,
        camera_index=0,
        camera_width=640,
        camera_height=480,
        screen_width=1920,
        screen_height=1080,
        samples=[
            {
                "target_x": x,
                "target_y": y,
                "feature_x": (x - 0.1) / 0.8,
                "feature_y": (y - 0.2) / 0.6,
                "confidence": 0.9,
            }
            for x, y in points
        ],
    )


def test_affine_calibration_recovers_mapping() -> None:
    parameters = CalibrationService().fit(_payload())
    x, y = apply_calibration(0.5, 0.5, parameters)
    assert x == pytest.approx(0.5, abs=1e-8)
    assert y == pytest.approx(0.5, abs=1e-8)
    assert parameters.root_mean_squared_error < 1e-8


def test_collinear_calibration_is_rejected() -> None:
    payload = _payload()
    for index, sample in enumerate(payload.samples):
        sample.feature_x = index / 4
        sample.feature_y = index / 4
    with pytest.raises(Exception, match="span both screen axes"):
        CalibrationService().fit(payload)


def test_every_target_needs_a_reliable_sample() -> None:
    payload = _payload()
    payload.samples[0].confidence = 0.1
    payload.samples.extend(payload.samples[1:].copy())
    with pytest.raises(Exception, match="every calibration target"):
        CalibrationService().fit(payload)


def test_center_target_sets_neutral_head_pose() -> None:
    payload = _payload()
    center = payload.samples[-1]
    center.head_yaw = 7.0
    center.head_pitch = -11.0
    center.head_roll = 2.5
    parameters = CalibrationService().fit(payload)
    assert parameters.neutral_head_yaw == 7.0
    assert parameters.neutral_head_pitch == -11.0
    assert parameters.neutral_head_roll == 2.5
