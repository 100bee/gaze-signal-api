from __future__ import annotations

import numpy as np
import pytest

from gaze_signal_api.preview import draw_signal_overlay, normalized_gaze_point
from gaze_signal_api.schemas.analysis import FrameSignals
from gaze_signal_api.schemas.calibration import CalibrationParameters


def signal() -> FrameSignals:
    return FrameSignals(
        face_present=True,
        gaze_zone="center",
        gaze_feature_x=0.25,
        gaze_feature_y=0.6,
        confidence=0.4,
        processing_latency_ms=8.0,
    )


def test_uncalibrated_preview_converts_raw_x_to_screen_x() -> None:
    assert normalized_gaze_point(signal(), None) == pytest.approx((0.75, 0.6))


def test_calibrated_preview_uses_affine_screen_point() -> None:
    calibration = CalibrationParameters(
        x_coefficients=(2.0, 0.0, 0.0),
        y_coefficients=(0.0, 0.5, 0.0),
        root_mean_squared_error=0.01,
    )
    assert normalized_gaze_point(signal(), calibration) == pytest.approx((0.5, 0.3))


def test_overlay_draws_without_mutating_source_frame() -> None:
    pytest.importorskip("cv2")
    source = np.zeros((480, 640, 3), dtype=np.uint8)
    rendered = draw_signal_overlay(source, signal(), calibration=None, effective_fps=15.0)
    assert np.count_nonzero(source) == 0
    assert np.count_nonzero(rendered) > 0


def test_overlay_labels_black_camera_input() -> None:
    pytest.importorskip("cv2")
    source = np.zeros((480, 640, 3), dtype=np.uint8)
    rendered = draw_signal_overlay(
        source,
        signal(),
        calibration=None,
        effective_fps=15.0,
        frame_brightness=0.0,
    )
    assert np.count_nonzero(rendered[430:, :, 2]) > 0
