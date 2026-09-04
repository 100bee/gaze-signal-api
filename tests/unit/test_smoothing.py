from __future__ import annotations

import pytest

from gaze_signal_api.analytics.smoothing import ExponentialMovingAverage, ZoneMajoritySmoother
from gaze_signal_api.schemas.common import GazeZone


def test_ema_uses_previous_value() -> None:
    ema = ExponentialMovingAverage(alpha=0.25)
    assert ema.update(10.0) == 10.0
    assert ema.update(14.0) == pytest.approx(11.0)
    ema.reset()
    assert ema.update(2.0) == 2.0


def test_zone_majority_filters_one_frame_spike() -> None:
    smoother = ZoneMajoritySmoother(window_size=5)
    assert smoother.update(GazeZone.CENTER) == GazeZone.CENTER
    assert smoother.update(GazeZone.CENTER) == GazeZone.CENTER
    assert smoother.update(GazeZone.AWAY) == GazeZone.CENTER


def test_invalid_ema_alpha() -> None:
    with pytest.raises(ValueError):
        ExponentialMovingAverage(alpha=0.0)
