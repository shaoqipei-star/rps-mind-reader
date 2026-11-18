// 讀心猜拳 AI — UNO Q MCU 端（STM32U585）
// 負責：即時驅動 8x13 LED 點陣（256 階亮度）與板載 RGB LED
// Python（Linux 端）透過 Bridge 呼叫這裡提供的 draw() 和 set_rgb()

#include <Arduino_RouterBridge.h>
#include <Arduino_LED_Matrix.h>
#include <vector>

Arduino_LED_Matrix matrix;

const uint8_t FRAME_SIZE = 8 * 13;
uint8_t frame[FRAME_SIZE] = {0};

// 板載 RGB LED4（LED4_R / LED4_G / LED4_B 是內建腳位名稱，LOW = 亮）

void setup() {
  matrix.begin();
  matrix.setGrayscaleBits(8);  // 每顆 LED 0~255 亮度
  matrix.clear();

  pinMode(LED4_R, OUTPUT);
  pinMode(LED4_G, OUTPUT);
  pinMode(LED4_B, OUTPUT);
  set_rgb(0);

  Bridge.begin();
  Bridge.provide("draw", draw);
  Bridge.provide("set_rgb", set_rgb);
}

void loop() {
  matrix.draw(frame);
  delay(10);
}

// Python 傳來 104 個位元組，更新畫面
void draw(std::vector<uint8_t> newFrame) {
  size_t len = min(newFrame.size(), (size_t)FRAME_SIZE);
  memcpy(frame, newFrame.data(), len);
}

// 0=關 1=紅（板子贏） 2=綠（你贏） 3=藍（平手）
void set_rgb(int color) {
  digitalWrite(LED4_R, color == 1 ? LOW : HIGH);
  digitalWrite(LED4_G, color == 2 ? LOW : HIGH);
  digitalWrite(LED4_B, color == 3 ? LOW : HIGH);
}
