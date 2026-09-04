from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from gaze_signal_api.schemas.analysis import HeadPose

# Coarse six-point face model in OpenCV camera coordinates:
# x points image-right, y points image-down, and z points away from the camera.
# The nose tip is the origin and the remaining features are behind it.
FACE_MODEL_POINTS = np.asarray(
    [
        (0.0, 0.0, 0.0),
        (0.0, 330.0, 65.0),
        (-225.0, -170.0, 135.0),
        (225.0, -170.0, 135.0),
        (-150.0, 150.0, 125.0),
        (150.0, 150.0, 125.0),
    ],
    dtype=np.float64,
)


def rotation_matrix_to_euler(rotation: np.ndarray) -> HeadPose:
    """Convert a camera-coordinate rotation matrix to pitch/yaw/roll degrees.

    For an unmirrored camera image, positive yaw turns toward image-left (the
    user's screen-right), positive pitch turns downward, and positive roll is
    clockwise in the raw image.
    """

    sy = math.sqrt(float(rotation[0, 0] ** 2 + rotation[1, 0] ** 2))
    singular = sy < 1e-6
    if not singular:
        pitch = math.atan2(float(rotation[2, 1]), float(rotation[2, 2]))
        yaw = math.atan2(float(-rotation[2, 0]), sy)
        roll = math.atan2(float(rotation[1, 0]), float(rotation[0, 0]))
    else:
        pitch = math.atan2(float(-rotation[1, 2]), float(rotation[1, 1]))
        yaw = math.atan2(float(-rotation[2, 0]), sy)
        roll = 0.0
    return HeadPose(
        yaw=math.degrees(yaw),
        pitch=math.degrees(pitch),
        roll=math.degrees(roll),
    )


@dataclass(slots=True)
class HeadPoseEstimator:
    """Estimate face rotation with OpenCV solvePnP from six Face Landmarker points.

    Output follows :func:`rotation_matrix_to_euler` and therefore refers to the raw,
    unmirrored camera image rather than a mirrored preview.
    """

    # nose, chin, left eye outer, right eye outer, left mouth, right mouth
    landmark_indices: tuple[int, ...] = (1, 152, 33, 263, 61, 291)

    def estimate(
        self,
        landmarks: tuple[tuple[float, float, float], ...],
        frame_width: int,
        frame_height: int,
    ) -> HeadPose | None:
        if len(landmarks) <= max(self.landmark_indices):
            return None
        try:
            import cv2
        except ImportError:
            return None

        image_points = np.asarray(
            [
                (landmarks[index][0] * frame_width, landmarks[index][1] * frame_height)
                for index in self.landmark_indices
            ],
            dtype=np.float64,
        )
        focal_length = float(frame_width)
        camera_matrix = np.asarray(
            [
                (focal_length, 0.0, frame_width / 2.0),
                (0.0, focal_length, frame_height / 2.0),
                (0.0, 0.0, 1.0),
            ],
            dtype=np.float64,
        )
        distortion = np.zeros((4, 1), dtype=np.float64)
        success, rotation_vector, _translation = cv2.solvePnP(
            FACE_MODEL_POINTS,
            image_points,
            camera_matrix,
            distortion,
            flags=cv2.SOLVEPNP_ITERATIVE,
        )
        if not success:
            return None
        rotation_matrix, _ = cv2.Rodrigues(rotation_vector)
        return rotation_matrix_to_euler(rotation_matrix)
