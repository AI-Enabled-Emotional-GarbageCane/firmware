from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from queue import Queue
import time
from typing import Callable

import numpy as np


@dataclass(frozen=True)
class DistanceTriggerConfig:
    trigger_distance_cm: float = 30.0
    cooldown_sec: float = 2.0
    roi_fraction: float = 0.5
    invalid_center_fraction: float = 0.9
    invalid_ratio_threshold: float = 0.70
    min_valid_cm: float = 5.0
    max_valid_cm: float = 300.0


def _center_roi(depth_raw: np.ndarray, fraction: float) -> np.ndarray:
    if depth_raw.ndim != 2:
        raise ValueError("depth frame must be a 2D array")
    fraction = float(np.clip(fraction, 1e-3, 1.0))
    h, w = depth_raw.shape
    roi_h = max(1, int(round(h * fraction)))
    roi_w = max(1, int(round(w * fraction)))
    y0 = max(0, (h - roi_h) // 2)
    x0 = max(0, (w - roi_w) // 2)
    return depth_raw[y0 : y0 + roi_h, x0 : x0 + roi_w]


def _depth_to_cm(depth_raw: np.ndarray, depth_scale_m: float) -> np.ndarray:
    depth_cm = depth_raw.astype(np.float32, copy=False) * float(depth_scale_m) * 100.0
    depth_cm[~np.isfinite(depth_cm)] = 0.0
    return depth_cm


def compute_center_roi_distance_cm(
    depth_raw: np.ndarray,
    *,
    depth_scale_m: float,
    roi_fraction: float = 0.5,
    min_valid_cm: float = 5.0,
    max_valid_cm: float = 300.0,
) -> float | None:
    roi = _center_roi(np.asarray(depth_raw), roi_fraction)
    depth_cm = _depth_to_cm(roi, depth_scale_m)
    valid = depth_cm[(depth_cm >= float(min_valid_cm)) & (depth_cm <= float(max_valid_cm))]
    if valid.size == 0:
        return None
    return round(float(np.median(valid)), 1)


def is_depth_frame_invalid(
    depth_raw: np.ndarray,
    *,
    depth_scale_m: float,
    center_fraction: float = 0.9,
    invalid_ratio_threshold: float = 0.70,
    min_valid_cm: float = 5.0,
    max_valid_cm: float = 300.0,
) -> bool:
    roi = _center_roi(np.asarray(depth_raw), center_fraction)
    if roi.size == 0:
        return True
    depth_cm = _depth_to_cm(roi, depth_scale_m)
    invalid = (depth_cm < float(min_valid_cm)) | (depth_cm > float(max_valid_cm))
    invalid_ratio = float(np.count_nonzero(invalid)) / float(invalid.size)
    return invalid_ratio > float(invalid_ratio_threshold)


class L515DistanceTrigger:
    """Convert L515 depth frames into proximity-only user_detected events.

    YOLO inference stays in the vision module; firmware only owns depth distance
    sensing and the public q_detected/user_detected trigger.
    """

    def __init__(
        self,
        q_detected: Queue[dict[str, object]],
        *,
        config: DistanceTriggerConfig | None = None,
        monotonic: Callable[[], float] = time.monotonic,
        now: Callable[[], datetime] = datetime.now,
    ) -> None:
        self._q_detected = q_detected
        self._config = config or DistanceTriggerConfig()
        self._monotonic = monotonic
        self._now = now
        self._last_emit_at: float | None = None

    def process_depth_frame(self, depth_raw: np.ndarray, *, depth_scale_m: float) -> bool:
        cfg = self._config
        if is_depth_frame_invalid(
            depth_raw,
            depth_scale_m=depth_scale_m,
            center_fraction=cfg.invalid_center_fraction,
            invalid_ratio_threshold=cfg.invalid_ratio_threshold,
            min_valid_cm=cfg.min_valid_cm,
            max_valid_cm=cfg.max_valid_cm,
        ):
            return False

        distance_cm = compute_center_roi_distance_cm(
            depth_raw,
            depth_scale_m=depth_scale_m,
            roi_fraction=cfg.roi_fraction,
            min_valid_cm=cfg.min_valid_cm,
            max_valid_cm=cfg.max_valid_cm,
        )
        if distance_cm is None or distance_cm > cfg.trigger_distance_cm:
            return False

        now_mono = self._monotonic()
        if self._last_emit_at is not None and (now_mono - self._last_emit_at) < cfg.cooldown_sec:
            return False

        self._last_emit_at = now_mono
        self._q_detected.put(
            {
                "event": "user_detected",
                "distance_cm": distance_cm,
                "ts": self._now().isoformat(timespec="seconds"),
            }
        )
        return True
