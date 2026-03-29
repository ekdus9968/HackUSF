# =============================================================================
# auth.py — Noctura authentication
# Backend: SQLite, unchanged.
# UI: customtkinter, cockpit aesthetic, matches ui.py
# =============================================================================

import sqlite3
import hashlib
import re
import os
import sys
import customtkinter as ctk

DB_PATH = os.path.join(os.path.dirname(__file__), "users.db")

# =============================================================================
# Database layer — completely unchanged
# =============================================================================

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

# =============================================================================
# Theme — matches ui.py exactly
# =============================================================================

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

BG     = "#080C12"
PANEL  = "#0D1219"
BORDER = "#1A2332"
AMBER  = "#F5A623"
GREEN  = "#00E87A"
RED    = "#FF3A3A"
TEXT   = "#C8D8E8"
TEXT2  = "#607080"
CARD   = "#0F1520"

# =============================================================================
# Reusable widget helpers
# =============================================================================

def _make_entry(parent, placeholder, show="", width=380):
    return ctk.CTkEntry(
        parent,
        placeholder_text=placeholder,
        font=ctk.CTkFont(family="Courier", size=13),
        fg_color=PANEL,
        border_color=BORDER,
        border_width=1,
        text_color=TEXT,
        placeholder_text_color=TEXT2,
        width=width, height=42,
        corner_radius=6,
        show=show
    )

def _make_btn(parent, text, command, fg=AMBER, tc="#000000", width=380, outline=False):
    return ctk.CTkButton(
        parent,
        text=text,
        command=command,
        font=ctk.CTkFont(family="Courier", size=12, weight="bold"),
        fg_color="transparent" if outline else fg,
        hover_color=PANEL if outline else "#E8920D",
        text_color=TEXT2 if outline else tc,
        border_width=1 if outline else 0,
        border_color=BORDER if outline else fg,
        width=width, height=42,
        corner_radius=6
    )

def _make_label(parent, text, size=10, color=TEXT2, bold=False):
    return ctk.CTkLabel(
        parent,
        text=text,
        font=ctk.CTkFont(family="Courier", size=size,
                         weight="bold" if bold else "normal"),
        text_color=color
    )

def _divider(parent, width=380):
    ctk.CTkFrame(parent, fg_color=BORDER, height=1,
                 width=width, corner_radius=0).pack(pady=10)

# =============================================================================
# Auth window
# =============================================================================

