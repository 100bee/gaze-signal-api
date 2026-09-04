from __future__ import annotations

import pytest
from pydantic import ValidationError

from gaze_signal_api.config.settings import Settings
from gaze_signal_api.schemas.calibration import CalibrationCreate
from gaze_signal_api.schemas.session import SessionCreate


def test_raw_frame_storage_is_rejected() -> None:
    with pytest.raises(ValidationError, match="raw frame storage"):
        Settings(store_raw_frames=True)


def test_screen_dimensions_must_be_paired() -> None:
    with pytest.raises(ValidationError, match="provided together"):
        SessionCreate(consent_given=True, screen_width=1920)


def test_calibration_requires_five_distinct_targets() -> None:
    sample = {
        "target_x": 0.5,
        "target_y": 0.5,
        "feature_x": 0.5,
        "feature_y": 0.5,
    }
    with pytest.raises(ValidationError, match="distinct targets"):
        CalibrationCreate(
            pattern_points=5,
            camera_index=0,
            camera_width=640,
            camera_height=480,
            screen_width=1920,
            screen_height=1080,
            samples=[sample] * 5,
        )


def test_yolo_period_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        Settings(yolo_every_n_frames=0)
