from __future__ import annotations

import numpy as np

from gaze_signal_api.vision.object_detector import PhoneDetector


class FakeResult:
    boxes = (object(),)


class FakeModel:
    def __init__(self, fail: bool = False) -> None:
        self.calls = 0
        self.fail = fail

    def predict(self, **_kwargs):  # type: ignore[no-untyped-def]
        self.calls += 1
        if self.fail:
            raise RuntimeError("inference error")
        return [FakeResult()]


def detector() -> PhoneDetector:
    return PhoneDetector(
        enabled=True,
        model_path="unused.pt",
        confidence_threshold=0.5,
        every_n_frames=10,
    )


def test_phone_detector_runs_at_configured_low_frequency() -> None:
    phone = detector()
    model = FakeModel()
    phone._model = model
    frame = np.zeros((4, 4, 3), dtype=np.uint8)
    for frame_index in range(1, 10):
        assert phone.detect(frame, frame_index) is False
    assert phone.detect(frame, 10) is True
    assert phone.detect(frame, 11) is True
    assert model.calls == 1


def test_phone_failure_disables_only_detector() -> None:
    phone = detector()
    phone._model = FakeModel(fail=True)
    assert phone.detect(np.zeros((4, 4, 3), dtype=np.uint8), 10) is False
    assert phone.enabled is False
    assert phone.failure_code == "yolo_inference_failed"


def test_missing_local_weight_disables_detector_without_download(tmp_path) -> None:  # type: ignore[no-untyped-def]
    phone = PhoneDetector(
        enabled=True,
        model_path=str(tmp_path / "missing.pt"),
        confidence_threshold=0.5,
        every_n_frames=1,
    )
    assert phone.detect(np.zeros((4, 4, 3), dtype=np.uint8), 1) is False
    assert phone.enabled is False
    assert phone.failure_code == "yolo_model_unavailable"
