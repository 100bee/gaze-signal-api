from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path
from typing import Any
from uuid import UUID

from gaze_signal_api.calibration.service import apply_calibration
from gaze_signal_api.capture.camera import CameraConfig, OpenCVCapture
from gaze_signal_api.config.settings import Settings
from gaze_signal_api.errors import GazeSignalError, ResourceUnavailableError
from gaze_signal_api.schemas.analysis import FrameSignals
from gaze_signal_api.schemas.calibration import CalibrationParameters
from gaze_signal_api.schemas.common import GazeZone
from gaze_signal_api.storage.database import Database
from gaze_signal_api.storage.repository import Repository
from gaze_signal_api.vision.pipeline import VisionPipeline

logger = logging.getLogger(__name__)
WINDOW_NAME = "Session Signals · Local live preview"


def normalized_gaze_point(
    signal: FrameSignals,
    calibration: CalibrationParameters | None,
) -> tuple[float, float] | None:
    """Map the derived iris feature to a coarse normalized screen point."""

    if signal.gaze_feature_x is None or signal.gaze_feature_y is None:
        return None
    if calibration is None:
        x, y = 1.0 - signal.gaze_feature_x, signal.gaze_feature_y
    else:
        x, y = apply_calibration(
            signal.gaze_feature_x,
            signal.gaze_feature_y,
            calibration,
        )
    return min(1.0, max(0.0, x)), min(1.0, max(0.0, y))


def draw_signal_overlay(
    frame_bgr: Any,
    signal: FrameSignals,
    *,
    calibration: CalibrationParameters | None,
    effective_fps: float,
    frame_brightness: float | None = None,
) -> Any:
    """Draw derived labels on a copy of a local preview frame."""

    import cv2

    frame = frame_bgr.copy()
    height, width = frame.shape[:2]
    colors = {
        GazeZone.CENTER: (100, 230, 160),
        GazeZone.LEFT: (80, 200, 255),
        GazeZone.RIGHT: (80, 200, 255),
        GazeZone.UP: (80, 200, 255),
        GazeZone.DOWN: (80, 200, 255),
        GazeZone.AWAY: (80, 80, 255),
        GazeZone.UNKNOWN: (170, 170, 170),
    }
    color = colors[signal.gaze_zone]
    if not signal.face_analysis_available or not signal.face_present:
        color = (80, 80, 255)

    panel_height = min(height, 126)
    panel = frame.copy()
    cv2.rectangle(panel, (0, 0), (width, panel_height), (8, 12, 22), -1)
    cv2.addWeighted(panel, 0.82, frame, 0.18, 0.0, frame)
    cv2.rectangle(frame, (0, 0), (width - 1, height - 1), color, 4)

    face_label = (
        "UNAVAILABLE"
        if not signal.face_analysis_available
        else ("DETECTED" if signal.face_present else "MISSING")
    )
    mode = "CALIBRATED" if calibration is not None else "UNCALIBRATED / APPROXIMATE"
    cv2.putText(
        frame,
        f"COARSE GAZE: {signal.gaze_zone.value.upper()}",
        (18, 34),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.82,
        color,
        2,
        cv2.LINE_AA,
    )
    cv2.putText(
        frame,
        f"FACE: {face_label}   HEAD yaw {signal.head_yaw:+.1f}  pitch {signal.head_pitch:+.1f}",
        (18, 66),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.52,
        (235, 239, 248),
        1,
        cv2.LINE_AA,
    )
    cv2.putText(
        frame,
        f"{mode}   quality {signal.confidence:.2f}   "
        f"{effective_fps:.1f} FPS   {signal.processing_latency_ms:.1f} ms",
        (18, 92),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.47,
        (190, 199, 216),
        1,
        cv2.LINE_AA,
    )
    cv2.putText(
        frame,
        "LOCAL ONLY - NOT RECORDED   |   Q or ESC: quit   M: mirror",
        (18, 116),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.42,
        (150, 161, 181),
        1,
        cv2.LINE_AA,
    )

    point = normalized_gaze_point(signal, calibration)
    if point is not None and signal.face_present:
        x = int(point[0] * (width - 1))
        # Keep the marker below the text panel when it is near the top edge.
        y = max(panel_height + 12, int(point[1] * (height - 1)))
        y = min(height - 1, y)
        cv2.circle(frame, (x, y), 18, color, 3, cv2.LINE_AA)
        cv2.circle(frame, (x, y), 4, color, -1, cv2.LINE_AA)
        cv2.line(frame, (x - 27, y), (x + 27, y), color, 1, cv2.LINE_AA)
        cv2.line(frame, (x, y - 27), (x, y + 27), color, 1, cv2.LINE_AA)

    if signal.phone_visible:
        cv2.putText(
            frame,
            "PHONE OBJECT VISIBLE",
            (18, height - 22),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (70, 70, 255),
            2,
            cv2.LINE_AA,
        )
    if frame_brightness is not None and frame_brightness < 2.0:
        cv2.rectangle(frame, (0, height - 58), (width, height), (10, 10, 10), -1)
        cv2.putText(
            frame,
            "CAMERA INPUT IS BLACK - close camera apps or try --camera 1",
            (18, height - 24),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.54,
            (80, 80, 255),
            2,
            cv2.LINE_AA,
        )
    return frame


