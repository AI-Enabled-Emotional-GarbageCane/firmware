from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, Literal


LEDStatus = Literal["idle", "detected", "camera_error"]
VALID_LED_STATUSES: tuple[str, ...] = ("idle", "detected", "camera_error")


class LEDController(Protocol):
    def set_status(self, status: LEDStatus) -> None: ...


@dataclass
class MockLEDController:
    status: LEDStatus = "idle"
    history: list[LEDStatus] = field(default_factory=list)

    def set_status(self, status: LEDStatus) -> None:
        if status not in VALID_LED_STATUSES:
            raise ValueError(f"unsupported LED status: {status}")
        self.status = status
        self.history.append(status)
