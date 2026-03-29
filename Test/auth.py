# =============================================================================
# auth.py — Noctura authentication backend
# =============================================================================
# Database layer only. All UI is handled in ui.py.
# =============================================================================

import sqlite3
import hashlib
import re
import os
import sys

DB_PATH = os.path.join(os.path.dirname(__file__), "users.db")


def _init_db():
    con = sqlite3.connect(DB_PATH)
    con.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id          TEXT PRIMARY KEY,
            first_name       TEXT NOT NULL,
            last_name        TEXT NOT NULL,
            pw_hash          TEXT NOT NULL,
            personal_email   TEXT NOT NULL,
            emergency_email  TEXT NOT NULL,
            ear_threshold    REAL,
            pitch_baseline   REAL
        )
    """)
    cols = [r[1] for r in con.execute("PRAGMA table_info(users)").fetchall()]
    if "ear_threshold" not in cols:
        con.execute("ALTER TABLE users ADD COLUMN ear_threshold REAL")
    if "pitch_baseline" not in cols:
        con.execute("ALTER TABLE users ADD COLUMN pitch_baseline REAL")
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
            "INSERT INTO users VALUES (?,?,?,?,?,?,NULL,NULL)",
            (user_id, first, last, _hash(pw), personal_email, emergency_email)
        )
        con.commit()
        con.close()
        return ""
    except sqlite3.IntegrityError:
        return "User ID already taken."


def save_calibration(user_id: str, ear_threshold: float, pitch_baseline: float):
    con = sqlite3.connect(DB_PATH)
    con.execute(
        "UPDATE users SET ear_threshold=?, pitch_baseline=? WHERE user_id=?",
        (ear_threshold, pitch_baseline, user_id)
    )
    con.commit()
    con.close()
    print(f"[Auth] Calibration saved for '{user_id}'.", file=sys.stderr)


def _sign_in(user_id, pw):
    """Returns user dict or None."""
    con = sqlite3.connect(DB_PATH)
    row = con.execute(
        "SELECT * FROM users WHERE user_id=? AND pw_hash=?",
        (user_id, _hash(pw))
    ).fetchone()
    con.close()
    if row:
        return {
            "user_id":         row[0],
            "first_name":      row[1],
            "last_name":       row[2],
            "personal_email":  row[4],
            "emergency_email": row[5],
            "ear_threshold":   row[6],
            "pitch_baseline":  row[7],
        }
    return None