class AuthWindow(ctk.CTk):
    """
    Fullscreen auth window. Swaps content frames between screens.
    Stores result in self.result, then destroys itself.
    """

    def __init__(self):
        super().__init__()
        self.title("Noctura")
        self.configure(fg_color=BG)
        self.resizable(True, True)
        self.after(100, lambda: self.state("zoomed"))
        self.result = None
        self._show_welcome()

    # ── Screen manager ────────────────────────────────────────────────────────

    def _clear(self):
        for w in self.winfo_children():
            w.destroy()

    def _card(self, width=500, height=None):
        """Returns (outer, card, inner) — centered card layout."""
        outer = ctk.CTkFrame(self, fg_color=BG)
        outer.pack(fill="both", expand=True)

        card = ctk.CTkFrame(
            outer, fg_color=CARD,
            corner_radius=16,
            border_width=1, border_color=BORDER
        )
        if height:
            card.configure(height=height, width=width)
            card.pack_propagate(False)
        card.place(relx=0.5, rely=0.5, anchor="center")

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(padx=48, pady=40, fill="both", expand=True)

        return outer, card, inner

    # ── Screen 1: Welcome ─────────────────────────────────────────────────────

    def _show_welcome(self):
        self._clear()
        _, _, inner = self._card(width=460, height=420)

        # Logo
        ctk.CTkLabel(
            inner, text="◉",
            font=ctk.CTkFont(family="Courier", size=72),
            text_color=AMBER
        ).pack(pady=(8, 0))

        # App name
        ctk.CTkLabel(
            inner, text="NOCTURA",
            font=ctk.CTkFont(family="Courier", size=30, weight="bold"),
            text_color=TEXT
        ).pack()

        # Tagline
        _make_label(inner, "driver awareness system", size=11).pack(pady=(4, 32))

        # CTA
        _make_btn(inner, "GET STARTED →", self._show_signin).pack()

        # Version
        _make_label(inner, "hackusf 2025 · v1.0", size=9,
                    color=BORDER).pack(pady=(20, 0))

    # ── Screen 2: Sign In ─────────────────────────────────────────────────────

    def _show_signin(self):
        self._clear()
        _, _, inner = self._card(width=500, height=560)

        # Header
        ctk.CTkLabel(
            inner, text="SIGN IN",
            font=ctk.CTkFont(family="Courier", size=22, weight="bold"),
            text_color=AMBER
        ).pack(pady=(0, 4))
        _make_label(inner, "welcome back").pack(pady=(0, 24))

        # Fields
        uid_e = _make_entry(inner, "User ID")
        uid_e.pack(pady=(0, 10))
        pw_e = _make_entry(inner, "Password", show="●")
        pw_e.pack(pady=(0, 4))

        # Error label
        err_lbl = _make_label(inner, "", color=RED)
        err_lbl.pack(pady=(0, 12))

        # Sign in button
        def do_signin():
            uid  = uid_e.get().strip()
            pw   = pw_e.get()
            if not uid or not pw:
                err_lbl.configure(text="Please enter your user ID and password.")
                return
            user = _sign_in(uid, pw)
            if user:
                self.result = user
                print(f"[Auth] Signed in: {user['user_id']}", file=sys.stderr)
                self.quit()
            else:
                err_lbl.configure(text="Incorrect user ID or password.")
                pw_e.delete(0, "end")

        _make_btn(inner, "SIGN IN", do_signin).pack(pady=(0, 10))

        _divider(inner)

        # Bottom row — create + guest
        row = ctk.CTkFrame(inner, fg_color="transparent")
        row.pack()

        _make_btn(row, "Create Account", self._show_create,
                  outline=True, width=184).pack(side="left", padx=(0, 8))
        _make_btn(row, "Continue as Guest", self._do_guest,
                  outline=True, width=184).pack(side="left")

        # Back
        ctk.CTkButton(
            inner, text="← back",
            command=self._show_welcome,
            font=ctk.CTkFont(family="Courier", size=10),
            fg_color="transparent", hover_color=PANEL,
            text_color=TEXT2
        ).pack(pady=(16, 0))

        # Bind Enter key to sign in
        self.bind("<Return>", lambda e: do_signin())
        uid_e.focus()

    # ── Screen 3: Create Account ──────────────────────────────────────────────

    def _show_create(self):
        self._clear()
        self.unbind("<Return>")

        _, _, inner = self._card(width=540, height=700)

        ctk.CTkLabel(
            inner, text="CREATE ACCOUNT",
            font=ctk.CTkFont(family="Courier", size=20, weight="bold"),
            text_color=AMBER
        ).pack(pady=(0, 4))
        _make_label(inner, "calibration runs after — saves your eye baseline").pack(pady=(0, 20))

        # Name row
        name_row = ctk.CTkFrame(inner, fg_color="transparent")
        name_row.pack(pady=(0, 10))
        first_e = _make_entry(name_row, "First name", width=185)
        first_e.pack(side="left", padx=(0, 8))
        last_e  = _make_entry(name_row, "Last name",  width=185)
        last_e.pack(side="left")

        uid_e   = _make_entry(inner, "User ID  (letters, numbers, _ only)")
        uid_e.pack(pady=(0, 10))
        pw_e    = _make_entry(inner, "Password  (min 6 characters)", show="●")
        pw_e.pack(pady=(0, 10))
        pw2_e   = _make_entry(inner, "Confirm password", show="●")
        pw2_e.pack(pady=(0, 10))
        gmail_e = _make_entry(inner, "Personal Gmail")
        gmail_e.pack(pady=(0, 10))
        em_e    = _make_entry(inner, "Emergency email  (optional)")
        em_e.pack(pady=(0, 4))

        err_lbl = _make_label(inner, "", color=RED)
        err_lbl.pack(pady=(0, 12))

        def do_create():
            first = first_e.get().strip()
            last  = last_e.get().strip()
            uid   = uid_e.get().strip()
            pw    = pw_e.get()
            pw2   = pw2_e.get()
            gmail = gmail_e.get().strip()
            em    = em_e.get().strip()

            if not all([first, last, uid, pw, pw2, gmail]):
                err_lbl.configure(text="All fields except emergency email are required.")
                return
            if pw != pw2:
                err_lbl.configure(text="Passwords do not match.")
                return

            error = _create_user(uid, first, last, pw, gmail, em)
            if error:
                err_lbl.configure(text=error)
                return

            user = _sign_in(uid, pw)
            user["needs_calibration"] = True
            self.result = user
            print(f"[Auth] Account created: {user['user_id']}", file=sys.stderr)
            self.quit()

        _make_btn(inner, "CREATE ACCOUNT & CALIBRATE", do_create).pack(pady=(0, 8))

        ctk.CTkButton(
            inner, text="← back to sign in",
            command=self._show_signin,
            font=ctk.CTkFont(family="Courier", size=10),
            fg_color="transparent", hover_color=PANEL,
            text_color=TEXT2
        ).pack()

        first_e.focus()

    # ── Guest ─────────────────────────────────────────────────────────────────

    def _do_guest(self):
        self.result = {
            "user_id":         "guest",
            "first_name":      "Guest",
            "last_name":       "",
            "personal_email":  "",
            "emergency_email": "",
            "ear_threshold":   None,
            "pitch_baseline":  None,
        }
        print("[Auth] Continuing as guest.", file=sys.stderr)
        self.after(10, self.quit)


# =============================================================================
# Public entry point
# =============================================================================

def run_auth():
    """
    Shows auth flow. Returns user dict or None if window closed.
    Called by auth_runner.py as a subprocess from main.py.
    """
    _init_db()
    win = AuthWindow()
    win.mainloop()
    return win.result