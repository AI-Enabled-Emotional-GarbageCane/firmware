# firmware

硬體感測與互動裝置韌體 — [AI 情緒垃圾筒](https://github.com/AI-Enabled-Emotional-GarbageCane/ai-enabled-emotional-garbagecane) 的韌體子系統。

## 職責

- **紅外線 / 距離感測**:偵測使用者與垃圾桶的距離,作為系統觸發源
- 喇叭 / LED 聲光回饋
- 垃圾桶機構(舵機 / 電磁鐵 / 蓋板觸發)

## 介面

- 偵測到使用者 → 發送 `user_detected` trigger 給 vision
- 接收 display 的 `user_action` 指令(開蓋 / 取消)

詳細 API 契約見 [monorepo `docs/api-contract.md`](https://github.com/AI-Enabled-Emotional-GarbageCane/ai-enabled-emotional-garbagecane/blob/main/docs/api-contract.md)。

## 技術棧

TBD(Raspberry Pi / Arduino / ESP32 擇一)
