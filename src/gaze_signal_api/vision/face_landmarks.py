from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from gaze_signal_api.errors import ResourceUnavailableError


@dataclass(frozen=True, slots=True)
class LandmarkObservation:
    landmarks: tuple[tuple[float, float, float], ...]
    confidence: float


class FaceLandmarkExtractor:
    """Lazy MediaPipe Face Landmarker adapter.

    The model asset is local. Frame data is passed only to the in-process Tasks API.
    """

    def __init__(self, model_path: Path, min_confidence: float = 0.55) -> None:
        self.model_path = model_path
        self.min_confidence = min_confidence
        self._landmarker: Any | None = None
        self._mp: Any | None = None
        self._load_failed = False

    def _load(self) -> None:
        if self._landmarker is not None:
            return
        if self._load_failed:
            raise ResourceUnavailableError("face landmarker model could not be loaded")
        if not self.model_path.is_file():
            self._load_failed = True
            raise ResourceUnavailableError("face landmarker model asset is not installed")
        try:
            import mediapipe as mp
        except ImportError as exc:
            raise ResourceUnavailableError("MediaPipe vision extra is not installed") from exc

        try:
            options = mp.tasks.vision.FaceLandmarkerOptions(
                base_options=mp.tasks.BaseOptions(
                    model_asset_path=str(self.model_path),
                    delegate=mp.tasks.BaseOptions.Delegate.CPU,
                ),
                running_mode=mp.tasks.vision.RunningMode.IMAGE,
                num_faces=1,
                min_face_detection_confidence=self.min_confidence,
                min_face_presence_confidence=self.min_confidence,
                min_tracking_confidence=self.min_confidence,
            )
            self._landmarker = mp.tasks.vision.FaceLandmarker.create_from_options(options)
            self._mp = mp
        except Exception as exc:
            self._load_failed = True
            raise ResourceUnavailableError("face landmarker model could not be loaded") from exc

    def extract(self, frame_bgr: Any) -> LandmarkObservation | None:
        self._load()
        assert self._mp is not None and self._landmarker is not None
        rgb = frame_bgr[:, :, ::-1].copy()
        image = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=rgb)
        result = self._landmarker.detect(image)
        if not result.face_landmarks:
            return None
        face = result.face_landmarks[0]
        landmarks = tuple((float(point.x), float(point.y), float(point.z)) for point in face)
        return LandmarkObservation(landmarks=landmarks, confidence=1.0)

    def close(self) -> None:
        landmarker, self._landmarker = self._landmarker, None
        if landmarker is not None:
            landmarker.close()
