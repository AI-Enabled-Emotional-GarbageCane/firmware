# firmware

硬體感測與互動裝置韌體 - [AI 情緒垃圾筒](https://github.com/AI-Enabled-Emotional-GarbageCane/ai-enabled-emotional-garbagecane) 的韌體子系統。

## 職責

- 使用 Intel RealSense L515 depth 串流偵測使用者是否靠近垃圾桶。
- 偵測到使用者距離小於閾值時，透過 `q_detected` 發送 `user_detected` 給 vision。
- LED 可依狀態顯示 `idle`、`detected`、`camera_error`。

Firmware 不負責模型推論、UI、語音播放、使用者確認流程或開蓋機構。

Intel RealSense L515 是 v0.2 定稿的 camera hardware。中心文件與跨 repo 契約應一致使用 L515。

## Public Event

`firmware -> vision`

```json
{ "event": "user_detected", "distance_cm": 25.0, "ts": "2026-05-31T21:00:00" }
```

欄位必須符合中心契約 `contract.v0.2.json`：

- `event`: 固定為 `user_detected`
- `distance_cm`: L515 中央 ROI 有效深度中位數，單位為公分
- `ts`: 本機 ISO8601 時間

## 使用方式

Launcher 建立 `multiprocessing.Queue` 後，把 `q_detected` 傳給 firmware loop：

```python
from multiprocessing import Queue

from firmware_l515.runner import run_distance_trigger_loop

q_detected = Queue()
run_distance_trigger_loop(q_detected)
```

測試 L515 depth pipeline 時，可以先只跑有限幀數：

```python
from multiprocessing import Queue

from firmware_l515.distance_trigger import DistanceTriggerConfig
from firmware_l515.runner import run_distance_trigger_loop

q_detected = Queue()
processed = run_distance_trigger_loop(
    q_detected,
    config=DistanceTriggerConfig(trigger_distance_cm=30.0, cooldown_sec=2.0),
    max_frames=120,
)
print("processed frames:", processed)
while not q_detected.empty():
    print(q_detected.get())
```

## L515 距離判斷

- 預設解析度為 `640x480@30fps`。
- 使用 depth frame 中央 `50%` ROI。
- 只保留有效 depth，將 raw Z16 乘以 L515 實際 `depth_scale` 後轉成公分。
- 用 median distance 判斷距離，避免單點雜訊。
- 預設距離閾值為 `30cm`。
- 預設 cooldown 為 `2s`，避免連續觸發 vision。

## 測試

```powershell
python -m unittest discover -s tests -v
```
