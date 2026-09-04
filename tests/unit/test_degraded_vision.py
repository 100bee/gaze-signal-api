from __future__ import annotations

import numpy as np

from gaze_signal_api.config.settings import Settings
from gaze_signal_api.errors import ResourceUnavailableError
from gaze_signal_api.vision.pipeline import VisionPipeline


class MissingFaceModel:
    def extract(self, _frame: np.ndarray) -> None:
        raise ResourceUnavailableError("model missing")

    def close(self) -> None:
        pass


def test_missing_face_model_returns_explicitly_unavailable_signal() -> None:
    pipeline = VisionPipeline(
        Settings(yolo_enabled=False),
        face_extractor=MissingFaceModel(),  # type: ignore[arg-type]
    )
    signal = pipeline.process(np.zeros((16, 16, 3), dtype=np.uint8))
    assert signal.face_present is False
    assert signal.face_analysis_available is False
    assert signal.gaze_zone == "unknown"
    assert signal.confidence == 0.0
