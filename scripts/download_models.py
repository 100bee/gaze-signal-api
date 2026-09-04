#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import shutil
import urllib.request
from pathlib import Path

FACE_LANDMARKER_URL = (
    "https://storage.googleapis.com/mediapipe-models/face_landmarker/"
    "face_landmarker/float16/1/face_landmarker.task"
)
FACE_LANDMARKER_SHA256 = "64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff"
YOLO11N_URL = "https://github.com/ultralytics/assets/releases/download/v8.4.0/yolo11n.pt"
YOLO11N_SHA256 = "0ebbc80d4a7680d14987a577cd21342b65ecfd94632bd9a8da63ae6417644ee1"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def download(url: str, destination: Path, expected_sha256: str) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".part")
    request = urllib.request.Request(url, headers={"User-Agent": "GazeSignal-model-fetch/0.1"})
    try:
        with (
            urllib.request.urlopen(request, timeout=60) as response,
            temporary.open("wb") as output,
        ):
            shutil.copyfileobj(response, output)
        actual = sha256(temporary)
        if actual != expected_sha256:
            raise RuntimeError(f"model checksum mismatch: expected {expected_sha256}, got {actual}")
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download the official MediaPipe Face Landmarker model to local storage."
    )
    parser.add_argument("--output", type=Path, default=Path("models/face_landmarker.task"))
    parser.add_argument("--url", default=FACE_LANDMARKER_URL)
    parser.add_argument("--sha256", default=FACE_LANDMARKER_SHA256)
    parser.add_argument(
        "--include-yolo",
        action="store_true",
        help="Also download the optional AGPL/commercial YOLO11n weight.",
    )
    parser.add_argument("--yolo-output", type=Path, default=Path("models/yolo11n.pt"))
    parser.add_argument("--yolo-url", default=YOLO11N_URL)
    parser.add_argument("--yolo-sha256", default=YOLO11N_SHA256)
    args = parser.parse_args()

    def ensure_model(label: str, output: Path, url: str, expected_sha256: str) -> None:
        if output.exists():
            actual = sha256(output)
            if actual != expected_sha256:
                raise SystemExit(f"existing {label} checksum mismatch: {actual}")
            print(f"{label} already exists and checksum is valid: {output}")
            return
        download(url, output, expected_sha256)
        print(f"downloaded {label}: {output} ({output.stat().st_size} bytes)")
        print(f"sha256: {sha256(output)}")

    ensure_model("Face Landmarker", args.output, args.url, args.sha256)
    if args.include_yolo:
        ensure_model(
            "YOLO11n",
            args.yolo_output,
            args.yolo_url,
            args.yolo_sha256,
        )


if __name__ == "__main__":
    main()
