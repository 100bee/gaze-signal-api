from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class PhoneDetector:
    """Low-frequency optional YOLO adapter. COCO class 67 is a cell phone."""

    def __init__(
        self,
        *,
        enabled: bool,
        model_path: str,
        confidence_threshold: float,
        every_n_frames: int,
    ) -> None:
        self.enabled = enabled
        self.model_path = model_path
        self.confidence_threshold = confidence_threshold
        self.every_n_frames = every_n_frames
        self._model: Any | None = None
        self._last_visible = False
        self.failure_code: str | None = None

    def _load(self) -> None:
        if self._model is not None or not self.enabled:
            return
        if not Path(self.model_path).is_file():
            logger.warning("YOLO model is not installed locally; disabling detector")
            self.enabled = False
            self.failure_code = "yolo_model_unavailable"
            return
        try:
            from ultralytics import YOLO

            self._model = YOLO(self.model_path)
        except Exception:
            logger.exception("YOLO phone detector failed to load")
            self.enabled = False
            self.failure_code = "yolo_model_unavailable"

    def detect(self, frame_bgr: Any, frame_index: int) -> bool:
        if not self.enabled:
            return False
        if frame_index % self.every_n_frames != 0:
            return self._last_visible
        self._load()
        if self._model is None:
            return False
        try:
            results = self._model.predict(
                source=frame_bgr,
                classes=[67],
                conf=self.confidence_threshold,
                verbose=False,
            )
            self._last_visible = any(len(result.boxes) > 0 for result in results)
        except Exception:
            logger.exception("YOLO phone detection failed; disabling detector")
            self.enabled = False
            self.failure_code = "yolo_inference_failed"
            self._last_visible = False
        return self._last_visible
