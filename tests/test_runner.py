from __future__ import annotations

from queue import Queue
import unittest

import numpy as np

from firmware_l515.distance_trigger import DistanceTriggerConfig
from firmware_l515.runner import run_distance_trigger_loop


class FakeCamera:
    def __init__(self, frames: list[np.ndarray]) -> None:
        self.frames = frames
        self.depth_scale_m = 0.001
        self.started = False
        self.stopped = False

    def start(self) -> None:
        self.started = True

    def read_depth_frame(self) -> np.ndarray:
        if not self.frames:
            raise RuntimeError("no frames left")
        return self.frames.pop(0)

    def stop(self) -> None:
        self.stopped = True


class RunnerTests(unittest.TestCase):
    def test_loop_reads_depth_and_stops_camera_after_max_frames(self) -> None:
        q_detected: Queue[dict[str, object]] = Queue()
        camera = FakeCamera(
            [
                np.full((6, 6), 700, dtype=np.uint16),
                np.full((6, 6), 250, dtype=np.uint16),
            ]
        )
        statuses: list[str] = []

        processed = run_distance_trigger_loop(
            q_detected,
            camera=camera,
            config=DistanceTriggerConfig(
                trigger_distance_cm=30.0,
                cooldown_sec=2.0,
                roi_fraction=0.5,
                invalid_ratio_threshold=0.9,
            ),
            max_frames=2,
            on_status=statuses.append,
        )

        self.assertEqual(processed, 2)
        self.assertTrue(camera.started)
        self.assertTrue(camera.stopped)
        self.assertEqual(q_detected.qsize(), 1)
        self.assertEqual(q_detected.get_nowait()["distance_cm"], 25.0)
        self.assertIn("detected", statuses)


if __name__ == "__main__":
    unittest.main()
