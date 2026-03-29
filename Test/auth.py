"""
auth.py — SQLite-based authentication
Screens: Sign In / Create Account / Guest
Stores calibration + driver profile data per user.
"""
import sqlite3
import hashlib
import re
import os
import cv2
import numpy as np

DB_PATH = os.path.join(os.path.dirname(__file__), "users.db")

# ── Database setup ────────────────────────────────────────────────
def _init_db():
    con = sqlite3.connect(DB_PATH)
    con.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id              TEXT PRIMARY KEY,
            first_name           TEXT NOT NULL,
            last_name            TEXT NOT NULL,
            pw_hash              TEXT NOT NULL,
            personal_email       TEXT NOT NULL,
            emergency_email      TEXT NOT NULL,
            ear_threshold        REAL,
            pitch_baseline       REAL,
            -- Driver profile
            drive_frequency      TEXT,   -- e.g. "daily", "2-3x/week", "weekends", "rarely"
            vision_left          TEXT,   -- e.g. "20/20", "20/40", "unknown"
            vision_right         TEXT,
            wears_glasses        TEXT,   -- "yes" / "no" / "contacts"
            drive_time_of_day    TEXT,   -- "morning" / "afternoon" / "evening" / "night" / "mixed"
            avg_drive_duration   TEXT,   -- "under30" / "30to120" / "over120"
            drive_environment    TEXT,   -- "urban" / "highway" / "mixed"
            avg_sleep_hours      TEXT,   -- "under5" / "5to6" / "7to8" / "over8"
            caffeine_intake      TEXT    -- "none" / "light" / "moderate" / "heavy"
        )
    """)

    # Migrate existing DB — add any missing columns
    existing_cols = {r[1] for r in con.execute("PRAGMA table_info(users)").fetchall()}
    new_cols = {
        "ear_threshold":      "REAL",
        "pitch_baseline":     "REAL",
        "drive_frequency":    "TEXT",
        "vision_left":        "TEXT",
        "vision_right":       "TEXT",
        "wears_glasses":      "TEXT",
        "drive_time_of_day":  "TEXT",
        "avg_drive_duration": "TEXT",
        "drive_environment":  "TEXT",
        "avg_sleep_hours":    "TEXT",
        "caffeine_intake":    "TEXT",
    }
    for col, dtype in new_cols.items():
        if col not in existing_cols:
            con.execute(f"ALTER TABLE users ADD COLUMN {col} {dtype}")
            print(f"[DB] Migrated: added column '{col}'")

    con.commit()
    con.close()


def _hash(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()


def _create_user(user_id, first, last, pw, personal_email, emergency_email) -> str:
    """Returns '' on success, error message on failure."""
    if not re.match(r'^[a-zA-Z0-9_]{3,20}$', user_id):
        return "User ID: 3-20 chars, letters/numbers/underscore only."
    if len(pw) < 6:
        return "Password must be at least 6 characters."
    try:
        con = sqlite3.connect(DB_PATH)
        con.execute(
            """INSERT INTO users
               (user_id, first_name, last_name, pw_hash,
                personal_email, emergency_email)
               VALUES (?,?,?,?,?,?)""",
            (user_id, first, last, _hash(pw), personal_email, emergency_email)
        )
        con.commit()
        con.close()
        return ""
    except sqlite3.IntegrityError:
        return "User ID already taken."


def save_calibration(user_id: str, ear_threshold: float, pitch_baseline: float):
    """Save calibration data for a user."""
    con = sqlite3.connect(DB_PATH)
    con.execute(
        "UPDATE users SET ear_threshold=?, pitch_baseline=? WHERE user_id=?",
        (ear_threshold, pitch_baseline, user_id)
    )
    con.commit()
    con.close()
    print(f"[Auth] Calibration saved for '{user_id}'.")


def save_driver_profile(user_id: str, profile: dict):
    """
    Save driver profile answers.
    profile keys:
        drive_frequency, vision_left, vision_right, wears_glasses,
        drive_time_of_day, avg_drive_duration, drive_environment,
        avg_sleep_hours, caffeine_intake
    """
    allowed = {
        "drive_frequency", "vision_left", "vision_right", "wears_glasses",
        "drive_time_of_day", "avg_drive_duration", "drive_environment",
        "avg_sleep_hours", "caffeine_intake",
    }
    filtered = {k: v for k, v in profile.items() if k in allowed}
    if not filtered:
        return
    sets   = ", ".join(f"{k}=?" for k in filtered)
    values = list(filtered.values()) + [user_id]
    con = sqlite3.connect(DB_PATH)
    con.execute(f"UPDATE users SET {sets} WHERE user_id=?", values)
    con.commit()
    con.close()
    print(f"[Auth] Driver profile saved for '{user_id}'.")


def _sign_in(user_id, pw):
    con = sqlite3.connect(DB_PATH)
    row = con.execute(
        "SELECT * FROM users WHERE user_id=? AND pw_hash=?",
        (user_id, _hash(pw))
    ).fetchone()
    cols = [r[1] for r in con.execute("PRAGMA table_info(users)").fetchall()]
    con.close()
    if not row:
        return None
    return dict(zip(cols, row))


def get_driver_profile(user_id: str) -> dict:
    """Load driver profile fields for a user."""
    con = sqlite3.connect(DB_PATH)
    row = con.execute(
        """SELECT drive_frequency, vision_left, vision_right, wears_glasses,
                  drive_time_of_day, avg_drive_duration, drive_environment,
                  avg_sleep_hours, caffeine_intake
           FROM users WHERE user_id=?""",
        (user_id,)
    ).fetchone()
    con.close()
    if not row:
        return {}
    keys = ["drive_frequency", "vision_left", "vision_right", "wears_glasses",
            "drive_time_of_day", "avg_drive_duration", "drive_environment",
            "avg_sleep_hours", "caffeine_intake"]
    return dict(zip(keys, row))


# ── Profile question definitions (used by UI) ─────────────────────
PROFILE_QUESTIONS = [
    {
        "key":     "drive_frequency",
        "label":   "How often do you drive per week?",
        "type":    "choice",
        "single":  True,
        "options": ["Daily", "2–3x / week", "Weekends only", "Rarely"],
        "values":  ["daily", "2-3x/week", "weekends", "rarely"],
    },
    {
        "key":     "vision_left",
        "label":   "Left eye vision (e.g. 20/20, 20/40)",
        "type":    "text",
        "placeholder": "e.g. 20/20",
    },
    {
        "key":     "vision_right",
        "label":   "Right eye vision (e.g. 20/20, 20/40)",
        "type":    "text",
        "placeholder": "e.g. 20/20",
    },
    {
        "key":     "wears_glasses",
        "label":   "Do you wear glasses or contacts?",
        "type":    "choice",
        "single":  True,
        "options": ["No", "Glasses", "Contact lenses"],
        "values":  ["no", "glasses", "contacts"],
    },
    {
        "key":     "drive_time_of_day",
        "label":   "When do you usually drive?",
        "type":    "choice",
        "options": ["Morning", "Afternoon", "Evening", "Night", "Mixed"],
        "values":  ["morning", "afternoon", "evening", "night", "mixed"],
    },
    {
        "key":     "avg_drive_duration",
        "label":   "Typical single drive duration?",
        "type":    "choice",
        "single":  True,
        "options": ["Under 30 min", "30 min – 2 hrs", "Over 2 hrs"],
        "values":  ["under30", "30to120", "over120"],
    },
    {
        "key":     "drive_environment",
        "label":   "Typical driving environment?",
        "type":    "choice",
        "options": ["Urban / city", "Highway", "Mixed"],
        "values":  ["urban", "highway", "mixed"],
    },
    {
        "key":     "avg_sleep_hours",
        "label":   "Average sleep per night?",
        "type":    "choice",
        "single":  True,
        "options": ["Under 5 hrs", "5–6 hrs", "7–8 hrs", "Over 8 hrs"],
        "values":  ["under5", "5to6", "7to8", "over8"],
    },
    {
        "key":     "caffeine_intake",
        "label":   "Daily caffeine intake?",
        "type":    "choice",
        "single":  True,
        "options": ["None", "Light (1 cup)", "Moderate (2–3 cups)", "Heavy (4+ cups)"],
        "values":  ["none", "light", "moderate", "heavy"],
    },
]