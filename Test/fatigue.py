"""
fatigue.py — Additional fatigue signal detection using MediaPipe landmarks
Signals:
  1. Blink rate  — blinks per minute (normal: 15-20, fatigued: <10)
  2. PERCLOS     — % of time eyes closed in last 60s (>30% = fatigued)
  3. Brow furrow — eyebrow distance ratio (frowning = fatigue/stress)
"""
import time
import numpy as np
from collections import deque

# ── Thresholds ────────────────────────────────────────────────────
BLINK_EAR_THRESH  = 0.20   # EAR below this = blink frame
BLINK_MIN_FRAMES  = 2      # minimum consecutive frames to count as blink
PERCLOS_WINDOW    = 60.0   # seconds
PERCLOS_THRESHOLD = 0.30   # 30% eyes-closed = fatigued
BLINK_RATE_LOW    = 8      # blinks/min below this = fatigued
BROW_FURROW_THRESH= 0.65   # normalized brow distance ratio below this = frown


class FatigueDetector:
    def __init__(self, ear_threshold: float):
        self.ear_threshold = ear_threshold

        # Blink tracking
        self._blink_frames     = 0
        self._blink_timestamps = deque()
        self._eye_was_closed   = False

        # PERCLOS
        self._perclos_history  = deque()

        # Brow baseline
        self._brow_baseline    = None
        self._brow_samples     = []

        # Output state
        self.blink_rate    = 0.0
        self.perclos       = 0.0
        self.is_frowning   = False
        self.fatigue_score = 0
        self.fatigue_flags = []

    # ── Per-frame update ──────────────────────────────────────────
    def update(self, face_landmarks, frame_w: int, frame_h: int, avg_ear: float):
        now = time.time()

        def pt(idx):
            lm = face_landmarks.landmark[idx]
            return np.array([lm.x * frame_w, lm.y * frame_h])

        self._update_blink(avg_ear, now)
        self._update_perclos(avg_ear, now)
        self._update_brow(pt)
        self._update_score()

    def _update_blink(self, ear: float, now: float):
        closed = ear < BLINK_EAR_THRESH
        if closed:
            self._blink_frames += 1
        else:
            if self._eye_was_closed and self._blink_frames >= BLINK_MIN_FRAMES:
                self._blink_timestamps.append(now)
            self._blink_frames = 0
        self._eye_was_closed = closed

        cutoff = now - 60.0
        while self._blink_timestamps and self._blink_timestamps[0] < cutoff:
            self._blink_timestamps.popleft()
        elapsed = min(60.0, now - self._blink_timestamps[0]) if self._blink_timestamps else 60.0
        self.blink_rate = len(self._blink_timestamps) / elapsed * 60.0 if elapsed > 0 else 0.0

    def _update_perclos(self, ear: float, now: float):
        closed = ear < self.ear_threshold
        self._perclos_history.append((now, closed))
        cutoff = now - PERCLOS_WINDOW
        while self._perclos_history and self._perclos_history[0][0] < cutoff:
            self._perclos_history.popleft()
        if self._perclos_history:
            self.perclos = sum(1 for _, c in self._perclos_history if c) / len(self._perclos_history)

    def _update_brow(self, pt):
        try:
            left_inner  = pt(46)
            right_inner = pt(276)
            brow_dist   = np.linalg.norm(right_inner - left_inner)
            face_w      = np.linalg.norm(pt(356) - pt(127))
            if face_w < 1:
                return
            ratio = brow_dist / face_w

            if self._brow_baseline is None:
                self._brow_samples.append(ratio)
                if len(self._brow_samples) >= 60:
                    self._brow_baseline = float(np.mean(self._brow_samples))
                    print(f"[Fatigue] Brow baseline: {self._brow_baseline:.3f}")
                return

            self.is_frowning = ratio < self._brow_baseline * BROW_FURROW_THRESH
        except Exception:
            pass

    def _update_score(self):
        flags = []
        score = 0

        if self.perclos >= PERCLOS_THRESHOLD:
            flags.append("PERCLOS")
            score += 2
        if 0 < self.blink_rate < BLINK_RATE_LOW:
            flags.append("LOW BLINK")
            score += 1
        if self.is_frowning:
            flags.append("FROWNING")
            score += 1

        self.fatigue_score = min(score, 4)
        self.fatigue_flags = flags

    # ── Terminal print (on flag change) ──────────────────────────
    def print_status(self):
        if self.fatigue_flags:
            print(f"[Fatigue] score:{self.fatigue_score}/4  "
                  f"blink:{self.blink_rate:.0f}/min  "
                  f"PERCLOS:{self.perclos*100:.0f}%  "
                  f"flags: {', '.join(self.fatigue_flags)}")