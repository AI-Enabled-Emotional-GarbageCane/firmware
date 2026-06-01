from __future__ import annotations

from queue import Queue
import time
from typing import Callable, Protocol

from .distance_trigger import DistanceTriggerConfig, L515DistanceTrigger
from .led import LEDController, VALID_LED_STATUSES
from .realsense_l515 import L515DepthCamera


class DepthCamera(Protocol):
    depth_scale_m: float | None

    def start(self) -> None: ...

    def read_depth_frame(self): ...

    def stop(self) -> None: ...


def run_distance_trigger_loop(
    q_detected: Queue[dict[str, object]],
    *,
    camera: DepthCamera | None = None,
    config: DistanceTriggerConfig | None = None,
    max_frames: int | None = None,
    poll_delay_sec: float = 0.0,
    on_status: Callable[[str], None] | None = None,
    led_controller: LEDController | None = None,
) -> int:
    camera = camera or L515DepthCamera()
    trigger = L515DistanceTrigger(q_detected, config=config)
    processed = 0

    def status(value: str) -> None:
        if led_controller is not None and value in VALID_LED_STATUSES:
            led_controller.set_status(value)
        if on_status is not None:
            on_status(value)

    try:
        status("starting")
        camera.start()
        status("idle")
        while max_frames is None or processed < max_frames:
            depth_raw = camera.read_depth_frame()
            depth_scale_m = camera.depth_scale_m
            if depth_scale_m is None:
                raise RuntimeError("camera did not provide depth_scale_m")
            if trigger.process_depth_frame(depth_raw, depth_scale_m=depth_scale_m):
                status("detected")
            processed += 1
            if poll_delay_sec > 0:
                time.sleep(poll_delay_sec)
    except Exception:
        status("camera_error")
        raise
    finally:
        camera.stop()
    return processed
