# 讀心猜拳 AI — UNO Q Linux 端（Python）
#
# 流程：
#   瀏覽器（Mac 鏡頭 + MediaPipe 手部關節偵測）→ 透過 WebSocket 傳 21 個關節座標
#   → 這裡判斷手勢、用馬可夫鏈預測你的下一拳 → 透過 Bridge 叫 MCU 在 LED 點陣上顯示
import random
import sys
import threading
import time
from pathlib import Path

from arduino.app_utils import App, Bridge, Logger
from arduino.app_bricks.web_ui import WebUI

sys.path.insert(0, str(Path(__file__).resolve().parent))
from icons import icon_bytes  # noqa: E402
from gesture import classify  # noqa: E402
from predictor import MarkovPredictor, judge, MOVES  # noqa: E402

logger = Logger("RPS-AI")

# ---------------------------------------------------------------- Web UI
# 用 HTTPS，瀏覽器才允許網頁使用 Mac 的鏡頭
try:
    ui = WebUI(use_tls=True)
except TypeError:  # 舊版系統沒有 use_tls
    ui = WebUI()
    logger.warning("WebUI 不支援 HTTPS，請更新板子系統")

# ---------------------------------------------------------------- LED 點陣 / RGB 燈（MCU）
def show(icon: str):
    try:
        Bridge.call("draw", icon_bytes(icon))
    except Exception as e:
        logger.error(f"draw 失敗: {e}")


def rgb(color: int):
    """0=關 1=紅 2=綠 3=藍"""
    try:
        Bridge.call("set_rgb", color)
    except Exception as e:
        logger.error(f"set_rgb 失敗: {e}")


# ---------------------------------------------------------------- 手勢分類（在 UNO Q 上）
model_status = {"ready": True, "message": "UNO Q 已就緒，等待瀏覽器傳來手部關節"}

# 最近辨識到的手勢（給遊戲判斷用）
latest = {"move": None, "time": 0.0, "streak": 0}
latest_lock = threading.Lock()


def record_move(move):
    with latest_lock:
        if move is not None and move == latest["move"]:
            latest["streak"] += 1
        else:
            latest["streak"] = 1 if move else 0
        latest["move"] = move
        latest["time"] = time.time()


def on_landmarks(sid, data):
    """瀏覽器傳來 21 個手部關節座標 → UNO Q 判斷是石頭、剪刀還是布。"""
    t0 = time.perf_counter()
    move, fingers = classify(data.get("landmarks") or [], data.get("aspect", 4 / 3))
    record_move(move)
    us = int((time.perf_counter() - t0) * 1_000_000)
    return {"move": move, "fingers": fingers, "us": us}


def on_manual_move(sid, data):
    """沒有鏡頭時的備案：用網頁按鈕出拳。"""
    move = data.get("move")
    if move in MOVES:
        record_move(move)
        record_move(move)  # 按鈕一次就算穩定


# ---------------------------------------------------------------- 遊戲
predictor = MarkovPredictor()
score = {"player": 0, "ai": 0, "draw": 0}
rounds = []  # 每局紀錄
busy = threading.Lock()


def wait_for_player_move(reveal_time: float, timeout: float = 2.5):
    """喊「出！」之後，等到連續兩張畫面都是同一個手勢。"""
    deadline = reveal_time + timeout
    while time.time() < deadline:
        with latest_lock:
            if latest["time"] >= reveal_time + 0.15 and latest["move"] and latest["streak"] >= 2:
                return latest["move"]
        time.sleep(0.03)
    return None


def play_round():
    if not busy.acquire(blocking=False):
        return
    try:
        # 1. 板子先決定要出什麼（在看到你的手之前就鎖定，公平！）
        ai_move, predicted, prob, method = predictor.choose_ai_move()
        ui.send_message("round_start", {})
        rgb(0)

        # 2. 倒數 3、2、1
        for n in ("3", "2", "1"):
            show(n)
            ui.send_message("countdown", {"n": n})
            time.sleep(0.7)
        show("go")
        ui.send_message("countdown", {"n": "出！"})
        reveal = time.time()

        # 3. 看你出什麼
        player_move = wait_for_player_move(reveal)
        if player_move is None:
            show("question")
            ui.send_message("round_result", {"error": "沒看到你的手，再試一次！"})
            time.sleep(1.2)
            show("idle")
            return

        # 4. 判斷勝負、更新學習資料
        winner = judge(player_move, ai_move)
        hit = predicted == player_move
        predictor.add(player_move)
        score[winner] += 1
        rounds.append({"player": player_move, "ai": ai_move, "winner": winner,
                       "predicted": predicted, "prob": round(prob, 2), "hit": hit})

        # 5. 顯示：先秀板子出的拳，再秀表情和 RGB 燈
        show(ai_move)
        ui.send_message("round_result", {
            "player": player_move, "ai": ai_move, "winner": winner,
            "predicted": predicted, "prob": round(prob, 2), "method": method,
            "hit": hit, "score": score, "rounds": rounds[-20:],
            "ai_win_rate": ai_win_rate(),
        })
        time.sleep(1.5)
        show({"ai": "happy", "player": "sad", "draw": "draw"}[winner])
        rgb({"ai": 1, "player": 2, "draw": 3}[winner])
    finally:
        busy.release()


def ai_win_rate():
    decided = score["ai"] + score["player"]
    return round(score["ai"] / decided, 2) if decided else 0.0


def on_start(sid, data):
    threading.Thread(target=play_round, daemon=True).start()


def on_reset(sid, data):
    predictor.reset()
    rounds.clear()
    for k in score:
        score[k] = 0
    show("idle")
    rgb(0)
    ui.send_message("reset_done", {"score": score})


def on_connect(sid):
    ui.send_message("status", model_status)
    ui.send_message("reset_done", {"score": score, "rounds": rounds[-20:]})


ui.on_connect(on_connect)
ui.on_message("landmarks", on_landmarks)
ui.on_message("manual_move", on_manual_move)
ui.on_message("start_round", on_start)
ui.on_message("reset", on_reset)


# 待機動畫：偶爾眨眼
def idle_loop():
    time.sleep(2)
    show("idle")
    while True:
        time.sleep(random.uniform(3, 6))
        if busy.acquire(blocking=False):
            try:
                if not rounds or time.time() - latest["time"] > 5:
                    show("blink")
                    time.sleep(0.15)
                    show("idle")
            finally:
                busy.release()


threading.Thread(target=idle_loop, daemon=True).start()

App.run()
