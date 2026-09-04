from __future__ import annotations

import logging
import platform
import threading
from dataclasses import dataclass
from typing import Any

from gaze_signal_api.errors import ResourceUnavailableError

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class CameraConfig:
    index: int
    width: int
    height: int
    fps: float


@dataclass(frozen=True, slots=True)
class CameraInfo:
    index: int
    available: bool
    width: int | None = None
    height: int | None = None


class OpenCVCapture:
    """OpenCV-only frame acquisition; no analysis or frame persistence."""

    def __init__(self, config: CameraConfig) -> None:
        self.config = config
        self._capture: Any | None = None
        # OpenCV does not promise that read() and release() are safe when called
        # concurrently. The runtime stops the capture from a different thread, so
        # serialize all access to the native handle.
        self._capture_lock = threading.RLock()

    def open(self) -> None:
        try:
            import cv2
        except ImportError as exc:
            raise ResourceUnavailableError("OpenCV vision extra is not installed") from exc

        backend = cv2.CAP_AVFOUNDATION if platform.system() == "Darwin" else cv2.CAP_ANY
        with self._capture_lock:
            if self._capture is not None:
                self._capture.release()
                self._capture = None
            capture = cv2.VideoCapture(self.config.index, backend)
            if not capture.isOpened():
                capture.release()
                raise ResourceUnavailableError("camera is unavailable or permission was denied")
            capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.width)
            capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.height)
            capture.set(cv2.CAP_PROP_FPS, self.config.fps)
            self._capture = capture

    def read(self) -> tuple[bool, Any | None]:
        with self._capture_lock:
            if self._capture is None:
                return False, None
            ok, frame = self._capture.read()
            return bool(ok), frame if ok else None

    def release(self) -> None:
        with self._capture_lock:
            capture, self._capture = self._capture, None
            if capture is not None:
                capture.release()

    @property
    def is_opened(self) -> bool:
        with self._capture_lock:
            return self._capture is not None and bool(self._capture.isOpened())


def list_cameras(max_index: int = 5) -> list[CameraInfo]:
    """Probe cameras only when explicitly requested by the API caller."""

    try:
        import cv2
    except ImportError as exc:
        raise ResourceUnavailableError("OpenCV vision extra is not installed") from exc

    result: list[CameraInfo] = []
    backend = cv2.CAP_AVFOUNDATION if platform.system() == "Darwin" else cv2.CAP_ANY
    for index in range(max_index):
        capture = cv2.VideoCapture(index, backend)
        try:
            if not capture.isOpened():
                continue
            result.append(
                CameraInfo(
                    index=index,
                    available=True,
                    width=int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)),
                    height=int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT)),
                )
            )
        finally:
            capture.release()
    return result
