#include <Arduino.h>
#include <SD.h>
#include <SPI.h>
#include "driver/i2s.h"

// ESP32-S3 + MAX98357A default wiring. Adjust pins for your board.
static constexpr int SD_CS_PIN = 10;
static constexpr int I2S_BCLK_PIN = 4;
static constexpr int I2S_LRCLK_PIN = 5;
static constexpr int I2S_DOUT_PIN = 6;
static constexpr int SERIAL_BAUD = 115200;
static constexpr int DEFAULT_PRE_DELAY_MS = 500;
static constexpr const char *VOICE_ROOT = "/";
static constexpr const char *DING_PATH = "/sfx/ding.wav";

struct WavInfo {
  uint32_t sampleRate = 0;
  uint16_t bitsPerSample = 0;
  uint16_t channels = 0;
  uint32_t dataStart = 0;
  uint32_t dataSize = 0;
};

String serialLine;

uint16_t readLe16(File &file) {
  uint8_t b0 = file.read();
  uint8_t b1 = file.read();
  return static_cast<uint16_t>(b0 | (b1 << 8));
}

uint32_t readLe32(File &file) {
  uint32_t b0 = file.read();
  uint32_t b1 = file.read();
  uint32_t b2 = file.read();
  uint32_t b3 = file.read();
  return b0 | (b1 << 8) | (b2 << 16) | (b3 << 24);
}

bool readTag(File &file, const char *expected) {
  char tag[5] = {0, 0, 0, 0, 0};
  if (file.readBytes(tag, 4) != 4) {
    return false;
  }
  return strncmp(tag, expected, 4) == 0;
}

bool parseWavHeader(File &file, WavInfo &info) {
  if (!readTag(file, "RIFF")) {
    return false;
  }
  readLe32(file);
  if (!readTag(file, "WAVE")) {
    return false;
  }

  bool hasFmt = false;
  bool hasData = false;
  while (file.available()) {
    char chunkId[5] = {0, 0, 0, 0, 0};
    if (file.readBytes(chunkId, 4) != 4) {
      break;
    }
    uint32_t chunkSize = readLe32(file);
    uint32_t nextChunk = file.position() + chunkSize + (chunkSize % 2);

    if (strncmp(chunkId, "fmt ", 4) == 0) {
      uint16_t audioFormat = readLe16(file);
      info.channels = readLe16(file);
      info.sampleRate = readLe32(file);
      readLe32(file);
      readLe16(file);
      info.bitsPerSample = readLe16(file);
      hasFmt = audioFormat == 1;
    } else if (strncmp(chunkId, "data", 4) == 0) {
      info.dataStart = file.position();
      info.dataSize = chunkSize;
      hasData = true;
    }

    file.seek(nextChunk);
    if (hasFmt && hasData) {
      return info.bitsPerSample == 16 && (info.channels == 1 || info.channels == 2);
    }
  }
  return false;
}

void configureI2S(uint32_t sampleRate) {
  i2s_config_t i2sConfig = {
      .mode = static_cast<i2s_mode_t>(I2S_MODE_MASTER | I2S_MODE_TX),
      .sample_rate = sampleRate,
      .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,
      .channel_format = I2S_CHANNEL_FMT_RIGHT_LEFT,
      .communication_format = I2S_COMM_FORMAT_STAND_I2S,
      .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
      .dma_buf_count = 8,
      .dma_buf_len = 256,
      .use_apll = false,
      .tx_desc_auto_clear = true,
      .fixed_mclk = 0,
  };
  i2s_pin_config_t pinConfig = {
      .bck_io_num = I2S_BCLK_PIN,
      .ws_io_num = I2S_LRCLK_PIN,
      .data_out_num = I2S_DOUT_PIN,
      .data_in_num = I2S_PIN_NO_CHANGE,
  };

  i2s_driver_uninstall(I2S_NUM_0);
  i2s_driver_install(I2S_NUM_0, &i2sConfig, 0, nullptr);
  i2s_set_pin(I2S_NUM_0, &pinConfig);
  i2s_set_clk(I2S_NUM_0, sampleRate, I2S_BITS_PER_SAMPLE_16BIT, I2S_CHANNEL_STEREO);
  i2s_zero_dma_buffer(I2S_NUM_0);
}

