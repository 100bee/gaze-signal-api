#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, math.ceil(fraction * len(ordered)) - 1))
    return ordered[index]


def summarize(events: list[dict[str, Any]]) -> dict[str, float | int]:
    if not events:
        return {
            "event_count": 0,
            "effective_fps": 0.0,
            "latency_p50_ms": 0.0,
            "latency_p95_ms": 0.0,
        }
    timestamps = [
        datetime.fromisoformat(item["timestamp"].replace("Z", "+00:00")) for item in events
    ]
    duration = max(0.0, (max(timestamps) - min(timestamps)).total_seconds())
    latencies = [float(item["processing_latency_ms"]) for item in events]
    return {
        "event_count": len(events),
        "effective_fps": (len(events) - 1) / duration if duration > 0 else 0.0,
        "latency_p50_ms": percentile(latencies, 0.50),
        "latency_p95_ms": percentile(latencies, 0.95),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize exported AnalysisEvent JSON.")
    parser.add_argument("json_file", type=Path)
    args = parser.parse_args()
    payload = json.loads(args.json_file.read_text(encoding="utf-8"))
    events = payload.get("items", payload) if isinstance(payload, dict) else payload
    print(json.dumps(summarize(events), indent=2))


if __name__ == "__main__":
    main()
