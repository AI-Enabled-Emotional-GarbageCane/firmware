from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class L515CameraConfig:
    width: int = 640
    height: int = 480
    fps: int = 30
    warmup_frames: int = 30
    timeout_ms: int = 1000
    laser_on: bool = True


class L515DepthCamera:
    def __init__(self, config: L515CameraConfig | None = None) -> None:
        self._config = config or L515CameraConfig()
        self._rs = None
        self._pipeline = None
        self.depth_scale_m: float | None = None

    def start(self) -> None:
        import pyrealsense2 as rs

        pipeline = rs.pipeline()
        cfg = rs.config()
        cfg.enable_stream(
            rs.stream.depth,
            self._config.width,
            self._config.height,
            rs.format.z16,
            self._config.fps,
        )

        profile = pipeline.start(cfg)
        depth_sensor = profile.get_device().first_depth_sensor()
        self.depth_scale_m = float(depth_sensor.get_depth_scale())

        if depth_sensor.supports(rs.option.emitter_enabled):
            depth_sensor.set_option(rs.option.emitter_enabled, 1 if self._config.laser_on else 0)

        try:
            for _ in range(max(0, int(self._config.warmup_frames))):
                self._wait_for_frames(pipeline, during_warmup=True)
        except RuntimeError:
            pipeline.stop()
            raise

        self._rs = rs
        self._pipeline = pipeline

    def read_depth_frame(self) -> np.ndarray:
        if self._pipeline is None:
            raise RuntimeError("L515DepthCamera.start() must be called before reading frames")
        frames = self._wait_for_frames(self._pipeline, during_warmup=False)
        depth_frame = frames.get_depth_frame()
        if not depth_frame:
            raise RuntimeError("missing L515 depth frame")
        return np.asanyarray(depth_frame.get_data())

    def stop(self) -> None:
        if self._pipeline is not None:
            self._pipeline.stop()
            self._pipeline = None

    def _wait_for_frames(self, pipeline, *, during_warmup: bool):
        timeout_ms = int(self._config.timeout_ms)
        try:
            return pipeline.wait_for_frames(timeout_ms)
        except RuntimeError as exc:
            phase = " during warmup" if during_warmup else ""
            raise RuntimeError(f"timed out waiting for L515 depth frame{phase} after {timeout_ms} ms") from exc
