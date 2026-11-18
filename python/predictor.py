# 「讀心」預測器：用馬可夫鏈（Markov chain）學習玩家的出拳習慣
import random
from collections import Counter, defaultdict

MOVES = ["rock", "paper", "scissors"]
# COUNTER[x] = 能贏 x 的拳
COUNTER = {"rock": "paper", "paper": "scissors", "scissors": "rock"}


def judge(player: str, ai: str) -> str:
    """回傳 'player'（玩家贏）、'ai'（板子贏）或 'draw'。"""
    if player == ai:
        return "draw"
    return "player" if COUNTER[ai] == player else "ai"


class MarkovPredictor:
    """
    記錄玩家每一拳，預測下一拳：
      1. 二階：看「前兩拳」之後你最常出什麼（例如：石頭、布 → 常接剪刀）
      2. 一階：看「前一拳」之後你最常出什麼
      3. 頻率：你整體最常出什麼
    資料不夠時就用隨機出拳。
    """

    def __init__(self, min_rounds: int = 3):
        self.min_rounds = min_rounds
        self.history: list[str] = []
        self.order1: dict[tuple, Counter] = defaultdict(Counter)
        self.order2: dict[tuple, Counter] = defaultdict(Counter)

    def reset(self):
        self.__init__(self.min_rounds)

    def add(self, move: str):
        h = self.history
        if len(h) >= 1:
            self.order1[(h[-1],)][move] += 1
        if len(h) >= 2:
            self.order2[(h[-2], h[-1])][move] += 1
        h.append(move)

    def predict(self):
        """回傳 (預測玩家會出的拳, 機率 0~1, 使用的方法)；資料不足回傳 (None, 0, 'random')。"""
        h = self.history
        if len(h) < self.min_rounds:
            return None, 0.0, "random"

        candidates = []
        if len(h) >= 2:
            candidates.append((self.order2.get((h[-2], h[-1])), "markov-2"))
        candidates.append((self.order1.get((h[-1],)), "markov-1"))
        candidates.append((Counter(h), "frequency"))

        for counts, method in candidates:
            if counts and sum(counts.values()) >= 2:
                total = sum(counts.values())
                best = max(MOVES, key=lambda m: (counts[m], random.random()))
                return best, counts[best] / total, method
        return None, 0.0, "random"

    def choose_ai_move(self):
        """板子出拳：預測有把握就出剋制的拳，否則隨機。"""
        predicted, prob, method = self.predict()
        if predicted is None or prob < 0.4:
            return random.choice(MOVES), predicted, prob, method
        return COUNTER[predicted], predicted, prob, method
