# 讀心猜拳 AI（RPS Mind Reader）

在 **Arduino UNO Q** 上執行的邊緣 AI 猜拳對戰。你對著鏡頭出拳，瀏覽器先偵測出手部 21 個關節，UNO Q 再用這些座標**在板子上判斷手勢**，同時用**馬可夫鏈**學習你的出拳習慣，預測你下一拳後出剋制你的手勢。結果顯示在板載 8×13 LED 點陣與 RGB LED 上。

全程在本地端運算（模型與函式庫都放在板子上），不使用任何雲端 API，也不需要任何金鑰。

> 開發紀錄：原本打算直接在板子上跑 MediaPipe Python，但官方 aarch64 版本需要 ARMv8.2 指令集（dotprod、fp16 等），UNO Q 的 Cortex-A53 是 ARMv8.0，執行時會出現 SIGILL（exit code 132）。因此改成「瀏覽器偵測關節、板子負責判斷與決策」的分工，傳輸的資料也從整張影像縮小成 42 個數字。

## 系統架構

```
 Mac 瀏覽器（鏡頭 + MediaPipe Hand Landmarker, WebAssembly）
   │  21 個手部關節座標（HTTPS + WebSocket，約 12 次/秒）
   ▼
 UNO Q Linux 端（Qualcomm QRB2210, Python）
   ├─ gesture.py：用關節幾何判斷哪幾根手指伸直 → 石頭 / 剪刀 / 布
   ├─ MarkovPredictor：二階 → 一階 → 頻率，預測你的下一拳
   └─ 遊戲邏輯（板子在看到你出拳「之前」就先鎖定自己的拳）
   │  Bridge (RPC)
   ▼
 UNO Q MCU 端（STM32U585, Arduino）
   ├─ 8×13 LED 點陣：倒數、板子出的拳、勝負表情
   └─ RGB LED4：紅＝板子贏、綠＝你贏、藍＝平手
```

## 檔案

| 路徑 | 說明 |
| --- | --- |
| `python/main.py` | Linux 端主程式：Web 伺服器、手勢辨識、遊戲流程 |
| `python/predictor.py` | 馬可夫鏈出拳預測器 |
| `python/icons.py` | LED 點陣圖示 |
| `python/gesture.py` | 由手部關節判斷石頭 / 剪刀 / 布 |
| `sketch/sketch.ino` | MCU 端：驅動 LED 點陣與 RGB LED |
| `assets/` | 網頁介面（鏡頭、比分、AI 預測） |
| `assets/libs/mediapipe/` | MediaPipe Tasks Vision（WebAssembly，Apache 2.0） |
| `assets/models/hand_landmarker.task` | Google MediaPipe 手部關節模型（Apache 2.0） |

## 執行方式

1. 把整個資料夾複製到板子的 `~/ArduinoApps/`：
   `scp -r rps-mind-reader arduino@<板子名稱>.local:~/ArduinoApps/`
2. 在 Arduino App Lab 的 **My Apps** 打開 **RPS Mind Reader**，按 **Run**。
3. 用 Chrome 打開 `https://<板子名稱>.local:7000`，略過自簽憑證警告，並允許使用鏡頭。
4. 按空白鍵開始，倒數到「出！」時出拳：✊ 石頭、✌️ 剪刀、🖐 布。

沒有鏡頭時，也可以在「出！」之後按網頁按鈕或鍵盤 1 / 2 / 3 出拳。

## 致謝

- 手部關節模型與函式庫：[MediaPipe Hand Landmarker](https://ai.google.dev/edge/mediapipe/solutions/vision/hand_landmarker)（Apache 2.0）
- Socket.IO client（MIT）
