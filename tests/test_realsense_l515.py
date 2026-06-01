from __future__ import annotations

import sys
from types import SimpleNamespace
import unittest

import numpy as np

from firmware_l515.realsense_l515 import L515CameraConfig, L515DepthCamera


class FakeDepthFrame:
    def get_data(self) -> np.ndarray:
        return np.full((2, 2), 250, dtype=np.uint16)

    def __bool__(self) -> bool:
        return True


class FakeFrames:
    def get_depth_frame(self) -> FakeDepthFrame:
        return FakeDepthFrame()


class FakeDepthSensor:
    def get_depth_scale(self) -> float:
        return 0.001

    def supports(self, _option: object) -> bool:
        return False


class FakeProfile:
    def get_device(self):
        return self

    def first_depth_sensor(self) -> FakeDepthSensor:
        return FakeDepthSensor()


class FakePipeline:
    def __init__(self) -> None:
        self.wait_timeouts: list[int | None] = []
        self.stopped = False

    def start(self, _config: object) -> FakeProfile:
        return FakeProfile()

    def wait_for_frames(self, timeout_ms: int | None = None) -> FakeFrames:
        self.wait_timeouts.append(timeout_ms)
        return FakeFrames()

    def stop(self) -> None:
        self.stopped = True


class FakeConfig:
    def enable_stream(self, *_args: object) -> None:
        return None


class RealSenseL515Tests(unittest.TestCase):
    def test_read_depth_frame_uses_wait_timeout_ms(self) -> None:
        pipeline = FakePipeline()
        fake_rs = SimpleNamespace(
            pipeline=lambda: pipeline,
            config=FakeConfig,
            stream=SimpleNamespace(depth=object()),
            format=SimpleNamespace(z16=object()),
            option=SimpleNamespace(emitter_enabled=object()),
        )
        previous = sys.modules.get("pyrealsense2")
        sys.modules["pyrealsense2"] = fake_rs
        try:
            camera = L515DepthCamera(L515CameraConfig(warmup_frames=2, timeout_ms=1000))

            camera.start()
            depth = camera.read_depth_frame()
            camera.stop()
        finally:
            if previous is None:
                sys.modules.pop("pyrealsense2", None)
            else:
                sys.modules["pyrealsense2"] = previous

        self.assertEqual(depth.tolist(), [[250, 250], [250, 250]])
        self.assertEqual(pipeline.wait_timeouts, [1000, 1000, 1000])
        self.assertTrue(pipeline.stopped)


if __name__ == "__main__":
    unittest.main()
