"""
auth.py — SQLite-based authentication
Screens: Sign In / Create Account / Guest
Calibration data stored per user account.
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
    # Migrate existing DB if calibration columns missing
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
    """Save calibration data for a user."""
    con = sqlite3.connect(DB_PATH)
    con.execute(
        "UPDATE users SET ear_threshold=?, pitch_baseline=? WHERE user_id=?",
        (ear_threshold, pitch_baseline, user_id)
    )
    con.commit()
    con.close()
    print(f"[Auth] Calibration saved for '{user_id}'.")

def _sign_in(user_id, pw):
    """Returns user row dict or None."""
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

# ── UI helpers ────────────────────────────────────────────────────
W, H   = 640, 520
BG     = (15, 15, 20)
CARD   = (25, 27, 35)
ACCENT = (0, 210, 140)
WHITE  = (230, 230, 230)
MUTED  = (100, 105, 120)
BORDER = (50, 55, 70)

def _draw_bg(canvas):
    canvas[:] = BG
    cv2.rectangle(canvas, (60, 30), (580, H - 30), CARD, -1)
    cv2.rectangle(canvas, (60, 30), (580, H - 30), BORDER, 1)

def _draw_title(canvas, title, subtitle=""):
    cv2.putText(canvas, title, (80, 80),
                cv2.FONT_HERSHEY_SIMPLEX, 0.9, ACCENT, 2)
    if subtitle:
        cv2.putText(canvas, subtitle, (80, 105),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, MUTED, 1)

def _draw_field(canvas, label, value, y, active, masked=False):
    cv2.putText(canvas, label, (80, y - 6),
                cv2.FONT_HERSHEY_SIMPLEX, 0.42, MUTED, 1)
    border_col = ACCENT if active else BORDER
    cv2.rectangle(canvas, (80, y), (560, y + 34), border_col, 1)
    display = ("*" * len(value)) if masked else value
    display += "|" if active else ""
    cv2.putText(canvas, display, (88, y + 23),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, WHITE, 1)

def _draw_btn(canvas, text, y, x1=80, x2=560, color=ACCENT, text_col=(15,15,20)):
    cv2.rectangle(canvas, (x1, y), (x2, y + 38), color, -1)
    tw = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0][0]
    mid = (x1 + x2) // 2
    cv2.putText(canvas, text, (mid - tw // 2, y + 25),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, text_col, 2)

def _draw_btn_outline(canvas, text, y, x1, x2):
    cv2.rectangle(canvas, (x1, y), (x2, y + 38), BORDER, 1)
    tw = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)[0][0]
    mid = (x1 + x2) // 2
    cv2.putText(canvas, text, (mid - tw // 2, y + 26),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, WHITE, 1)

# ── Sign In screen ────────────────────────────────────────────────
def _screen_signin():
    fields = ["", ""]
    focus  = 0
    error  = ""
    labels = ["User ID", "Password"]
    masked = [False, True]
    ys     = [155, 225]

    while True:
        canvas = np.zeros((H, W, 3), dtype=np.uint8)
        _draw_bg(canvas)
        _draw_title(canvas, "SMART CAR", "Sign in to continue")

        for i, (label, y) in enumerate(zip(labels, ys)):
            _draw_field(canvas, label, fields[i], y, focus == i, masked=masked[i])

        if error:
            ew = cv2.getTextSize(error, cv2.FONT_HERSHEY_SIMPLEX, 0.4, 1)[0][0]
            cv2.putText(canvas, error, (320 - ew//2, 295),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (80, 80, 220), 1)

        _draw_btn(canvas, "SIGN IN", 310)
        _draw_btn_outline(canvas, "CREATE ACCOUNT  [C]", 362, 80, 305)
        _draw_btn_outline(canvas, "GUEST  [G]", 362, 315, 560)

        cv2.putText(canvas, "TAB: next field",
                    (80, H - 40), cv2.FONT_HERSHEY_SIMPLEX, 0.38, MUTED, 1)

        cv2.imshow("Smart Car", canvas)
        key = cv2.waitKey(20) & 0xFF

        if key == 27:
            return None, None
        elif key == 9:
            focus = (focus + 1) % 2
        elif key == 13:
            uid, pw = fields[0].strip(), fields[1]
            user = _sign_in(uid, pw)
            if user:
                cv2.destroyWindow("Smart Car")
                return "signin", user
            else:
                error = "Incorrect user ID or password."
        elif key == 8:
            fields[focus] = fields[focus][:-1]
        elif key in (ord('c'), ord('C')):
            cv2.destroyWindow("Smart Car")
            return "create", None
        elif key in (ord('g'), ord('G')):
            cv2.destroyWindow("Smart Car")
            return "guest", {
                "user_id": "guest", "first_name": "Guest", "last_name": "",
                "personal_email": "", "emergency_email": "",
                "ear_threshold": None, "pitch_baseline": None,
            }
        elif 32 <= key <= 126:
            fields[focus] += chr(key)

# ── Create Account screen ─────────────────────────────────────────
def _screen_create():
    labels = ["First Name", "Last Name", "User ID",
              "Password", "Confirm Password",
              "Personal Gmail", "Emergency Email"]
    masked = [False, False, False, True, True, False, False]
    fields = [""] * 7
    focus  = 0
    error  = ""
    ys     = [105, 155, 205, 255, 305, 355, 405]
    H2     = 570

    while True:
        canvas = np.zeros((H2, W, 3), dtype=np.uint8)
        canvas[:] = BG
        cv2.rectangle(canvas, (60, 10), (580, H2 - 10), CARD, -1)
        cv2.rectangle(canvas, (60, 10), (580, H2 - 10), BORDER, 1)
        cv2.putText(canvas, "CREATE ACCOUNT", (80, 65),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, ACCENT, 2)
        cv2.putText(canvas, "Calibration will run after account creation.",
                    (80, 85), cv2.FONT_HERSHEY_SIMPLEX, 0.38, MUTED, 1)

        for i, (label, y) in enumerate(zip(labels, ys)):
            _draw_field(canvas, label, fields[i], y, focus == i, masked=masked[i])

        if error:
            ew = cv2.getTextSize(error, cv2.FONT_HERSHEY_SIMPLEX, 0.38, 1)[0][0]
            cv2.putText(canvas, error, (320 - ew//2, H2 - 58),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.38, (80, 80, 220), 1)

        _draw_btn(canvas, "CREATE & CALIBRATE", H2 - 48)

        cv2.imshow("Smart Car", canvas)
        key = cv2.waitKey(20) & 0xFF

        if key == 27:
            cv2.destroyWindow("Smart Car")
            return None
        elif key == 9:
            focus = (focus + 1) % len(fields)
        elif key == 13:
            if focus < len(fields) - 1:
                focus += 1
            else:
                first, last, uid, pw, pw2, gmail, em = [f.strip() for f in fields]
                if not all([first, last, uid, pw, pw2, gmail]):
                    error = "All fields except emergency email are required."
                elif pw != pw2:
                    error = "Passwords do not match."
                else:
                    err = _create_user(uid, first, last, pw, gmail, em)
                    if err:
                        error = err
                    else:
                        cv2.destroyWindow("Smart Car")
                        # Return user dict — calibration will happen in detection.py
                        user = _sign_in(uid, pw)
                        user["needs_calibration"] = True
                        return user
        elif key == 8:
            fields[focus] = fields[focus][:-1]
        elif 32 <= key <= 126:
            fields[focus] += chr(key)

# ── Public entry point ────────────────────────────────────────────
def run_auth():
    """
    Shows Sign In screen.
    Returns user dict on success, guest dict, or None if closed.
    user dict includes 'needs_calibration': True if new account.
    """
    _init_db()
    cv2.namedWindow("Smart Car")

    while True:
        action, user = _screen_signin()

        if action == "signin":
            print(f"[Auth] Signed in: {user['user_id']} ({user['first_name']} {user['last_name']})")
            return user
        elif action == "guest":
            print("[Auth] Continuing as guest.")
            return user
        elif action == "create":
            new_user = _screen_create()
            if new_user:
                print(f"[Auth] Account created: {new_user['user_id']}")
                return new_user
            # else: back to sign in
        else:
            return None