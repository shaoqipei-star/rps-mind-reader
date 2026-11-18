# 在 UNO Q 上把「手部 21 個關節座標」分類成 石頭 / 剪刀 / 布
#
# 關節編號（MediaPipe Hand Landmarks）：
#   0 手腕
#   1-4 大拇指   5-8 食指   9-12 中指   13-16 無名指   17-20 小指
#   每根手指：MCP(指根) → PIP → DIP → TIP(指尖)
import math

FINGERS = {  # 名稱: (MCP, PIP, TIP)
    "index": (5, 6, 8),
    "middle": (9, 10, 12),
    "ring": (13, 14, 16),
    "pinky": (17, 18, 20),
}


def _dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def finger_states(pts):
    """判斷四根手指是否伸直：指尖離手腕的距離 明顯大於 PIP 關節離手腕的距離 → 伸直。"""
    wrist = pts[0]
    palm = _dist(wrist, pts[9]) or 1e-6  # 手掌大小，用來做比例（手離鏡頭遠近都適用）
    states = {}
    for name, (mcp, pip, tip) in FINGERS.items():
        tip_d = _dist(wrist, pts[tip]) / palm
        pip_d = _dist(wrist, pts[pip]) / palm
        states[name] = tip_d > pip_d * 1.15
    return states


def classify(landmarks, aspect=4 / 3):
    """
    landmarks: 21 個 [x, y]（0~1 正規化座標）
    aspect: 畫面寬/高，用來把座標轉成等比例
    回傳 (move 或 None, 伸直的手指 dict)
    """
    if not landmarks or len(landmarks) != 21:
        return None, {}
    pts = [(p[0] * aspect, p[1]) for p in landmarks]
    s = finger_states(pts)
    n = sum(s.values())

    if n == 0:
        move = "rock"
    elif s["index"] and s["middle"] and not s["ring"] and not s["pinky"]:
        move = "scissors"
    elif n >= 4:
        move = "paper"
    else:
        move = None  # 不是猜拳手勢（例如只比一根手指）
    return move, s
