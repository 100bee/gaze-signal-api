from __future__ import annotations

import logging
import threading
import time
from queue import Empty
from typing import Any, Protocol
from uuid import UUID

from gaze_signal_api.analytics.state_machine import TemporalStateMachine
from gaze_signal_api.capture.camera import CameraConfig, OpenCVCapture
from gaze_signal_api.capture.latest_frame import LatestFrameBuffer
from gaze_signal_api.config.settings import Settings
from gaze_signal_api.schemas.analysis import AnalysisEvent
from gaze_signal_api.schemas.common import SessionStatus
from gaze_signal_api.storage.repository import Repository
from gaze_signal_api.vision.pipeline import VisionPipeline

logger = logging.getLogger(__name__)


class Capture(Protocol):
    def open(self) -> None: ...

    def read(self) -> tuple[bool, Any | None]: ...

    def release(self) -> None: ...


class SessionRunner:
    """Two-thread camera/analysis runner with a size-one latest-frame buffer."""

    def __init__(
        self,
        *,
        session_id: UUID,
        camera_config: CameraConfig,
        pipeline: VisionPipeline,
        repository: Repository,
        event_hub: Any,
        settings: Settings,
        capture: Capture | None = None,
    ) -> None:
        self.session_id = session_id
        self.camera_config = camera_config
        self.pipeline = pipeline
        self.repository = repository
        self.event_hub = event_hub
        self.settings = settings
        self.capture = capture or OpenCVCapture(camera_config)
        self.frames: LatestFrameBuffer[Any] = LatestFrameBuffer()
        self._stop = threading.Event()
        self._capture_finished = threading.Event()
        self._failure_code: str | None = None
        self._capture_thread: threading.Thread | None = None
        self._analysis_thread: threading.Thread | None = None

    def start(self) -> None:
        self.capture.open()
        self._capture_thread = threading.Thread(
            target=self._capture_loop,
            name=f"capture-{self.session_id}",
            daemon=True,
        )
        self._analysis_thread = threading.Thread(
            target=self._analysis_loop,
            name=f"analysis-{self.session_id}",
            daemon=True,
        )
        self._capture_thread.start()
        self._analysis_thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        self.capture.release()
        for thread in (self._capture_thread, self._analysis_thread):
            if thread is not None and thread is not threading.current_thread():
                thread.join(timeout=timeout)

    @property
    def is_alive(self) -> bool:
        return any(
            thread is not None and thread.is_alive()
            for thread in (self._capture_thread, self._analysis_thread)
        )

    def _capture_loop(self) -> None:
        consecutive_failures = 0
        try:
            while not self._stop.is_set():
                ok, frame = self.capture.read()
                if ok and frame is not None:
                    consecutive_failures = 0
                    self.frames.put(frame)
                    continue
                consecutive_failures += 1
                if consecutive_failures < 3:
                    continue
                if not self._reconnect():
                    self._failure_code = "camera_disconnected"
                    break
                consecutive_failures = 0
        except Exception:
            logger.exception(
                "camera capture loop failed", extra={"session_id": str(self.session_id)}
            )
            self._failure_code = "camera_capture_failed"
        finally:
            self._capture_finished.set()
            self.capture.release()

    def _reconnect(self) -> bool:
        self.capture.release()
        for _attempt in range(self.settings.camera_reconnect_attempts):
            if self._stop.wait(0.25):
                return False
            try:
                self.capture.open()
                return True
            except Exception:
                logger.warning(
                    "camera reconnect attempt failed",
                    extra={"session_id": str(self.session_id)},
                )
        return False

    def _analysis_loop(self) -> None:
        state_machine = TemporalStateMachine(
            session_id=self.session_id,
            confidence_threshold=self.settings.gaze_confidence_threshold,
            debounce_ms=self.settings.debounce_ms,
            away_min_duration_ms=self.settings.away_min_duration_ms,
        )
        batch: list[AnalysisEvent] = []
        min_interval = 1.0 / self.camera_config.fps
        last_processed = 0.0
        try:
            while not self._stop.is_set():
                try:
                    frame = self.frames.get(timeout=0.25)
                except Empty:
                    if self._capture_finished.is_set():
                        break
                    continue
                current = time.monotonic()
                # Frames arrive with jitter; a strict gate drops every other frame
                # when the camera already delivers the target fps.
                if current - last_processed < min_interval * 0.9:
                    continue
                last_processed = current
                signal = self.pipeline.process(frame)
                state, transition = state_machine.update(signal)
                event = AnalysisEvent(
                    session_id=self.session_id,
                    state=state,
                    **signal.model_dump(),
                )
                batch.append(event)
                self.event_hub.publish(event)
                if transition is not None:
                    self.repository.add_transition(transition)
                if len(batch) >= self.settings.event_batch_size:
                    self.repository.add_events(batch)
                    batch.clear()
        except Exception:
            logger.exception("analysis loop failed", extra={"session_id": str(self.session_id)})
            self._failure_code = "analysis_pipeline_failed"
        finally:
            try:
                if batch:
                    self.repository.add_events(batch)
            except Exception:
                logger.exception(
                    "final event batch could not be stored",
                    extra={"session_id": str(self.session_id)},
                )
                self._failure_code = self._failure_code or "event_persistence_failed"
            try:
                self.pipeline.close()
            except Exception:
                logger.exception(
                    "vision pipeline close failed",
                    extra={"session_id": str(self.session_id)},
                )
            try:
                if self._failure_code and not self._stop.is_set():
                    self.repository.set_session_status(
                        self.session_id,
                        SessionStatus.FAILED,
                        failure_code=self._failure_code,
                    )
            except Exception:
                logger.exception(
                    "failed session status could not be stored",
                    extra={"session_id": str(self.session_id)},
                )
            finally:
                self._stop.set()
