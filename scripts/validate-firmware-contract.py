#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from queue import Queue

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "firmware_l515"
EXPECTED_EVENT_FIELDS = {"event", "distance_cm", "ts"}


def fail(message: str) -> None:
    print(f"[FAIL] {message}", file=sys.stderr)
    raise SystemExit(1)


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def read_text(path: str) -> str:
    file_path = ROOT / path
    require(file_path.exists(), f"missing required file: {path}")
    return file_path.read_text(encoding="utf-8")


def read_json(path: str) -> dict:
    file_path = ROOT / path
    require(file_path.exists(), f"missing required file: {path}")
    with file_path.open(encoding="utf-8") as handle:
        return json.load(handle)


def require_contains(text: str, needle: str, path: str) -> None:
    require(needle in text, f"{path} must contain {needle!r}")


def require_not_contains(text: str, needle: str, path: str) -> None:
    require(needle not in text, f"{path} must not contain stale text {needle!r}")


def validate_lock() -> None:
    lock = read_json("contracts/contract.lock.json")
    require(lock.get("contract_version") == "v0.3", "contract.lock.json must use v0.3")
    require(lock.get("module") == "firmware", "contract.lock.json module must be firmware")
    require(lock.get("owned_events") == ["user_detected"], "firmware must own user_detected")
    require(lock.get("consumed_events") == [], "firmware must not consume cross-repo events")
    require(lock.get("forbidden_cross_repo_changes"), "contract.lock.json must list forbidden changes")


def validate_docs() -> None:
    readme = read_text("README.md")
    require_contains(readme, "v0.3", "README.md")
    require_contains(readme, "Intel RealSense L515", "README.md")
    require_contains(readme, "q_detected", "README.md")
    require_contains(readme, "user_detected", "README.md")
    require_contains(readme, "distance_cm", "README.md")
    require_contains(readme, "ts", "README.md")

    for stale in ["D435", "d435", "YOLOv8", "YOLOv8n", "user_action"]:
        require_not_contains(readme, stale, "README.md")


def validate_source_boundaries() -> None:
    source_text = "\n".join(path.read_text(encoding="utf-8") for path in SRC.glob("*.py"))
    require_contains(source_text, '"event": "user_detected"', "firmware_l515/*.py")
    require_contains(source_text, '"distance_cm"', "firmware_l515/*.py")
    require_contains(source_text, '"ts"', "firmware_l515/*.py")

    for forbidden in [
        "recognition_result",
        "q_result",
        "user_action",
        "snapshot_path",
        "display_to_firmware",
        "opening_lid",
    ]:
        require_not_contains(source_text, forbidden, "firmware_l515/*.py")


def fixed_ts() -> datetime:
    return datetime(2026, 5, 31, 21, 0, 0)


def validate_emitted_payload() -> None:
    sys.path.insert(0, str(ROOT))
    from firmware_l515.distance_trigger import DistanceTriggerConfig, L515DistanceTrigger

    q_detected: Queue[dict[str, object]] = Queue()
    trigger = L515DistanceTrigger(
        q_detected,
        config=DistanceTriggerConfig(
            trigger_distance_cm=30.0,
            release_distance_cm=45.0,
            cooldown_sec=0.0,
            required_consecutive_frames=1,
            roi_fraction=0.5,
            invalid_ratio_threshold=0.9,
        ),
        now=fixed_ts,
    )
    depth = np.full((6, 6), 250, dtype=np.uint16)

    require(trigger.process_depth_frame(depth, depth_scale_m=0.001), "trigger must emit user_detected for close L515 depth")
    require(q_detected.qsize() == 1, "firmware must emit exactly one event")

    event = q_detected.get_nowait()
    require(set(event) == EXPECTED_EVENT_FIELDS, "user_detected payload fields drifted")
    require(event["event"] == "user_detected", "event name must be user_detected")
    require(isinstance(event["distance_cm"], (int, float)), "distance_cm must be numeric")
    require(event["distance_cm"] == 25.0, "distance_cm must be reported in centimeters")
    require(event["ts"] == "2026-05-31T21:00:00", "ts must be ISO8601 seconds timestamp")


def main() -> None:
    validate_lock()
    validate_docs()
    validate_source_boundaries()
    validate_emitted_payload()
    print("[OK] firmware contract lock, docs, source boundaries, and emitted payload are consistent")


if __name__ == "__main__":
    main()
