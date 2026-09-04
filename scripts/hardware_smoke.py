#!/usr/bin/env python3
"""Consent-gated, memory-only camera and MediaPipe smoke test.

This script never writes frames. It prints only aggregate derived signals so a
developer can validate the actual camera/OS/model path before claiming accuracy.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from gaze_signal_api.capture.camera import CameraConfig, OpenCVCapture
from gaze_signal_api.config.settings import Settings
from gaze_signal_api.errors import ResourceUnavailableError
from gaze_signal_api.schemas.analysis import FrameSignals
from gaze_signal_api.vision.pipeline import VisionPipeline


@dataclass
class Phase:
    key: str
    instruction: str
    signals: list[FrameSignals] = field(default_factory=list)
    capture_seconds: float = 0.0


def median(values: list[float]) -> float | None:
    return round(float(statistics.median(values)), 3) if values else None


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int((len(ordered) - 1) * fraction)))
    return round(float(ordered[index]), 3)


def summarize(phase: Phase) -> dict[str, object]:
    signals = phase.signals
    analyzable = [signal for signal in signals if signal.face_analysis_available]
    faces = [signal for signal in analyzable if signal.face_present]
    return {
        "frames_processed": len(signals),
        "capture_seconds": round(phase.capture_seconds, 3),
        "effective_fps": round(len(signals) / phase.capture_seconds, 3)
        if phase.capture_seconds > 0
        else 0.0,
        "face_analysis_available_ratio": round(len(analyzable) / len(signals), 3)
        if signals
        else 0.0,
        "face_present_ratio": round(len(faces) / len(analyzable), 3) if analyzable else 0.0,
        "gaze_zones": dict(Counter(signal.gaze_zone.value for signal in signals)),
        "median_gaze_feature_x": median(
            [signal.gaze_feature_x for signal in faces if signal.gaze_feature_x is not None]
        ),
        "median_gaze_feature_y": median(
            [signal.gaze_feature_y for signal in faces if signal.gaze_feature_y is not None]
        ),
        "median_head_yaw": median([signal.head_yaw for signal in faces]),
        "median_head_pitch": median([signal.head_pitch for signal in faces]),
        "median_head_roll": median([signal.head_roll for signal in faces]),
        "latency_p50_ms": percentile([signal.processing_latency_ms for signal in signals], 0.50),
        "latency_p95_ms": percentile([signal.processing_latency_ms for signal in signals], 0.95),
        "latency_max_ms": round(
            max((signal.processing_latency_ms for signal in signals), default=0.0), 3
        ),
        "phone_visible_frames": sum(signal.phone_visible for signal in signals),
    }


def guided_sign_checks(summaries: dict[str, dict[str, object]]) -> dict[str, bool | None]:
    center = summaries["center"]

    def difference(phase: str, key: str) -> float | None:
        baseline = center[key]
        observed = summaries[phase][key]
        if not isinstance(baseline, float | int) or not isinstance(observed, float | int):
            return None
        return float(observed) - float(baseline)

    expectations = {
        "screen_left_yaw_is_negative": (difference("screen_left", "median_head_yaw"), -1),
        "screen_right_yaw_is_positive": (difference("screen_right", "median_head_yaw"), 1),
        "up_pitch_is_negative": (difference("up", "median_head_pitch"), -1),
        "down_pitch_is_positive": (difference("down", "median_head_pitch"), 1),
    }
    result: dict[str, bool | None] = {}
    for key, (delta, direction) in expectations.items():
        result[key] = None if delta is None else delta * direction >= 3.0
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a memory-only macOS camera + MediaPipe end-to-end smoke test."
    )
    parser.add_argument(
        "--consent",
        action="store_true",
        help="Required acknowledgement that this command will activate the local camera.",
    )
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=480)
    parser.add_argument("--fps", type=float, default=15.0)
    parser.add_argument("--seconds", type=float, default=8.0)
    parser.add_argument("--guided-pose", action="store_true")
    parser.add_argument("--phase-seconds", type=float, default=3.0)
    parser.add_argument("--prep-seconds", type=float, default=2.0)
    parser.add_argument("--yolo", action="store_true")
    parser.add_argument("--model", type=Path, default=Path("models/face_landmarker.task"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.consent:
        raise SystemExit(
            "camera was not opened: pass --consent only after the person on camera agrees"
        )
    if args.seconds <= 0 or args.phase_seconds <= 0 or args.prep_seconds < 0:
        raise SystemExit("durations must be positive")

    phases = (
        [
            Phase("center", "Look at the screen center with a relaxed head."),
            Phase("screen_left", "Turn your face toward the screen's LEFT edge."),
            Phase("screen_right", "Turn your face toward the screen's RIGHT edge."),
            Phase("up", "Turn your face toward the TOP edge."),
            Phase("down", "Turn your face toward the BOTTOM edge."),
        ]
        if args.guided_pose
        else [Phase("end_to_end", "Look naturally near the screen center.")]
    )
    duration = args.phase_seconds if args.guided_pose else args.seconds
    settings = Settings(
        face_model_path=args.model,
        yolo_enabled=args.yolo,
        target_fps=args.fps,
    )
    capture = OpenCVCapture(
        CameraConfig(index=args.camera, width=args.width, height=args.height, fps=args.fps)
    )
    pipeline = VisionPipeline(settings, yolo_enabled=args.yolo)
    frame_shapes: Counter[str] = Counter()
    read_failures = 0
    started = time.monotonic()
    warmup_seconds = 0.0
    warmup_frames = max(3, settings.yolo_every_n_frames if args.yolo else 3)

    try:
        capture.open()
        print(
            f"WARMING UP: initializing models with {warmup_frames} in-memory frames.",
            file=sys.stderr,
            flush=True,
        )
        warmup_started = time.monotonic()
        warmed = 0
        while warmed < warmup_frames:
            ok, frame = capture.read()
            if not ok or frame is None:
                read_failures += 1
                if read_failures >= 3:
                    raise ResourceUnavailableError("camera stopped returning frames")
                continue
            read_failures = 0
            frame_shapes[f"{frame.shape[1]}x{frame.shape[0]}"] += 1
            pipeline.process(frame)
            warmed += 1
        warmup_seconds = time.monotonic() - warmup_started
        for phase in phases:
            print(f"\nPREPARE: {phase.instruction}", file=sys.stderr, flush=True)
            if args.prep_seconds:
                time.sleep(args.prep_seconds)
            print(f"CAPTURING: {phase.key}", file=sys.stderr, flush=True)
            phase_started = time.monotonic()
            deadline = phase_started + duration
            next_frame = phase_started
            while time.monotonic() < deadline:
                ok, frame = capture.read()
                if not ok or frame is None:
                    read_failures += 1
                    if read_failures >= 3:
                        raise ResourceUnavailableError("camera stopped returning frames")
                    continue
                read_failures = 0
                frame_shapes[f"{frame.shape[1]}x{frame.shape[0]}"] += 1
                phase.signals.append(pipeline.process(frame))
                next_frame += 1.0 / args.fps
                time.sleep(max(0.0, next_frame - time.monotonic()))
            phase.capture_seconds = time.monotonic() - phase_started
    except ResourceUnavailableError as exc:
        print(json.dumps({"status": "failed", "reason": exc.message}, indent=2))
        raise SystemExit(2) from None
    finally:
        capture.release()
        pipeline.close()

    summaries = {phase.key: summarize(phase) for phase in phases}
    result: dict[str, object] = {
        "status": "ok",
        "privacy": "frames processed in memory; no images written",
        "camera_index": args.camera,
        "requested_format": f"{args.width}x{args.height}@{args.fps:g}",
        "observed_frame_shapes": dict(frame_shapes),
        "warmup_frames": warmup_frames,
        "warmup_seconds": round(warmup_seconds, 3),
        "wall_seconds": round(time.monotonic() - started, 3),
        "phases": summaries,
        "yolo_requested": args.yolo,
        "yolo_failure_code": pipeline.phone.failure_code,
    }
    if args.guided_pose:
        result["pose_sign_checks"] = guided_sign_checks(summaries)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
