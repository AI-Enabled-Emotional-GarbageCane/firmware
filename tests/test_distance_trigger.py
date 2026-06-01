from __future__ import annotations

from datetime import datetime
from queue import Queue
import unittest

import numpy as np

from firmware_l515.distance_trigger import (
    DistanceTriggerConfig,
    L515DistanceTrigger,
    compute_center_roi_distance_cm,
    is_depth_frame_invalid,
)


class FakeClock:
    def __init__(self, now: float = 0.0) -> None:
        self.now = now

    def monotonic(self) -> float:
        return self.now


def fixed_ts() -> datetime:
    return datetime(2026, 5, 31, 21, 0, 0)


class DistanceTriggerTests(unittest.TestCase):
    def test_compute_center_roi_distance_uses_valid_depth_median(self) -> None:
        depth = np.full((10, 10), 1000, dtype=np.uint16)
        depth[2:8, 2:8] = 400
        depth[4, 4] = 0
        depth[5, 5] = 900

        distance_cm = compute_center_roi_distance_cm(
            depth,
            depth_scale_m=0.001,
            roi_fraction=0.6,
            min_valid_cm=5.0,
            max_valid_cm=200.0,
        )

        self.assertEqual(distance_cm, 40.0)

    def test_compute_center_roi_distance_returns_none_when_roi_has_no_valid_depth(self) -> None:
        depth = np.full((8, 8), 1000, dtype=np.uint16)
        depth[2:6, 2:6] = 0

        distance_cm = compute_center_roi_distance_cm(
            depth,
            depth_scale_m=0.001,
            roi_fraction=0.5,
            min_valid_cm=5.0,
            max_valid_cm=200.0,
        )

        self.assertIsNone(distance_cm)

    def test_is_depth_frame_invalid_flags_high_invalid_ratio(self) -> None:
        depth = np.zeros((10, 10), dtype=np.uint16)
        depth[4:6, 4:6] = 400

        self.assertTrue(
            is_depth_frame_invalid(
                depth,
                depth_scale_m=0.001,
                center_fraction=0.8,
                invalid_ratio_threshold=0.7,
                min_valid_cm=5.0,
                max_valid_cm=200.0,
            )
        )

    def test_trigger_puts_user_detected_event_once_with_cooldown(self) -> None:
        q_detected: Queue[dict[str, object]] = Queue()
        clock = FakeClock()
        trigger = L515DistanceTrigger(
            q_detected,
            config=DistanceTriggerConfig(
                trigger_distance_cm=30.0,
                cooldown_sec=2.0,
                roi_fraction=0.5,
                invalid_ratio_threshold=0.9,
            ),
            monotonic=clock.monotonic,
            now=fixed_ts,
        )
        depth = np.full((6, 6), 250, dtype=np.uint16)

        self.assertTrue(trigger.process_depth_frame(depth, depth_scale_m=0.001))
        self.assertEqual(q_detected.qsize(), 1)
        self.assertEqual(
            q_detected.get_nowait(),
            {
                "event": "user_detected",
                "distance_cm": 25.0,
                "ts": "2026-05-31T21:00:00",
            },
        )

        clock.now = 1.0
        self.assertFalse(trigger.process_depth_frame(depth, depth_scale_m=0.001))
        self.assertEqual(q_detected.qsize(), 0)

        clock.now = 2.1
        self.assertTrue(trigger.process_depth_frame(depth, depth_scale_m=0.001))
        self.assertEqual(q_detected.qsize(), 1)

    def test_trigger_ignores_invalid_or_far_depth_frames(self) -> None:
        q_detected: Queue[dict[str, object]] = Queue()
        trigger = L515DistanceTrigger(
            q_detected,
            config=DistanceTriggerConfig(trigger_distance_cm=30.0, roi_fraction=0.5),
            now=fixed_ts,
        )

        invalid_depth = np.zeros((6, 6), dtype=np.uint16)
        far_depth = np.full((6, 6), 700, dtype=np.uint16)

        self.assertFalse(trigger.process_depth_frame(invalid_depth, depth_scale_m=0.001))
        self.assertFalse(trigger.process_depth_frame(far_depth, depth_scale_m=0.001))
        self.assertEqual(q_detected.qsize(), 0)


if __name__ == "__main__":
    unittest.main()
