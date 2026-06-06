#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKETCH = ROOT / "esp32_voice_player" / "esp32_voice_player.ino"
README = ROOT / "esp32_voice_player" / "README.md"


def fail(message: str) -> None:
    print(f"[FAIL] {message}", file=sys.stderr)
    raise SystemExit(1)


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def main() -> None:
    require(SKETCH.exists(), "missing ESP32 voice player sketch")
    require(README.exists(), "missing ESP32 voice player README")

    sketch = SKETCH.read_text(encoding="utf-8")
    readme = README.read_text(encoding="utf-8")

    for category in ["accept", "reject", "repeat_reject", "low_confidence", "multi_object"]:
        require(category in sketch, f"sketch must support category {category}")
        require(category in readme, f"README must document category {category}")

    for required in ["SD.begin", "i2s_write", "MAX98357A", "audio_path", "pre_delay_ms"]:
        require(required in sketch or required in readme, f"ESP32 voice player must mention/use {required}")

    forbidden_model_terms = ["GPT_SoVITS", "torch", "fine-tune()", "inference()"]
    for term in forbidden_model_terms:
        require(term not in sketch, f"ESP32 sketch must not run model code: {term}")

    require("ESP32-S3 只負責播放聲音" in readme, "README must state ESP32 is playback-only")
    require("AGX" in readme, "README must describe AGX as the model/decision side")

    print("[OK] ESP32 voice player sketch and docs are playback-only and category-complete")


if __name__ == "__main__":
    main()