bool playWav(const String &path) {
  File file = SD.open(path.c_str(), FILE_READ);
  if (!file) {
    Serial.print("{\"ok\":false,\"error\":\"missing_audio\",\"path\":\"");
    Serial.print(path);
    Serial.println("\"}");
    return false;
  }

  WavInfo info;
  if (!parseWavHeader(file, info)) {
    Serial.print("{\"ok\":false,\"error\":\"unsupported_wav\",\"path\":\"");
    Serial.print(path);
    Serial.println("\"}");
    file.close();
    return false;
  }

  configureI2S(info.sampleRate);
  file.seek(info.dataStart);

  uint8_t inputBuffer[1024];
  int16_t stereoBuffer[1024];
  uint32_t remaining = info.dataSize;
  while (remaining > 0) {
    size_t toRead = min<uint32_t>(sizeof(inputBuffer), remaining);
    size_t bytesRead = file.read(inputBuffer, toRead);
    if (bytesRead == 0) {
      break;
    }
    remaining -= bytesRead;

    if (info.channels == 1) {
      size_t samples = bytesRead / 2;
      int16_t *mono = reinterpret_cast<int16_t *>(inputBuffer);
      for (size_t i = 0; i < samples; i++) {
        stereoBuffer[i * 2] = mono[i];
        stereoBuffer[i * 2 + 1] = mono[i];
      }
      size_t bytesWritten = 0;
      i2s_write(I2S_NUM_0, stereoBuffer, samples * 4, &bytesWritten, portMAX_DELAY);
    } else {
      size_t bytesWritten = 0;
      i2s_write(I2S_NUM_0, inputBuffer, bytesRead, &bytesWritten, portMAX_DELAY);
    }
  }

  file.close();
  i2s_zero_dma_buffer(I2S_NUM_0);
  Serial.print("{\"ok\":true,\"played\":\"");
  Serial.print(path);
  Serial.println("\"}");
  return true;
}

String jsonStringField(const String &json, const String &field) {
  String needle = "\"" + field + "\"";
  int key = json.indexOf(needle);
  if (key < 0) {
    return "";
  }
  int colon = json.indexOf(':', key + needle.length());
  int firstQuote = json.indexOf('"', colon + 1);
  int secondQuote = json.indexOf('"', firstQuote + 1);
  if (colon < 0 || firstQuote < 0 || secondQuote < 0) {
    return "";
  }
  return json.substring(firstQuote + 1, secondQuote);
}

int jsonIntField(const String &json, const String &field, int defaultValue) {
  String needle = "\"" + field + "\"";
  int key = json.indexOf(needle);
  if (key < 0) {
    return defaultValue;
  }
  int colon = json.indexOf(':', key + needle.length());
  if (colon < 0) {
    return defaultValue;
  }
  return json.substring(colon + 1).toInt();
}

bool isAllowedCategory(const String &category) {
  return category == "accept" || category == "reject" || category == "repeat_reject" ||
         category == "low_confidence" || category == "multi_object";
}

String normalizeAudioPath(String audioPath, const String &category) {
  audioPath.trim();
  audioPath.replace("\\", "/");
  audioPath.replace("assets/voice/gpt-sovits/", "");
  while (audioPath.startsWith("/")) {
    audioPath = audioPath.substring(1);
  }

  if (audioPath.length() == 0 && isAllowedCategory(category)) {
    audioPath = category + "/" + category + "-01.wav";
  }
  if (audioPath.indexOf("..") >= 0 || !audioPath.endsWith(".wav")) {
    return "";
  }
  return String(VOICE_ROOT) + audioPath;
}

void handleCommand(const String &line) {
  String category = jsonStringField(line, "category");
  String audioPath = normalizeAudioPath(jsonStringField(line, "audio_path"), category);
  String preSfx = jsonStringField(line, "pre_sfx");
  int preDelayMs = jsonIntField(line, "pre_delay_ms", DEFAULT_PRE_DELAY_MS);

  if (!isAllowedCategory(category)) {
    Serial.println("{\"ok\":false,\"error\":\"invalid_category\"}");
    return;
  }
  if (audioPath.length() == 0) {
    Serial.println("{\"ok\":false,\"error\":\"invalid_audio_path\"}");
    return;
  }

  if (preSfx == "ding" && SD.exists(DING_PATH)) {
    playWav(DING_PATH);
  }
  if (preDelayMs > 0) {
    delay(preDelayMs);
  }
  playWav(audioPath);
}

void setup() {
  Serial.begin(SERIAL_BAUD);
  delay(300);

  if (!SD.begin(SD_CS_PIN)) {
    Serial.println("{\"ok\":false,\"error\":\"sd_init_failed\"}");
  } else {
    Serial.println("{\"ok\":true,\"status\":\"esp32_voice_player_ready\"}");
  }
  configureI2S(44100);
}

void loop() {
  while (Serial.available()) {
    char ch = static_cast<char>(Serial.read());
    if (ch == '\n') {
      serialLine.trim();
      if (serialLine.length() > 0) {
        handleCommand(serialLine);
      }
      serialLine = "";
    } else if (ch != '\r') {
      serialLine += ch;
    }
  }
}
