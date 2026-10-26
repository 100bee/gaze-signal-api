from __future__ import annotations

from dataclasses import dataclass

from gaze_signal_api.calibration.service import apply_calibration
from gaze_signal_api.schemas.analysis import HeadPose
from gaze_signal_api.schemas.calibration import CalibrationParameters
from gaze_signal_api.schemas.common import GazeZone


@dataclass(frozen=True, slots=True)
class GazeEstimate:
    zone: GazeZone
    feature_x: float | None
    feature_y: float | None
    confidence: float


def classify_screen_point(x: float, y: float, away_margin: float = 0.1) -> GazeZone:
    if x < -away_margin or x > 1.0 + away_margin or y < -away_margin or y > 1.0 + away_margin:
        return GazeZone.AWAY
    dx, dy = x - 0.5, y - 0.5
    if abs(dx) <= 0.16 and abs(dy) <= 0.16:
        return GazeZone.CENTER
    if abs(dx) >= abs(dy):
        return GazeZone.LEFT if dx < 0 else GazeZone.RIGHT
    return GazeZone.UP if dy < 0 else GazeZone.DOWN


class GazeEstimator:
    # iris center, horizontal eye corners, upper/lower lids
    _LEFT = (468, 33, 133, 159, 145)
    _RIGHT = (473, 362, 263, 386, 374)

    def __init__(
        self,
        calibration: CalibrationParameters | None = None,
        yaw_away_degrees: float = 30.0,
        pitch_away_degrees: float = 25.0,
    ) -> None:
        self.calibration = calibration
        self.yaw_away_degrees = yaw_away_degrees
        self.pitch_away_degrees = pitch_away_degrees

    def estimate(
        self,
        landmarks: tuple[tuple[float, float, float], ...],
        head_pose: HeadPose,
        face_confidence: float,
    ) -> GazeEstimate:
        features = [self._eye_feature(landmarks, indices) for indices in (self._LEFT, self._RIGHT)]
        valid = [feature for feature in features if feature is not None]
        if not valid:
            return GazeEstimate(GazeZone.UNKNOWN, None, None, min(face_confidence, 0.2))
        feature_x = sum(item[0] for item in valid) / len(valid)
        feature_y = sum(item[1] for item in valid) / len(valid)

        if (
            abs(head_pose.yaw) >= self.yaw_away_degrees
            or abs(head_pose.pitch) >= self.pitch_away_degrees
        ):
            # Keep the derived eye feature available to calibration/diagnostics even
            # when the coarse head-pose rule classifies this frame as away. Head pose
            # needs no calibration, so this path is not capped like the iris path.
            return GazeEstimate(GazeZone.AWAY, feature_x, feature_y, face_confidence * 0.8)

        if self.calibration is not None:
            screen_x, screen_y = apply_calibration(feature_x, feature_y, self.calibration)
            rmse_penalty = min(0.7, self.calibration.root_mean_squared_error)
            confidence = face_confidence * (1.0 - rmse_penalty)
            return GazeEstimate(
                classify_screen_point(screen_x, screen_y), feature_x, feature_y, confidence
            )

        # OpenCV returns an unmirrored image: moving toward the user's screen-right
        # moves an iris toward image-left. Convert raw image x to screen x here;
        # calibrated mode learns this sign in its affine coefficients.
        screen_x = 1.0 - feature_x
        # Limited uncalibrated mode: ratios are approximate and confidence is capped.
        zone = classify_screen_point(screen_x, feature_y, away_margin=0.2)
        return GazeEstimate(zone, feature_x, feature_y, min(0.4, face_confidence * 0.4))

    @staticmethod
    def _eye_feature(
        landmarks: tuple[tuple[float, float, float], ...],
        indices: tuple[int, int, int, int, int],
    ) -> tuple[float, float] | None:
        if len(landmarks) <= max(indices):
            return None
        iris, corner_a, corner_b, upper, lower = (landmarks[index] for index in indices)
        left, right = sorted((corner_a[0], corner_b[0]))
        top, bottom = sorted((upper[1], lower[1]))
        width, height = right - left, bottom - top
        if width <= 1e-6 or height <= 1e-6:
            return None
        return (iris[0] - left) / width, (iris[1] - top) / height


def eye_aspect_ratio(
    landmarks: tuple[tuple[float, float, float], ...],
    aspect: float = 1.0,
) -> float | None:
    """Return a two-eye vertical/horizontal openness proxy.

    Landmarks are normalized by frame width and height separately, so pass the
    frame's width / height to get the same ratio at every resolution.
    """

    eye_sets = ((33, 133, 159, 145, 158, 153), (362, 263, 386, 374, 385, 380))
    ratios: list[float] = []
    for outer, inner, upper_a, lower_a, upper_b, lower_b in eye_sets:
        if len(landmarks) <= max(outer, inner, upper_a, lower_a, upper_b, lower_b):
            continue
        horizontal = abs(landmarks[outer][0] - landmarks[inner][0]) * aspect
        vertical_a = abs(landmarks[upper_a][1] - landmarks[lower_a][1])
        vertical_b = abs(landmarks[upper_b][1] - landmarks[lower_b][1])
        if horizontal > 1e-6:
            ratios.append((vertical_a + vertical_b) / (2.0 * horizontal))
    return sum(ratios) / len(ratios) if ratios else None
