#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

ZONES = ("center", "left", "right", "up", "down", "away", "unknown")


def evaluate(rows: list[dict[str, str]]) -> dict[str, object]:
    confusion = {truth: dict.fromkeys(ZONES, 0) for truth in ZONES}
    correct = 0
    known_correct = 0
    known_total = 0
    predictions: Counter[str] = Counter()
    for index, row in enumerate(rows, start=2):
        truth, predicted = row.get("true_zone"), row.get("predicted_zone")
        if truth not in ZONES or predicted not in ZONES:
            raise ValueError(f"invalid zone at CSV line {index}")
        confusion[truth][predicted] += 1
        predictions[predicted] += 1
        correct += truth == predicted
        if predicted != "unknown":
            known_total += 1
            known_correct += truth == predicted
    total = len(rows)
    return {
        "sample_count": total,
        "overall_accuracy": correct / total if total else 0.0,
        "known_only_accuracy": known_correct / known_total if known_total else 0.0,
        "unknown_ratio": predictions["unknown"] / total if total else 0.0,
        "confusion_matrix": confusion,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate held-out gaze-zone predictions.")
    parser.add_argument("csv_file", type=Path)
    args = parser.parse_args()
    with args.csv_file.open(newline="", encoding="utf-8") as source:
        result = evaluate(list(csv.DictReader(source)))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
