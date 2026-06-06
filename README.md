# AI 情緒垃圾筒 — Intel RealSense L515 depth sensing firmware

本 repo 是 AI 情緒垃圾筒的韌體子系統。v0.3 定稿硬體為 Intel RealSense L515 depth camera。

## 職責範圍

Firmware 只負責：

- 使用 Intel RealSense L515 depth stream 偵測使用者是否靠近垃圾桶。
- 以中央 ROI depth median 計算距離。
- 當距離低於閾值時，透過 `q_detected` 送出 `user_detected` 事件給 vision。
- 控制或暴露 LED 狀態：`idle`、`detected`、`camera_error`。

Firmware 不負責：

- YOLO inference；物件辨識屬於 vision。
- roast voice；語音回饋屬於 display。
- display UI 或 admin panel。
- 使用者按鈕。

## Public Contract

`firmware -> vision`

```json
{ "event": "user_detected", "distance_cm": 25.0, "ts": "2026-05-31T21:00:00" }
```

事件欄位維持中心契約不變：

- `event`: 固定為 `user_detected`
- `distance_cm`: L515 中央 ROI 有效 depth median，單位為公分
- `ts`: ISO 8601 timestamp

## L515 距離觸發流程

- 使用 `pyrealsense2` 啟動 L515 depth stream，預設 `640x480@30fps`。
- `wait_for_frames(timeout_ms=1000)`，避免 camera read 永久阻塞。
- 使用 RealSense depth sensor 回報的 `depth_scale`，不硬寫比例。
- 取畫面中央 ROI，預設中央 50%。
- 過濾無效 depth，取有效距離 median。
- 預設 `trigger_distance_cm = 30.0`。
- 預設 `required_consecutive_frames = 3`，避免單幀雜訊觸發。
- 預設 `release_distance_cm = 45.0`，使用 hysteresis 等使用者離開後才重新 armed。
- 預設 `cooldown_sec = 2.0`，避免短時間重複送出事件。
- L515 start/read 失敗時，狀態會切到 `camera_error` 並把錯誤往上拋。

## 使用方式

Launcher 以 `multiprocessing.Queue` 建立 `q_detected`，再啟動 firmware loop：

```python
from multiprocessing import Queue

from firmware_l515.runner import run_distance_trigger_loop

q_detected = Queue()
run_distance_trigger_loop(q_detected)
```

測試 L515 depth pipeline 時，可以先限制處理幀數：

```python
from multiprocessing import Queue

from firmware_l515.distance_trigger import DistanceTriggerConfig
from firmware_l515.led import MockLEDController
from firmware_l515.runner import run_distance_trigger_loop

q_detected = Queue()
led = MockLEDController()

processed = run_distance_trigger_loop(
    q_detected,
    config=DistanceTriggerConfig(trigger_distance_cm=30.0),
    max_frames=120,
    led_controller=led,
)

print("processed frames:", processed)
print("LED status:", led.status)
while not q_detected.empty():
    print(q_detected.get())
```

## 測試

完整 contract 與單元測試驗證：

```bash
./validate.sh
```

單獨執行單元測試：

```powershell
python -m unittest discover -s tests -v
```
