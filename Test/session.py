"""
session.py — Driving session data collection and SQLite storage
Snapshots every 5 seconds, saved to DB on session end.
"""
import sqlite3
import json
import os
import time
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "users.db")

SNAPSHOT_INTERVAL = 5.0  # seconds


def _init_session_tables():
    con = sqlite3.connect(DB_PATH)
    con.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id        INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id           TEXT NOT NULL,
            date              TEXT NOT NULL,
            start_time        TEXT NOT NULL,
            end_time          TEXT,
            total_minutes     REAL,
            avg_fatigue       REAL,
            worst_period_min  REAL,
            best_period_min   REAL,
            alert_1_count     INTEGER DEFAULT 0,
            alert_2_count     INTEGER DEFAULT 0,
            critical_count    INTEGER DEFAULT 0,
            perclos_avg       REAL,
            blink_rate_avg    REAL,
            timeline_json     TEXT
        )
    """)
    con.commit()
    con.close()


class SessionRecorder:
    def __init__(self, user_id: str):
        _init_session_tables()
        self.user_id       = user_id
        self.start_time    = time.time()
        self.start_dt      = datetime.now()
        self._timeline     = []          # list of snapshot dicts
        self._last_snap    = 0.0
        self._alert_counts = [0, 0, 0, 0]  # level 0-3
        self._prev_alert   = 0

    # ── Called every frame from detection.py ─────────────────────
    def update(self, alert_level: int, ear: float, pitch: float,
               blink_rate: float, perclos: float, fatigue_score: int):
        now     = time.time()
        elapsed = now - self.start_time

        # Count alert level transitions (rising only)
        if alert_level > self._prev_alert:
            self._alert_counts[alert_level] += 1
        self._prev_alert = alert_level

        # Snapshot every N seconds
        if now - self._last_snap >= SNAPSHOT_INTERVAL:
            self._timeline.append({
                "t":      round(elapsed / 60, 3),   # minutes
                "ear":    round(ear, 3),
                "pitch":  round(pitch, 1),
                "blink":  round(blink_rate, 1),
                "perclos":round(perclos * 100, 1),  # store as %
                "alert":  alert_level,
                "score":  fatigue_score,
            })
            self._last_snap = now

    # ── Called when session ends (q pressed) ─────────────────────
    def save(self) -> int:
        """Save session to DB and return session_id."""
        if not self._timeline:
            print("[Session] No data to save.")
            return -1

        end_dt        = datetime.now()
        total_minutes = (time.time() - self.start_time) / 60.0

        scores = [s["score"] for s in self._timeline]
        avg_fatigue = round(sum(scores) / len(scores), 1)

        # Worst period: highest 3-snapshot rolling average (15s window)
        worst_min, best_min = self._find_periods()

        perclos_avg   = round(sum(s["perclos"] for s in self._timeline) / len(self._timeline), 1)
        blink_avg     = round(sum(s["blink"]   for s in self._timeline) / len(self._timeline), 1)

        con = sqlite3.connect(DB_PATH)
        cur = con.execute("""
            INSERT INTO sessions
                (user_id, date, start_time, end_time, total_minutes,
                 avg_fatigue, worst_period_min, best_period_min,
                 alert_1_count, alert_2_count, critical_count,
                 perclos_avg, blink_rate_avg, timeline_json)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            self.user_id,
            self.start_dt.strftime("%Y-%m-%d"),
            self.start_dt.strftime("%H:%M:%S"),
            end_dt.strftime("%H:%M:%S"),
            round(total_minutes, 2),
            avg_fatigue,
            worst_min,
            best_min,
            self._alert_counts[1],
            self._alert_counts[2],
            self._alert_counts[3],
            perclos_avg,
            blink_avg,
            json.dumps(self._timeline),
        ))
        session_id = cur.lastrowid
        con.commit()
        con.close()

        print(f"[Session] Saved — ID:{session_id}  "
              f"{total_minutes:.1f}min  avg fatigue:{avg_fatigue}  "
              f"alerts:{self._alert_counts[1:]}")
        return session_id

    def _find_periods(self):
        """Return (worst_minute, best_minute) based on rolling avg score."""
        if len(self._timeline) < 3:
            mid = self._timeline[len(self._timeline)//2]["t"]
            return mid, mid

        window   = 3
        averages = []
        for i in range(len(self._timeline) - window + 1):
            avg = sum(s["score"] for s in self._timeline[i:i+window]) / window
            t   = self._timeline[i + window//2]["t"]
            averages.append((avg, t))

        worst = max(averages, key=lambda x: x[0])
        best  = min(averages, key=lambda x: x[0])
        return round(worst[1], 2), round(best[1], 2)


def load_sessions(user_id: str) -> list:
    """Load all sessions for a user (without timeline JSON)."""
    con = sqlite3.connect(DB_PATH)
    rows = con.execute("""
        SELECT session_id, date, start_time, total_minutes,
               avg_fatigue, worst_period_min, best_period_min,
               alert_1_count, alert_2_count, critical_count,
               perclos_avg, blink_rate_avg
        FROM sessions WHERE user_id=?
        ORDER BY session_id DESC
    """, (user_id,)).fetchall()
    con.close()
    keys = ["session_id","date","start_time","total_minutes",
            "avg_fatigue","worst_period_min","best_period_min",
            "alert_1_count","alert_2_count","critical_count",
            "perclos_avg","blink_rate_avg"]
    return [dict(zip(keys, r)) for r in rows]


def load_timeline(session_id: int) -> list:
    """Load timeline snapshots for a specific session."""
    con = sqlite3.connect(DB_PATH)
    row = con.execute(
        "SELECT timeline_json FROM sessions WHERE session_id=?",
        (session_id,)
    ).fetchone()
    con.close()
    return json.loads(row[0]) if row and row[0] else []