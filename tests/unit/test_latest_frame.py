from gaze_signal_api.capture.latest_frame import LatestFrameBuffer


def test_latest_frame_buffer_replaces_stale_item() -> None:
    buffer: LatestFrameBuffer[int] = LatestFrameBuffer()
    buffer.put(1)
    buffer.put(2)
    buffer.put(3)
    assert buffer.get() == 3
    assert buffer.dropped == 2
