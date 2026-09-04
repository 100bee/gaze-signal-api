from __future__ import annotations

import threading
import time
from typing import Any
from uuid import UUID

import numpy as np

from gaze_signal_api.capture.camera import CameraConfig
from gaze_signal_api.runtime.runner import SessionRunner
from gaze_signal_api.schemas.analysis import FrameSignals
from gaze_signal_api.schemas.common import SessionStatus


class FakeCapture:
    def __init__(self) -> None:
        self.opened = False
        self.released = False

    def open(self) -> None:
        self.opened = True

    def read(self) -> tuple[bool, np.ndarray | None]:
        if not self.opened:
            return False, None
        time.sleep(0.002)
        return True, np.zeros((12, 16, 3), dtype=np.uint8)

    def release(self) -> None:
        self.opened = False
        self.released = True


class ReconnectingCapture(FakeCapture):
    def __init__(self) -> None:
        super().__init__()
        self.open_count = 0
        self.read_count = 0

    def open(self) -> None:
        super().open()
        self.open_count += 1

    def read(self) -> tuple[bool, np.ndarray | None]:
        self.read_count += 1
        if self.open_count == 1:
            return False, None
        return super().read()


class FakePipeline:
    def __init__(self) -> None:
        self.closed = False

    def process(self, _frame: np.ndarray) -> FrameSignals:
        return FrameSignals(
            face_present=True,
            gaze_zone="center",
            gaze_feature_x=0.5,
            gaze_feature_y=0.5,
            confidence=0.9,
            processing_latency_ms=1.0,
        )

    def close(self) -> None:
        self.closed = True


class CollectingHub:
    def __init__(self) -> None:
        self.events: list[Any] = []
        self.received = threading.Event()

    def publish(self, event: Any) -> None:
        self.events.append(event)
        self.received.set()


def test_capture_to_analysis_to_database_vertical_slice(client, settings) -> None:  # type: ignore[no-untyped-def]
    created = client.post(
        "/sessions",
        json={"consent_given": True, "camera_index": 0, "target_fps": 60},
    ).json()
    capture = FakeCapture()
    pipeline = FakePipeline()
    hub = CollectingHub()
    runner = SessionRunner(
        session_id=UUID(created["id"]),
        camera_config=CameraConfig(index=0, width=640, height=480, fps=60),
        pipeline=pipeline,  # type: ignore[arg-type]
        repository=client.app.state.repository,
        event_hub=hub,
        settings=settings.model_copy(update={"event_batch_size": 1}),
        capture=capture,
    )
    try:
        runner.start()
        assert hub.received.wait(timeout=2.0)
    finally:
        runner.stop()

    events = client.app.state.repository.all_events(created["id"])
    assert events
    assert events[0].gaze_zone == "center"
    assert capture.released is True
    assert pipeline.closed is True


def test_camera_read_failure_reconnects_and_resumes_analysis(client, settings) -> None:  # type: ignore[no-untyped-def]
    created = client.post(
        "/sessions",
        json={"consent_given": True, "camera_index": 0, "target_fps": 60},
    ).json()
    capture = ReconnectingCapture()
    pipeline = FakePipeline()
    hub = CollectingHub()
    runner = SessionRunner(
        session_id=UUID(created["id"]),
        camera_config=CameraConfig(index=0, width=640, height=480, fps=60),
        pipeline=pipeline,  # type: ignore[arg-type]
        repository=client.app.state.repository,
        event_hub=hub,
        settings=settings.model_copy(update={"event_batch_size": 1}),
        capture=capture,
    )
    try:
        runner.start()
        assert hub.received.wait(timeout=2.0)
    finally:
        runner.stop()

    assert capture.open_count >= 2
    assert capture.read_count >= 4


class FailingRepository:
    def __init__(self) -> None:
        self.statuses: list[tuple[SessionStatus, str | None]] = []

    def add_transition(self, _transition: Any) -> None:
        pass

    def add_events(self, _events: Any) -> None:
        raise RuntimeError("database write failed")

    def set_session_status(
        self,
        _session_id: UUID,
        status: SessionStatus,
        *,
        failure_code: str | None = None,
    ) -> None:
        self.statuses.append((status, failure_code))


def test_final_storage_failure_still_closes_pipeline_and_marks_failed(settings) -> None:  # type: ignore[no-untyped-def]
    pipeline = FakePipeline()
    repository = FailingRepository()
    runner = SessionRunner(
        session_id=UUID("00000000-0000-0000-0000-000000000001"),
        camera_config=CameraConfig(index=0, width=640, height=480, fps=60),
        pipeline=pipeline,  # type: ignore[arg-type]
        repository=repository,  # type: ignore[arg-type]
        event_hub=CollectingHub(),
        settings=settings.model_copy(update={"event_batch_size": 10}),
        capture=FakeCapture(),
    )
    runner.frames.put(np.zeros((12, 16, 3), dtype=np.uint8))
    runner._capture_finished.set()

    thread = threading.Thread(target=runner._analysis_loop)
    thread.start()
    thread.join(timeout=2.0)

    assert not thread.is_alive()
    assert pipeline.closed is True
    assert repository.statuses == [(SessionStatus.FAILED, "event_persistence_failed")]
