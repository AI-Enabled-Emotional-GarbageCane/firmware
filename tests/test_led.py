from __future__ import annotations

import unittest

from firmware_l515.led import MockLEDController


class LedTests(unittest.TestCase):
    def test_mock_led_controller_records_valid_statuses(self) -> None:
        led = MockLEDController()

        led.set_status("idle")
        led.set_status("detected")
        led.set_status("camera_error")

        self.assertEqual(led.status, "camera_error")
        self.assertEqual(led.history, ["idle", "detected", "camera_error"])

    def test_mock_led_controller_rejects_unknown_status(self) -> None:
        led = MockLEDController()

        with self.assertRaisesRegex(ValueError, "unsupported LED status"):
            led.set_status("starting")


if __name__ == "__main__":
    unittest.main()