def load_calibration(
    settings: Settings,
    calibration_id: str | None,
    *,
    camera_index: int,
    width: int,
    height: int,
) -> tuple[CalibrationParameters | None, Database | None]:
    if calibration_id is None:
        return None, None
    database = Database(settings.database_url)
    database.create_all()
    repository = Repository(database)
    try:
        if calibration_id == "latest":
            items, _total = repository.list_calibrations(limit=1, offset=0)
            if not items:
                raise GazeSignalError("no saved calibration exists")
            saved = items[0]
        else:
            try:
                parsed_id = UUID(calibration_id)
            except ValueError as exc:
                raise GazeSignalError("calibration ID must be a UUID or 'latest'") from exc
            saved = repository.get_calibration(parsed_id)
    except Exception:
        database.close()
        raise
    if (
        saved.camera_index != camera_index
        or saved.camera_width != width
        or saved.camera_height != height
    ):
        database.close()
        raise GazeSignalError("saved calibration does not match camera geometry")
    return saved.parameters, database


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Show a local-only camera preview with real-time derived gaze labels."
    )
    parser.add_argument(
        "--consent",
        action="store_true",
        help="Required acknowledgement that this command activates the local camera.",
    )
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=480)
    parser.add_argument("--fps", type=float, default=15.0)
    parser.add_argument("--camera-warmup-seconds", type=float, default=2.0)
    parser.add_argument("--yolo", action="store_true")
    parser.add_argument(
        "--calibration-id",
        help="Saved calibration UUID, or 'latest'. Omit for approximate mode.",
    )
    parser.add_argument("--unmirrored", action="store_true")
    parser.add_argument("--fullscreen", action="store_true")
    parser.add_argument("--model", type=Path, default=Path("models/face_landmarker.task"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.consent:
        raise SystemExit(
            "camera was not opened: pass --consent only after the person on camera agrees"
        )
    if args.camera_warmup_seconds < 0:
        raise SystemExit("camera warm-up duration cannot be negative")

    try:
        import cv2
    except ImportError:
        raise SystemExit("OpenCV vision dependencies are not installed") from None

    settings = Settings(
        face_model_path=args.model,
        yolo_enabled=args.yolo,
        target_fps=args.fps,
    )
    calibration: CalibrationParameters | None = None
    database: Database | None = None
    capture = OpenCVCapture(
        CameraConfig(index=args.camera, width=args.width, height=args.height, fps=args.fps)
    )
    pipeline: VisionPipeline | None = None
    mirror = not args.unmirrored
    frame_count = 0
    fps_started = time.monotonic()
    effective_fps = 0.0

    try:
        calibration, database = load_calibration(
            settings,
            args.calibration_id,
            camera_index=args.camera,
            width=args.width,
            height=args.height,
        )
        pipeline = VisionPipeline(
            settings,
            calibration=calibration,
            yolo_enabled=args.yolo,
        )
        capture.open()
        print(
            f"Warming up camera for {args.camera_warmup_seconds:g} seconds...",
            flush=True,
        )
        warmup_deadline = time.monotonic() + args.camera_warmup_seconds
        warmup_frames = 0
        brightest_warmup_frame = 0.0
        while time.monotonic() < warmup_deadline:
            ok, warmup_frame = capture.read()
            if not ok or warmup_frame is None:
                raise ResourceUnavailableError("camera stopped during warm-up")
            warmup_frames += 1
            brightest_warmup_frame = max(
                brightest_warmup_frame,
                float(warmup_frame.mean()),
            )
        print(
            f"Camera warm-up complete: {warmup_frames} frames, "
            f"peak brightness {brightest_warmup_frame:.1f}",
            flush=True,
        )
        if warmup_frames and brightest_warmup_frame < 2.0:
            print(
                "Warning: camera is returning black frames. Close FaceTime/Zoom/OBS, "
                "or quit and retry with --camera 1.",
                flush=True,
            )
        cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(WINDOW_NAME, 960, 720)
        if args.fullscreen:
            cv2.setWindowProperty(
                WINDOW_NAME,
                cv2.WND_PROP_FULLSCREEN,
                cv2.WINDOW_FULLSCREEN,
            )
        while True:
            ok, raw_frame = capture.read()
            if not ok or raw_frame is None:
                raise ResourceUnavailableError("camera stopped returning frames")
            signal = pipeline.process(raw_frame)
            frame_brightness = float(raw_frame.mean())
            frame_count += 1
            elapsed = time.monotonic() - fps_started
            if elapsed >= 1.0:
                effective_fps = frame_count / elapsed
                frame_count = 0
                fps_started = time.monotonic()

            display_frame = cv2.flip(raw_frame, 1) if mirror else raw_frame
            display_frame = draw_signal_overlay(
                display_frame,
                signal,
                calibration=calibration,
                effective_fps=effective_fps,
                frame_brightness=frame_brightness,
            )
            cv2.imshow(WINDOW_NAME, display_frame)
            key = cv2.waitKey(1) & 0xFF
            if key in {27, ord("q"), ord("Q")}:
                break
            if key in {ord("m"), ord("M")}:
                mirror = not mirror
            if cv2.getWindowProperty(WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1:
                break
    except GazeSignalError as exc:
        raise SystemExit(exc.message) from None
    except ResourceUnavailableError as exc:
        raise SystemExit(exc.message) from None
    finally:
        capture.release()
        if pipeline is not None:
            pipeline.close()
        if database is not None:
            database.close()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
