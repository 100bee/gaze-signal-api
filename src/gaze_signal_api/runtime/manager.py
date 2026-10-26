from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from uuid import UUID

from gaze_signal_api.capture.camera import CameraConfig
from gaze_signal_api.config.settings import Settings
from gaze_signal_api.errors import ConflictError, ConsentRequiredError, ResourceUnavailableError
from gaze_signal_api.runtime.runner import SessionRunner
from gaze_signal_api.runtime.websocket import EventHub
from gaze_signal_api.schemas.common import SessionStatus
from gaze_signal_api.schemas.session import SessionRead
from gaze_signal_api.storage.repository import Repository
from gaze_signal_api.vision.pipeline import VisionPipeline

RunnerFactory = Callable[..., SessionRunner]
logger = logging.getLogger(__name__)


class SessionRuntimeManager:
    def __init__(
        self,
        repository: Repository,
        event_hub: EventHub,
        settings: Settings,
        runner_factory: RunnerFactory = SessionRunner,
    ) -> None:
        self.repository = repository
        self.event_hub = event_hub
        self.settings = settings
        self.runner_factory = runner_factory
        self._runners: dict[str, SessionRunner] = {}
        self._camera_owners: dict[int, str] = {}
        self._lock = threading.Lock()

    def start(self, session_id: UUID) -> SessionRead:
        with self._lock:
            session = self.repository.get_session(session_id)
            if session.status != SessionStatus.CREATED:
                raise ConflictError(f"cannot start a session in {session.status.value} state")
            if not session.consent_given:
                raise ConsentRequiredError("explicit camera consent is required before start")
            owner = self._camera_owners.get(session.camera_index)
            if owner is not None:
                owner_runner = self._runners.get(owner)
                if owner_runner is not None and getattr(owner_runner, "is_alive", True):
                    raise ConflictError("the selected camera is already used by another session")
                self._camera_owners.pop(session.camera_index, None)
                self._runners.pop(owner, None)

            calibration = None
            if session.calibration_id is not None:
                saved = self.repository.get_calibration(session.calibration_id)
                if (
                    saved.camera_index != session.camera_index
                    or saved.camera_width != session.frame_width
                    or saved.camera_height != session.frame_height
                    or saved.screen_width != session.screen_width
                    or saved.screen_height != session.screen_height
                ):
                    raise ConflictError(
                        "camera or screen geometry changed; create a new calibration"
                    )
                calibration = saved.parameters

            runner = self.runner_factory(
                session_id=session.id,
                camera_config=CameraConfig(
                    index=session.camera_index,
                    width=session.frame_width,
                    height=session.frame_height,
                    fps=session.target_fps,
                ),
                pipeline=VisionPipeline(
                    self.settings,
                    calibration=calibration,
                    yolo_enabled=session.yolo_enabled,
                ),
                repository=self.repository,
                event_hub=self.event_hub,
                settings=self.settings,
            )
            running = self.repository.set_session_status(session.id, SessionStatus.RUNNING)
            try:
                runner.start()
            except ResourceUnavailableError:
                runner.stop()
                self.repository.set_session_status(
                    session.id, SessionStatus.FAILED, failure_code="camera_unavailable"
                )
                raise
            except Exception as exc:
                runner.stop()
                self.repository.set_session_status(
                    session.id, SessionStatus.FAILED, failure_code="camera_start_failed"
                )
                raise ResourceUnavailableError("camera could not be started") from exc
            self._runners[str(session.id)] = runner
            self._camera_owners[session.camera_index] = str(session.id)
            current = self.repository.get_session(session.id)
            return current if current.status == SessionStatus.FAILED else running

    def stop(self, session_id: UUID) -> SessionRead:
        with self._lock:
            session = self.repository.get_session(session_id)
            if session.status != SessionStatus.RUNNING:
                raise ConflictError(f"cannot stop a session in {session.status.value} state")
            runner = self._runners.pop(str(session_id), None)
            self._release_camera(session.camera_index, session_id)
            if runner is not None:
                runner.stop()
            current = self.repository.get_session(session_id)
            if current.status == SessionStatus.FAILED:
                return current
            if runner is not None and runner.is_alive:
                return self.repository.set_session_status(
                    session_id,
                    SessionStatus.FAILED,
                    failure_code="runner_stop_timeout",
                )
            return self.repository.set_session_status(session_id, SessionStatus.STOPPED)

    def delete(self, session_id: UUID) -> None:
        with self._lock:
            session = self.repository.get_session(session_id)
            if session.status == SessionStatus.RUNNING:
                raise ConflictError("stop the running session before deleting it")
            runner = self._runners.pop(str(session_id), None)
            self._release_camera(session.camera_index, session_id)
            if runner is not None:
                runner.stop()
            self.repository.delete_session(session_id)

    def _release_camera(self, camera_index: int, session_id: UUID) -> None:
        # A session that never started must not free a camera another session is using.
        if self._camera_owners.get(camera_index) == str(session_id):
            del self._camera_owners[camera_index]

    def shutdown(self) -> None:
        with self._lock:
            runners = list(self._runners.items())
            self._runners.clear()
            self._camera_owners.clear()
        for session_id, runner in runners:
            try:
                runner.stop()
                current = self.repository.get_session(session_id)
                if current.status == SessionStatus.RUNNING:
                    status = SessionStatus.FAILED if runner.is_alive else SessionStatus.STOPPED
                    failure_code = "runner_stop_timeout" if runner.is_alive else None
                    self.repository.set_session_status(
                        session_id,
                        status,
                        failure_code=failure_code,
                    )
            except Exception:
                logger.exception(
                    "session cleanup failed during shutdown",
                    extra={"session_id": session_id},
                )
