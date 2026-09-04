from __future__ import annotations

import numpy as np

from gaze_signal_api.errors import GazeSignalError
from gaze_signal_api.schemas.calibration import CalibrationCreate, CalibrationParameters


class CalibrationService:
    """Fits an affine mapping from derived eye features to normalized screen position."""

    def fit(self, payload: CalibrationCreate) -> CalibrationParameters:
        samples = [sample for sample in payload.samples if sample.confidence >= 0.25]
        if len(samples) < payload.pattern_points:
            raise GazeSignalError("not enough reliable calibration samples")
        reliable_targets = {
            (round(sample.target_x, 3), round(sample.target_y, 3)) for sample in samples
        }
        if len(reliable_targets) < payload.pattern_points:
            raise GazeSignalError("every calibration target needs a reliable sample")

        design = np.asarray([[s.feature_x, s.feature_y, 1.0] for s in samples], dtype=float)
        target_x = np.asarray([s.target_x for s in samples], dtype=float)
        target_y = np.asarray([s.target_y for s in samples], dtype=float)
        weights = np.sqrt(np.asarray([s.confidence for s in samples], dtype=float))
        weighted_design = design * weights[:, None]

        if np.linalg.matrix_rank(weighted_design) < 3:
            raise GazeSignalError("calibration samples do not span both screen axes")

        x_coefficients, *_ = np.linalg.lstsq(weighted_design, target_x * weights, rcond=None)
        y_coefficients, *_ = np.linalg.lstsq(weighted_design, target_y * weights, rcond=None)
        prediction_x = design @ x_coefficients
        prediction_y = design @ y_coefficients
        squared_error = (prediction_x - target_x) ** 2 + (prediction_y - target_y) ** 2
        rmse = float(np.sqrt(np.mean(squared_error)))
        center_samples = [
            sample
            for sample in samples
            if abs(sample.target_x - 0.5) <= 0.05 and abs(sample.target_y - 0.5) <= 0.05
        ]

        def neutral_median(name: str) -> float:
            values = [getattr(sample, name) for sample in center_samples]
            available = [value for value in values if value is not None]
            return float(np.median(available)) if available else 0.0

        return CalibrationParameters(
            x_coefficients=tuple(float(v) for v in x_coefficients),
            y_coefficients=tuple(float(v) for v in y_coefficients),
            root_mean_squared_error=rmse,
            neutral_head_yaw=neutral_median("head_yaw"),
            neutral_head_pitch=neutral_median("head_pitch"),
            neutral_head_roll=neutral_median("head_roll"),
        )


def apply_calibration(
    feature_x: float,
    feature_y: float,
    parameters: CalibrationParameters,
) -> tuple[float, float]:
    vector = (feature_x, feature_y, 1.0)
    screen_x = sum(
        value * coefficient
        for value, coefficient in zip(vector, parameters.x_coefficients, strict=True)
    )
    screen_y = sum(
        value * coefficient
        for value, coefficient in zip(vector, parameters.y_coefficients, strict=True)
    )
    return screen_x, screen_y
