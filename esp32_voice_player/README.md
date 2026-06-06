# ESP32-S3 Voice Player

ESP32-S3 只負責播放聲音，不執行 GPT-SoVITS、voice cloning、fine-tune 或任何語音模型推論。AGX / Jetson 端決定要播哪一句，ESP32 透過 USB Serial / UART 收到一行 JSON 後，從 SD card 讀取 WAV 並用 I2S 播放。

## Hardware

建議硬體：

- ESP32-S3 development board
- microSD card module
- MAX98357A I2S amplifier
- 4 ohm / 8 ohm speaker

預設腳位在 `esp32_voice_player.ino`：

| 功能 | 預設 GPIO |
|---|---:|
| SD CS | 10 |
| I2S BCLK | 4 |
| I2S LRCLK / WS | 5 |
| I2S DOUT | 6 |

不同開發板請直接改 sketch 內的常數。

## SD Card Layout

SD card 放 GPT-SoVITS 在 AGX 產生好的 16-bit PCM WAV：

```text
/
  sfx/
    ding.wav
  accept/
    accept-01.wav
  reject/
    reject-01.wav
  repeat_reject/
    repeat-01.wav
  low_confidence/
    low-01.wav
  multi_object/
    multi-01.wav
```

支援 mono 或 stereo、16-bit PCM WAV。若 GPT-SoVITS 輸出不是這個格式，先在 AGX 轉檔：

```bash
ffmpeg -i input.wav -ar 44100 -ac 1 -sample_fmt s16 output.wav
```

## Serial Command

AGX / Jetson 端每次送一行 JSON，結尾要有 newline：

```json
{"category":"reject","audio_path":"reject/reject-01.wav","pre_sfx":"ding","pre_delay_ms":500}
```

也接受 vision repo 產生的 `assets/voice/gpt-sovits/reject/reject-01.wav`，ESP32 會自動去掉 `assets/voice/gpt-sovits/` 前綴，改讀 SD card 根目錄下的 `reject/reject-01.wav`。

允許的 `category`：

- `accept`
- `reject`
- `repeat_reject`
- `low_confidence`
- `multi_object`

## Build

用 Arduino IDE / arduino-cli，選 ESP32-S3 board，安裝 Espressif Arduino core 後上傳 `esp32_voice_player.ino`。

這份 sketch 不依賴 ArduinoJson，也不依賴外部音訊播放函式庫；它用 ESP32 I2S driver 直接播放 SD card 中的 PCM WAV。
