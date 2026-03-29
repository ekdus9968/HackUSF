# =============================================================================
# ui.py — Noctura unified application window
# =============================================================================

import os
import io
import cv2
import time
import threading
import mediapipe as mp
import numpy as np
import customtkinter as ctk
from PIL import Image, ImageTk, ImageDraw

from config import state
from auth import _init_db, _sign_in, _create_user, save_calibration, save_driver_profile, PROFILE_QUESTIONS
from constants import LEFT_EYE, RIGHT_EYE, calculate_EAR, calculate_pitch
from detection import run as run_detection

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

BG      = "#0A0E1A"
PANEL   = "#0D1224"
BORDER  = "#1A2440"
BORDER2 = "#243660"
AMBER   = "#E8A020"
AMBER2  = "#D4901A"
GREEN   = "#00E87A"
RED     = "#FF3A3A"
CYAN    = "#4A7FD4"
TEXT    = "#D8E4F8"
TEXT2   = "#5A7090"
TEXT3   = "#384860"
CARD    = "#0F1428"

CAL_STEPS = [
    {"title": "OPEN EYES",     "instruction": "Look straight at the camera with your eyes fully open.", "sub": "Hold still — we're measuring your natural eye openness.", "color": GREEN, "icon": "👁",  "samples": 60},
    {"title": "CLOSE EYES",    "instruction": "Now slowly close your eyes completely.",                  "sub": "Keep your head still — this sets your closed-eye baseline.", "color": AMBER, "icon": "😑", "samples": 60},
    {"title": "LOOK STRAIGHT", "instruction": "Open your eyes and look straight ahead naturally.",       "sub": "This calibrates your head pose — no need to tilt.",         "color": CYAN,  "icon": "⬆",  "samples": 60},
]


class AppWindow(ctk.CTk):

    def __init__(self):
        super().__init__()
        self.title("Noctura")
        self.configure(fg_color=BG)
        self.resizable(True, True)
        self.after(100, lambda: self.state("zoomed"))
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        _init_db()

        self._user              = None
        self._cal_step          = 0
        self._cal_collecting    = False
        self._cal_samples       = []
        self._cal_open_avg      = 0.0
        self._cal_done          = False
        self._ear_threshold     = 0.25
        self._pitch_baseline    = 0.0
        self._cap               = None
        self._face_mesh         = None
        self._cam_active        = False
        self._photo             = None
        self._detection_started = False
        self._welcome_playing   = False
        self._welcome_cap       = None
        self._alert_log         = []
        self._session_start     = None
        self._dashboard_active  = False
        self._badge_btn         = None

        self._show_welcome()

    # =========================================================================
    # Shared helpers
    # =========================================================================

    def _title_bar(self, subtitle="", step=""):
        bar = ctk.CTkFrame(self, fg_color=PANEL, height=40,
                           corner_radius=0, border_width=1, border_color=BORDER)
        bar.pack(fill="x", side="top")
        bar.pack_propagate(False)
        ctk.CTkLabel(bar, text="NOCTURA",
                     font=ctk.CTkFont(family="Inter", size=13, weight="bold"),
                     text_color=AMBER).pack(side="left", padx=16)
        if subtitle:
            ctk.CTkLabel(bar, text=subtitle,
                         font=ctk.CTkFont(family="Inter", size=11),
                         text_color=TEXT2).pack(side="left", padx=8)
        if step:
            ctk.CTkLabel(bar, text=step,
                         font=ctk.CTkFont(family="Inter", size=10),
                         text_color=TEXT2).pack(side="right", padx=16)
        return bar

    def _clear(self):
        for w in self.winfo_children():
            w.destroy()

    def _card(self, width=500, height=480):
        outer = ctk.CTkFrame(self, fg_color=BG)
        outer.pack(fill="both", expand=True)
        card = ctk.CTkFrame(outer, fg_color=CARD, corner_radius=16,
                            border_width=1, border_color=BORDER,
                            width=width, height=height)
        card.place(relx=0.5, rely=0.5, anchor="center")
        card.pack_propagate(False)
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.place(relx=0.5, rely=0.5, anchor="center")
        return outer, card, inner

    def _entry(self, parent, placeholder, show="", width=380):
        return ctk.CTkEntry(parent, placeholder_text=placeholder,
                            font=ctk.CTkFont(family="Inter", size=13),
                            fg_color=PANEL, border_color=BORDER, border_width=1,
                            text_color=TEXT, placeholder_text_color=TEXT2,
                            width=width, height=42, corner_radius=6, show=show)

    def _btn(self, parent, text, cmd, fg=AMBER, tc="#000", outline=False, width=380, pady=6):
        b = ctk.CTkButton(parent, text=text, command=cmd,
                          font=ctk.CTkFont(family="Inter", size=12, weight="bold"),
                          fg_color="transparent" if outline else fg,
                          hover_color=PANEL if outline else AMBER2,
                          text_color=TEXT2 if outline else tc,
                          border_width=1 if outline else 0,
                          border_color=BORDER if outline else fg,
                          width=width, height=42, corner_radius=6)
        b.pack(pady=pady)
        return b

    @staticmethod
    def _hex_bgr(hex_color):
        h = hex_color.lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return (b, g, r)

    # =========================================================================
    # Page 1 — Welcome
    # =========================================================================

    def _show_welcome(self):
        self._clear()
        self._stop_camera()

        outer = ctk.CTkFrame(self, fg_color="#000")
        outer.pack(fill="both", expand=True)

        self._welcome_canvas = ctk.CTkCanvas(outer, bg="#000", highlightthickness=0)
        self._welcome_canvas.pack(fill="both", expand=True)

        video_path = None
        for ext in [".mp4", ".mov", ".avi", ".m4v"]:
            p = os.path.join(os.path.dirname(__file__), f"Welcome To Noctua{ext}")
            if os.path.exists(p):
                video_path = p
                break

        if video_path:
            self._welcome_cap     = cv2.VideoCapture(video_path)
            self._welcome_playing = True
            self._play_welcome_video()
        else:
            self._welcome_canvas.create_text(
                400, 300, text="NOCTURA", fill=AMBER, font=("Inter", 48, "bold"))

        ctk.CTkButton(
            outer, text="GET STARTED →",
            command=self._stop_welcome_and_start,
            font=ctk.CTkFont(family="MuseoModerno", size=14, weight="bold"),
            fg_color=AMBER, hover_color=AMBER2,
            text_color="#000", width=260, height=52, corner_radius=8
        ).place(relx=0.5, rely=0.88, anchor="center")

    def _play_welcome_video(self):
        if not self._welcome_playing:
            return
        ret, frame = self._welcome_cap.read()
        if not ret:
            self._welcome_cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            self.after(33, self._play_welcome_video)
            return
        try:
            cw = self._welcome_canvas.winfo_width()
            ch = self._welcome_canvas.winfo_height()
            if cw > 1 and ch > 1:
                frame = cv2.resize(frame, (cw, ch))
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(frame_rgb)
            self._welcome_photo = ImageTk.PhotoImage(image=img)
            self._welcome_canvas.delete("all")
            self._welcome_canvas.create_image(0, 0, anchor="nw", image=self._welcome_photo)
        except Exception:
            pass
        self.after(33, self._play_welcome_video)

    def _stop_welcome_and_start(self):
        self._welcome_playing = False
        if self._welcome_cap:
            self._welcome_cap.release()
            self._welcome_cap = None
        self._show_signin()

    # =========================================================================
    # Page 2 — Sign In
    # =========================================================================

    def _show_signin(self):
        self._clear()
        _, _, inner = self._card(500, 560)

        ctk.CTkLabel(inner, text="SIGN IN",
                     font=ctk.CTkFont(family="MuseoModerno", size=22, weight="bold"),
                     text_color=AMBER).pack(pady=(0, 4))

        uid_e = self._entry(inner, "User ID")
        uid_e.pack(pady=(0, 10))
        pw_e  = self._entry(inner, "Password", show="●")
        pw_e.pack(pady=(0, 4))

        err = ctk.CTkLabel(inner, text="",
                           font=ctk.CTkFont(family="Inter", size=10),
                           text_color=RED)
        err.pack(pady=(0, 10))

        def do_signin():
            user = _sign_in(uid_e.get().strip(), pw_e.get())
            if user:
                self._user = user
                self._after_auth()
            else:
                err.configure(text="Incorrect user ID or password.")
                pw_e.delete(0, "end")

        self._btn(inner, "SIGN IN", do_signin)
        ctk.CTkFrame(inner, fg_color=BORDER, height=1, width=380,
                     corner_radius=0).pack(pady=10)

        row = ctk.CTkFrame(inner, fg_color="transparent")
        row.pack()
        ctk.CTkButton(row, text="Create Account", command=self._show_create,
                      font=ctk.CTkFont(family="MuseoModerno", size=11),
                      fg_color="transparent", hover_color=PANEL,
                      text_color=TEXT2, border_width=1, border_color=BORDER,
                      width=184, height=40, corner_radius=6).pack(side="left", padx=(0, 8))
        ctk.CTkButton(row, text="Guest", command=self._do_guest,
                      font=ctk.CTkFont(family="MuseoModerno", size=11),
                      fg_color="transparent", hover_color=PANEL,
                      text_color=TEXT2, border_width=1, border_color=BORDER,
                      width=184, height=40, corner_radius=6).pack(side="left")

        ctk.CTkButton(inner, text="← back", command=self._show_welcome,
                      font=ctk.CTkFont(family="MuseoModerno", size=10),
                      fg_color="transparent", hover_color=PANEL,
                      text_color=TEXT2).pack(pady=(12, 0))

        self.bind("<Return>", lambda e: do_signin())
        uid_e.focus()

    # =========================================================================
    # Page 2b — Create Account
    # =========================================================================

    def _show_create(self):
        self._clear()
        self.unbind("<Return>")

        outer = ctk.CTkFrame(self, fg_color=BG)
        outer.pack(fill="both", expand=True)
        card = ctk.CTkFrame(outer, fg_color=CARD, corner_radius=16,
                            border_width=1, border_color=BORDER, width=560, height=640)
        card.place(relx=0.5, rely=0.5, anchor="center")
        card.pack_propagate(False)
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(padx=48, pady=24, fill="both", expand=True)

        ctk.CTkLabel(inner, text="CREATE ACCOUNT",
                     font=ctk.CTkFont(family="MuseoModerno", size=20, weight="bold"),
                     text_color=AMBER).pack(pady=(0, 4))

        name_row = ctk.CTkFrame(inner, fg_color="transparent")
        name_row.pack(pady=(0, 8))
        first_e = self._entry(name_row, "First name", width=185)
        first_e.pack(side="left", padx=(0, 8))
        last_e  = self._entry(name_row, "Last name", width=185)
        last_e.pack(side="left")

        uid_e   = self._entry(inner, "User ID  (letters, numbers, _ only)")
        uid_e.pack(pady=(0, 8))
        pw_e    = self._entry(inner, "Password  (min 6 characters)", show="●")
        pw_e.pack(pady=(0, 8))
        pw2_e   = self._entry(inner, "Confirm password", show="●")
        pw2_e.pack(pady=(0, 8))
        gmail_e = self._entry(inner, "Personal Gmail")
        gmail_e.pack(pady=(0, 8))
        em_e    = self._entry(inner, "Emergency email  (optional)")
        em_e.pack(pady=(0, 4))

        err = ctk.CTkLabel(inner, text="",
                           font=ctk.CTkFont(family="Inter", size=10),
                           text_color=RED)
        err.pack(pady=(0, 6))

        def do_create():
            first = first_e.get().strip()
            last  = last_e.get().strip()
            uid   = uid_e.get().strip()
            pw    = pw_e.get()
            pw2   = pw2_e.get()
            gmail = gmail_e.get().strip()
            em    = em_e.get().strip()
            if not all([first, last, uid, pw, pw2, gmail]):
                err.configure(text="All fields except emergency email are required.")
                return
            if pw != pw2:
                err.configure(text="Passwords do not match.")
                return
            error = _create_user(uid, first, last, pw, gmail, em)
            if error:
                err.configure(text=error)
                return
            user = _sign_in(uid, pw)
            user["needs_calibration"] = True
            self._user = user
            self._after_auth()

        entries = [first_e, last_e, uid_e, pw_e, pw2_e, gmail_e, em_e]
        for i, e in enumerate(entries):
            next_e = entries[(i + 1) % len(entries)]
            e.bind("<Tab>", lambda ev, n=next_e: (n.focus(), "break"))
            e.bind("<Return>", lambda ev: do_create())

        self._btn(inner, "NEXT →", do_create)
        ctk.CTkButton(inner, text="← back to sign in", command=self._show_signin,
                      font=ctk.CTkFont(family="Inter", size=10),
                      fg_color="transparent", hover_color=BORDER,
                      text_color=TEXT2).pack()

        self.bind("<Return>", lambda e: do_create())
        first_e.focus()

    def _do_guest(self):
        self._user = {
            "user_id": "guest", "first_name": "Guest", "last_name": "",
            "personal_email": "", "emergency_email": "",
            "ear_threshold": None, "pitch_baseline": None,
        }
        self._after_auth()

    # =========================================================================
    # Page 2c — Driver Profile (new users only)
    # =========================================================================

    def _show_driver_profile(self):
        self._clear()
        self.unbind("<Return>")

        outer = ctk.CTkFrame(self, fg_color=BG)
        outer.pack(fill="both", expand=True)

        card = ctk.CTkScrollableFrame(outer, fg_color=CARD, corner_radius=16,
                                      border_width=1, border_color=BORDER,
                                      width=600, height=580,
                                      scrollbar_button_color=BORDER,
                                      scrollbar_button_hover_color=BORDER2)
        card.place(relx=0.5, rely=0.5, anchor="center")

        # Mac mousewheel scroll fix
        def _on_scroll(e):
            card._parent_canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
        card.bind_all("<MouseWheel>", _on_scroll)

        ctk.CTkLabel(card, text="DRIVER PROFILE",
                     font=ctk.CTkFont(family="Inter", size=20, weight="bold"),
                     text_color=AMBER).pack(pady=(16, 4))
        ctk.CTkLabel(card, text="Help us personalize your experience — takes 30 seconds.",
                     font=ctk.CTkFont(family="Inter", size=10),
                     text_color=TEXT2).pack(pady=(0, 16))

        answers = {}

        for q in PROFILE_QUESTIONS:
            ctk.CTkLabel(card, text=q["label"],
                         font=ctk.CTkFont(family="Inter", size=11, weight="bold"),
                         text_color=TEXT, anchor="w").pack(fill="x", padx=24, pady=(12, 4))

            if q["type"] == "choice":
                selected = []
                answers[q["key"]] = selected
                btn_row = ctk.CTkFrame(card, fg_color="transparent")
                btn_row.pack(fill="x", padx=24, pady=(0, 4))
                btn_refs = []

                def make_cmd(v, sel_list, refs):
                    def cmd():
                        if v in sel_list:
                            sel_list.remove(v)
                        else:
                            sel_list.append(v)
                        for b, bv in refs:
                            b.configure(
                                fg_color=AMBER if bv in sel_list else "transparent",
                                text_color="#000" if bv in sel_list else TEXT2
                            )
                    return cmd

                for label, value in zip(q["options"], q["values"]):
                    btn = ctk.CTkButton(btn_row, text=label,
                                        font=ctk.CTkFont(family="Inter", size=10),
                                        fg_color="transparent", hover_color=BORDER2,
                                        text_color=TEXT2, border_width=1, border_color=BORDER,
                                        height=34, corner_radius=6)
                    btn.pack(side="left", padx=(0, 6), pady=2)
                    btn_refs.append((btn, value))

                for btn, value in btn_refs:
                    btn.configure(command=make_cmd(value, selected, btn_refs))

            elif q["type"] == "text":
                entry = self._entry(card, q.get("placeholder", ""), width=552)
                entry.pack(padx=24, pady=(0, 4))
                answers[q["key"]] = entry

            ctk.CTkFrame(card, fg_color=BORDER, height=1,
                         corner_radius=0).pack(fill="x", padx=24, pady=(8, 0))

        # Buttons
        btn_frame = ctk.CTkFrame(card, fg_color="transparent")
        btn_frame.pack(pady=20)

        def save_and_continue():
            profile = {}
            for key, widget in answers.items():
                if isinstance(widget, list):
                    if widget:
                        profile[key] = ",".join(widget)
                else:
                    val = widget.get().strip()
                    if val:
                        profile[key] = val
            user = self._user
            if user and user["user_id"] != "guest":
                save_driver_profile(user["user_id"], profile)
            self.unbind("<MouseWheel>")
            self._after_driver_profile()

        ctk.CTkButton(btn_frame, text="SAVE & CONTINUE →",
                      command=save_and_continue,
                      font=ctk.CTkFont(family="Inter", size=12, weight="bold"),
                      fg_color=AMBER, hover_color=AMBER2,
                      text_color="#000", width=260, height=42, corner_radius=6).pack(side="left", padx=8)

        ctk.CTkButton(btn_frame, text="Skip",
                      command=lambda: (self.unbind("<MouseWheel>"), self._after_driver_profile()),
                      font=ctk.CTkFont(family="Inter", size=11),
                      fg_color="transparent", hover_color=PANEL,
                      text_color=TEXT2, border_width=1, border_color=BORDER,
                      width=100, height=42, corner_radius=6).pack(side="left")

    def _after_driver_profile(self):
        user = self._user
        if user["user_id"] == "guest" or not user.get("emergency_email"):
            self._show_emergency()
        else:
            state["contact_name"]  = f"{user['first_name']} {user['last_name']}"
            state["contact_email"] = user["emergency_email"]
            self._after_emergency()

    # =========================================================================
    # Page 3 — Emergency Contact
    # =========================================================================

    def _after_auth(self):
        self.unbind("<Return>")
        user = self._user
        state["user"] = user
        if user.get("needs_calibration"):
            self._show_driver_profile()
        elif user["user_id"] == "guest" or not user.get("emergency_email"):
            self._show_emergency()
        else:
            state["contact_name"]  = f"{user['first_name']} {user['last_name']}"
            state["contact_email"] = user["emergency_email"]
            self._after_emergency()

    def _show_emergency(self):
        self._clear()
        _, _, inner = self._card(520, 520)

        ctk.CTkLabel(inner, text="🚨",
                     font=ctk.CTkFont(size=52)).pack(pady=(0, 8))
        ctk.CTkLabel(inner, text="EMERGENCY CONTACT",
                     font=ctk.CTkFont(family="MuseoModerno", size=22, weight="bold"),
                     text_color=AMBER).pack(pady=(0, 4))
        ctk.CTkLabel(inner, text="If a critical alert fires, we'll notify this person.",
                     font=ctk.CTkFont(family="Inter", size=10),
                     text_color=TEXT2).pack(pady=(0, 24))

        ctk.CTkLabel(inner, text="CONTACT NAME",
                     font=ctk.CTkFont(family="MuseoModerno", size=9),
                     text_color=TEXT2).pack(anchor="w")
        name_e = self._entry(inner, "e.g. Jane Smith")
        name_e.pack(pady=(4, 14))

        ctk.CTkLabel(inner, text="CONTACT EMAIL",
                     font=ctk.CTkFont(family="MuseoModerno", size=9),
                     text_color=TEXT2).pack(anchor="w")
        email_e = self._entry(inner, "e.g. jane@gmail.com")
        email_e.pack(pady=(4, 8))

        err = ctk.CTkLabel(inner, text="",
                           font=ctk.CTkFont(family="Inter", size=10),
                           text_color=RED)
        err.pack(pady=(0, 12))

        def confirm():
            name  = name_e.get().strip()
            email = email_e.get().strip()
            if not name and not email:
                err.configure(text="Please enter at least a name or email.")
                return
            state["contact_name"]  = name
            state["contact_email"] = email
            self._after_emergency()

        def skip():
            state["contact_name"]  = ""
            state["contact_email"] = ""
            self._after_emergency()

        self._btn(inner, "SAVE CONTACT", confirm)
        self._btn(inner, "Skip for now", skip, outline=True)
        ctk.CTkLabel(inner, text="You can update this later in settings.",
                     font=ctk.CTkFont(family="Inter", size=9),
                     text_color=BORDER).pack(pady=(12, 0))

        self.bind("<Return>", lambda e: confirm())
        name_e.focus()

    def _after_emergency(self):
        self.unbind("<Return>")
        user = self._user
        needs_cal = user.get("needs_calibration") or user.get("ear_threshold") is None
        if needs_cal:
            self._show_calibration()
        else:
            state["ear_threshold"]  = user["ear_threshold"]
            state["pitch_baseline"] = user["pitch_baseline"]
            self._show_dashboard()

    # =========================================================================
    # Page 4 — Calibration
    # =========================================================================

    def _show_calibration(self):
        self._clear()
        self._cal_step       = 0
        self._cal_collecting = False
        self._cal_samples    = []
        self._cal_done       = False
        self._start_camera()

        prog_frame = ctk.CTkFrame(self, fg_color=BG, height=52)
        prog_frame.pack(fill="x", padx=60, pady=(12, 0))
        dot_row = ctk.CTkFrame(prog_frame, fg_color="transparent")
        dot_row.pack(anchor="center")
        self._cal_dots   = []
        self._cal_labels = []
        for i, step in enumerate(CAL_STEPS):
            col = ctk.CTkFrame(dot_row, fg_color="transparent")
            col.pack(side="left", padx=28)
            dot = ctk.CTkLabel(col, text="●",
                               font=ctk.CTkFont(family="Inter", size=18),
                               text_color=BORDER)
            dot.pack()
            lbl = ctk.CTkLabel(col, text=step["title"],
                               font=ctk.CTkFont(family="Inter", size=9),
                               text_color=TEXT2)
            lbl.pack()
            self._cal_dots.append(dot)
            self._cal_labels.append(lbl)

        body = ctk.CTkFrame(self, fg_color=BG)
        body.pack(fill="both", expand=True, padx=60, pady=12)

        cam_frame = ctk.CTkFrame(body, fg_color=CARD, corner_radius=12,
                                 border_width=1, border_color=BORDER)
        cam_frame.pack(side="left", fill="both", expand=True, padx=(0, 16))
        self._cal_canvas = ctk.CTkCanvas(cam_frame, bg="#000", highlightthickness=0)
        self._cal_canvas.pack(fill="both", expand=True, padx=2, pady=2)

        right = ctk.CTkFrame(body, fg_color=CARD, corner_radius=12,
                             border_width=1, border_color=BORDER, width=320)
        right.pack(side="right", fill="y")
        right.pack_propagate(False)

        panel = ctk.CTkFrame(right, fg_color="transparent")
        panel.place(relx=0.5, rely=0.4, anchor="center")

        self._cal_step_lbl = ctk.CTkLabel(panel, text="STEP 1 OF 3",
                                          font=ctk.CTkFont(family="Inter", size=10),
                                          text_color=TEXT2)
        self._cal_step_lbl.pack(pady=(0, 8))
        self._cal_icon_lbl = ctk.CTkLabel(panel, text="👁",
                                          font=ctk.CTkFont(size=56))
        self._cal_icon_lbl.pack(pady=(0, 10))
        self._cal_title_lbl = ctk.CTkLabel(panel, text="",
                                           font=ctk.CTkFont(family="Inter", size=20, weight="bold"),
                                           text_color=GREEN)
        self._cal_title_lbl.pack(pady=(0, 8))
        self._cal_instr_lbl = ctk.CTkLabel(panel, text="",
                                           font=ctk.CTkFont(family="Inter", size=12),
                                           text_color=TEXT, wraplength=260, justify="center")
        self._cal_instr_lbl.pack(pady=(0, 6))
        self._cal_sub_lbl = ctk.CTkLabel(panel, text="",
                                         font=ctk.CTkFont(family="Inter", size=10),
                                         text_color=TEXT2, wraplength=260, justify="center")
        self._cal_sub_lbl.pack(pady=(0, 20))
        self._cal_prog = ctk.CTkProgressBar(panel, width=260,
                                            fg_color=PANEL, progress_color=AMBER)
        self._cal_prog.set(0)
        self._cal_prog.pack(pady=(0, 10))
        self._cal_status_lbl = ctk.CTkLabel(panel, text="Position your face in the camera",
                                            font=ctk.CTkFont(family="Inter", size=10),
                                            text_color=TEXT2)
        self._cal_status_lbl.pack(pady=(0, 16))
        self._cal_btn = ctk.CTkButton(panel, text="START COLLECTING",
                                      command=self._cal_on_btn,
                                      font=ctk.CTkFont(family="Inter", size=12, weight="bold"),
                                      fg_color=AMBER, hover_color=AMBER2,
                                      text_color="#000", width=260, height=44, corner_radius=6)
        self._cal_btn.pack()
        self._update_cal_step_ui()
        self._cal_camera_loop()

    def _update_cal_step_ui(self):
        step = CAL_STEPS[self._cal_step]
        for i, (dot, lbl) in enumerate(zip(self._cal_dots, self._cal_labels)):
            if i < self._cal_step:
                dot.configure(text_color=GREEN); lbl.configure(text_color=GREEN)
            elif i == self._cal_step:
                dot.configure(text_color=step["color"]); lbl.configure(text_color=step["color"])
            else:
                dot.configure(text_color=BORDER); lbl.configure(text_color=TEXT2)
        self._cal_step_lbl.configure(text=f"STEP {self._cal_step + 1} OF 3")
        self._cal_icon_lbl.configure(text=step["icon"])
        self._cal_title_lbl.configure(text=step["title"], text_color=step["color"])
        self._cal_instr_lbl.configure(text=step["instruction"])
        self._cal_sub_lbl.configure(text=step["sub"])
        self._cal_prog.set(0)
        self._cal_prog.configure(progress_color=step["color"])
        self._cal_status_lbl.configure(text="Position your face in the camera", text_color=TEXT2)
        self._cal_btn.configure(text="START COLLECTING", state="normal", fg_color=AMBER)
        self._cal_collecting = False
        self._cal_samples    = []

    def _cal_on_btn(self):
        self._cal_collecting = True
        self._cal_btn.configure(text="COLLECTING...", state="disabled", fg_color=BORDER)
        self._cal_status_lbl.configure(text="Hold still...",
                                       text_color=CAL_STEPS[self._cal_step]["color"])

    def _cal_camera_loop(self):
        if self._cal_done:
            return
        ret, frame = self._cap.read() if self._cap else (False, None)
        if ret and frame is not None:
            frame = cv2.flip(frame, 1)
            h, w  = frame.shape[:2]
            rgb   = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = self._face_mesh.process(rgb) if self._face_mesh else None
            face_detected = False
            if results and results.multi_face_landmarks:
                face_detected = True
                for face_landmarks in results.multi_face_landmarks:
                    def get_point(idx):
                        lm = face_landmarks.landmark[idx]
                        return (lm.x * w, lm.y * h)
                    left_pts  = [get_point(i) for i in LEFT_EYE]
                    right_pts = [get_point(i) for i in RIGHT_EYE]
                    avg_EAR   = (calculate_EAR(left_pts) + calculate_EAR(right_pts)) / 2.0
                    pitch     = calculate_pitch(face_landmarks, w, h)
                    col_bgr   = self._hex_bgr(CAL_STEPS[self._cal_step]["color"])
                    for pt in left_pts + right_pts:
                        cv2.circle(frame, (int(pt[0]), int(pt[1])), 2, col_bgr, -1)
                    pts_l = np.array([(int(p[0]), int(p[1])) for p in left_pts], np.int32)
                    pts_r = np.array([(int(p[0]), int(p[1])) for p in right_pts], np.int32)
                    cv2.polylines(frame, [pts_l], True, col_bgr, 1)
                    cv2.polylines(frame, [pts_r], True, col_bgr, 1)
                    if self._cal_collecting:
                        if self._cal_step in (0, 1):
                            self._cal_samples.append(avg_EAR)
                        elif self._cal_step == 2 and pitch is not None:
                            self._cal_samples.append(pitch)
                        target = CAL_STEPS[self._cal_step]["samples"]
                        count  = len(self._cal_samples)
                        self._cal_prog.set(count / target)
                        if count >= target:
                            self._cal_finish_step()
            if not face_detected and self._cal_btn.cget("state") == "normal":
                self._cal_status_lbl.configure(text="No face detected — move closer", text_color=RED)
            elif face_detected and not self._cal_collecting:
                self._cal_status_lbl.configure(text="Face detected ✓  press START when ready", text_color=GREEN)
            try:
                cw = self._cal_canvas.winfo_width()
                ch = self._cal_canvas.winfo_height()
                if cw > 1 and ch > 1:
                    frame = cv2.resize(frame, (cw, ch))
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                img = Image.fromarray(frame_rgb)
                self._photo = ImageTk.PhotoImage(image=img)
                self._cal_canvas.delete("all")
                self._cal_canvas.create_image(0, 0, anchor="nw", image=self._photo)
            except Exception:
                pass
        if not self._cal_done:
            self.after(33, self._cal_camera_loop)

    def _cal_finish_step(self):
        self._cal_collecting = False
        samples = self._cal_samples[:]
        step    = CAL_STEPS[self._cal_step]
        self._cal_status_lbl.configure(text=f"✓ {step['title']} captured!", text_color=GREEN)
        self._cal_prog.set(1)
        if self._cal_step == 0:
            self._cal_open_avg = float(np.mean(samples))
        elif self._cal_step == 1:
            closed_avg = float(np.mean(samples))
            self._ear_threshold = (self._cal_open_avg + closed_avg) / 2.0
        elif self._cal_step == 2:
            self._pitch_baseline = float(np.mean(samples))
        if self._cal_step < 2:
            self._cal_step += 1
            self.after(800, self._update_cal_step_ui)
        else:
            self.after(800, self._cal_finish_all)

    def _cal_finish_all(self):
        self._cal_done = True
        for dot, lbl in zip(self._cal_dots, self._cal_labels):
            dot.configure(text_color=GREEN)
            lbl.configure(text_color=GREEN)
        self._cal_btn.configure(text="CALIBRATION COMPLETE ✓",
                                fg_color=GREEN, text_color="#000", state="disabled")
        self._cal_title_lbl.configure(text="ALL DONE!", text_color=GREEN)
        self._cal_instr_lbl.configure(text="Your personal profile has been saved.")
        self._cal_sub_lbl.configure(text="Starting Noctura...")
        user = self._user
        if user and user["user_id"] != "guest":
            save_calibration(user["user_id"], self._ear_threshold, self._pitch_baseline)
        state["ear_threshold"]  = self._ear_threshold
        state["pitch_baseline"] = self._pitch_baseline
        self.after(1500, self._show_dashboard)

    # =========================================================================
    # Page 5 — Dashboard
    # =========================================================================

    def _show_dashboard(self):
        self._clear()
        self._session_start = time.time()
        self._alert_log     = []

        if not self._detection_started:
            self._detection_started = True
            threading.Thread(target=run_detection, daemon=True).start()

        if not self._cam_active:
            self._start_camera()

        bar = ctk.CTkFrame(self, fg_color=PANEL, height=52,
                           corner_radius=0, border_width=1, border_color=BORDER)
        bar.pack(fill="x", side="top")
        bar.pack_propagate(False)

        ctk.CTkLabel(bar, text="NOCTURA",
                     font=ctk.CTkFont(family="Inter", size=13, weight="bold"),
                     text_color=AMBER).pack(side="left", padx=16)
        ctk.CTkLabel(bar, text="DRIVER MONITORING SYSTEM · ACTIVE SESSION",
                     font=ctk.CTkFont(size=11), text_color=TEXT2).pack(side="left", padx=8)

        # Profile badge — circle in title bar
        user     = self._user or {}
        initials = (user.get("first_name", "?")[:1] + user.get("last_name", "?")[:1]).upper() or "?"
        pic_path = os.path.join(os.path.dirname(__file__),
                                f"profile_{user.get('user_id', 'guest')}.png")

        self._badge_btn = ctk.CTkButton(
            bar, text=initials,
            command=self._open_profile_modal,
            font=ctk.CTkFont(family="Inter", size=13, weight="bold"),
            fg_color=CYAN, hover_color="#3A6FBA",
            text_color="#FFF", width=38, height=38, corner_radius=19
        )

        if os.path.exists(pic_path):
            try:
                img  = Image.open(pic_path).resize((38, 38)).convert("RGBA")
                mask = Image.new("L", (38, 38), 0)
                ImageDraw.Draw(mask).ellipse((0, 0, 38, 38), fill=255)
                img.putalpha(mask)
                self._badge_photo = ctk.CTkImage(img, size=(38, 38))
                self._badge_btn.configure(image=self._badge_photo, text="")
            except Exception:
                pass

        self._badge_btn.pack(side="right", padx=(4, 12))

        ctk.CTkButton(bar, text="END SESSION",
                      command=self._end_session,
                      font=ctk.CTkFont(family="Inter", size=11, weight="bold"),
                      fg_color="transparent", hover_color=PANEL,
                      text_color=TEXT2, border_width=1, border_color=BORDER,
                      width=110, height=30, corner_radius=4).pack(side="right", padx=4)

        self._status_label = ctk.CTkLabel(bar, text="● MONITORING",
                                          font=ctk.CTkFont(family="Inter", size=11),
                                          text_color=GREEN)
        self._status_label.pack(side="right", padx=16)

        self._session_label = ctk.CTkLabel(bar, text="00:00:00",
                                           font=ctk.CTkFont(family="Inter", size=11),
                                           text_color=TEXT2)
        self._session_label.pack(side="right", padx=16)

        body = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        body.pack(fill="both", expand=True)

        left = ctk.CTkFrame(body, fg_color=PANEL, width=240, corner_radius=0,
                            border_width=1, border_color=BORDER)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)
        self._build_left_panel(left)

        right = ctk.CTkFrame(body, fg_color=PANEL, width=260, corner_radius=0,
                             border_width=1, border_color=BORDER)
        right.pack(side="right", fill="y")
        right.pack_propagate(False)
        self._build_right_panel(right)

        center = ctk.CTkFrame(body, fg_color="#000", corner_radius=0)
        center.pack(side="left", fill="both", expand=True)
        self._build_center(center)

        self._dashboard_active = True
        self._dashboard_loop()

    def _end_session(self):
        self._dashboard_active = False
        self._hide_profile_badge()
        state["end_session"]   = True
        state["session_id"]    = None
        self.after(500, self._wait_for_session_save)

    def _wait_for_session_save(self):
        if state.get("session_id") is not None:
            self._show_report()
        else:
            self.after(200, self._wait_for_session_save)

    # ── Left panel ────────────────────────────────────────────────────────────

    def _build_left_panel(self, parent):
        pad = {"padx": 16, "pady": (10, 2)}

        ctk.CTkLabel(parent, text="EAR VALUE",
                     font=ctk.CTkFont(family="Inter", size=9),
                     text_color=TEXT2).pack(anchor="w", padx=16, pady=(14, 0))

        self._ear_canvas = ctk.CTkCanvas(parent, width=130, height=130,
                                         bg=PANEL, highlightthickness=0)
        self._ear_canvas.pack(pady=4)
        self._draw_ear_ring(0.31)

        ctk.CTkFrame(parent, fg_color=BORDER, height=1,
                     corner_radius=0).pack(fill="x", padx=16, pady=6)

        ctk.CTkLabel(parent, text="ALERT STAGE",
                     font=ctk.CTkFont(family="Inter", size=9),
                     text_color=TEXT2).pack(anchor="w", **pad)

        self.stage_label = ctk.CTkLabel(parent, text="STAGE 0",
                                        font=ctk.CTkFont(family="Inter", size=18, weight="bold"),
                                        text_color=GREEN)
        self.stage_label.pack(anchor="w", padx=16, pady=(0, 8))

        ctk.CTkFrame(parent, fg_color=BORDER, height=1,
                     corner_radius=0).pack(fill="x", padx=16, pady=4)

        for stage, desc, color in [
            ("Stage 1", "3s — audio alarm", AMBER),
            ("Stage 2", "5s — loud alarm",  "#FF8C00"),
            ("SMS",     "8s — email alert", RED),
        ]:
            row = ctk.CTkFrame(parent, fg_color=CARD, corner_radius=4)
            row.pack(fill="x", padx=12, pady=1)
            ctk.CTkFrame(row, fg_color=color, width=3, corner_radius=0).pack(side="left", fill="y")
            ctk.CTkLabel(row, text=stage,
                         font=ctk.CTkFont(family="Inter", size=10, weight="bold"),
                         text_color=color, width=56, anchor="w").pack(side="left", padx=6, pady=6)
            ctk.CTkLabel(row, text=desc,
                         font=ctk.CTkFont(family="Inter", size=9),
                         text_color=TEXT2).pack(side="left")

        ctk.CTkButton(
            parent, text="STOP ALARM",
            command=self._stop_alarm,
            font=ctk.CTkFont(family="Inter", size=12, weight="bold"),
            fg_color=RED, hover_color="#CC2222",
            text_color="#FFFFFF", corner_radius=0, height=48
        ).pack(fill="x", side="bottom")

        ctk.CTkFrame(parent, fg_color=BORDER, height=1,
                     corner_radius=0).pack(fill="x", side="bottom")

    def _draw_ear_ring(self, ear_val):
        c = self._ear_canvas
        c.delete("all")
        cx, cy, r = 65, 65, 48
        c.create_arc(cx-r, cy-r, cx+r, cy+r,
                     start=0, extent=359.9,
                     outline=BORDER2, width=8, style="arc")
        pct    = max(0, min(1, (ear_val - 0.08) / 0.34))
        extent = pct * 359.9
        color  = RED if ear_val < 0.20 else AMBER if ear_val < 0.25 else GREEN
        if extent > 0:
            c.create_arc(cx-r, cy-r, cx+r, cy+r,
                         start=90, extent=-extent,
                         outline=color, width=8, style="arc")
        c.create_text(cx, cy - 8, text=f"{ear_val:.2f}",
                      font=("Inter", 22, "bold"), fill=color)
        c.create_text(cx, cy + 16, text="EAR",
                      font=("Inter", 9), fill=TEXT2)

    # ── Right panel ───────────────────────────────────────────────────────────

    def _build_right_panel(self, parent):
        pad = {"padx": 14, "pady": (10, 2)}

        ctk.CTkLabel(parent, text="PERCLOS · 3s WINDOW",
                     font=ctk.CTkFont(family="Inter", size=9),
                     text_color=TEXT2).pack(anchor="w", padx=14, pady=(14, 0))

        self._perclos_canvas = ctk.CTkCanvas(parent, width=220, height=120,
                                             bg=PANEL, highlightthickness=0)
        self._perclos_canvas.pack(pady=4)
        self._draw_perclos_arc(0.0)

        ctk.CTkFrame(parent, fg_color=BORDER, height=1,
                     corner_radius=0).pack(fill="x", padx=14, pady=6)

        ctk.CTkLabel(parent, text="ALERT LOG",
                     font=ctk.CTkFont(family="Inter", size=9),
                     text_color=TEXT2).pack(anchor="w", **pad)

        log_frame = ctk.CTkFrame(parent, fg_color="transparent")
        log_frame.pack(fill="x", padx=14, pady=(0, 8))

        self._log_labels = []
        for _ in range(4):
            row = ctk.CTkFrame(log_frame, fg_color="transparent")
            row.pack(fill="x", pady=1)
            dot = ctk.CTkLabel(row, text="●",
                               font=ctk.CTkFont(family="Inter", size=8),
                               text_color=BORDER, width=14)
            dot.pack(side="left")
            lbl = ctk.CTkLabel(row, text="—",
                               font=ctk.CTkFont(family="Inter", size=9),
                               text_color=TEXT3, anchor="w")
            lbl.pack(side="left", fill="x", expand=True)
            self._log_labels.append((dot, lbl))

        ctk.CTkFrame(parent, fg_color=BORDER, height=1,
                     corner_radius=0).pack(fill="x", padx=14, pady=6)

        ctk.CTkLabel(parent, text="SENSITIVITY",
                     font=ctk.CTkFont(family="Inter", size=9),
                     text_color=TEXT2).pack(anchor="w", **pad)

        slider_row = ctk.CTkFrame(parent, fg_color="transparent")
        slider_row.pack(fill="x", padx=14, pady=(2, 0))

        self._thresh_val_lbl = ctk.CTkLabel(slider_row, text="0.25",
                                            font=ctk.CTkFont(family="Inter", size=10),
                                            text_color=AMBER, width=36)
        self._thresh_val_lbl.pack(side="right")

        self._slider = ctk.CTkSlider(slider_row, from_=15, to=35,
                                     button_color=AMBER,
                                     button_hover_color=AMBER2,
                                     progress_color=AMBER,
                                     fg_color=BORDER2,
                                     command=self._on_slider)
        self._slider.set(25)
        self._slider.pack(side="left", fill="x", expand=True, padx=(0, 8))

        ctk.CTkFrame(parent, fg_color="transparent").pack(fill="y", expand=True)

        gem_card = ctk.CTkFrame(parent, fg_color="#0A1A0F", corner_radius=8,
                                border_width=1, border_color="#1A3020")
        gem_card.pack(fill="x", padx=14, pady=(0, 14))

        header = ctk.CTkFrame(gem_card, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=(8, 4))
        ctk.CTkLabel(header, text="●",
                     font=ctk.CTkFont(family="Inter", size=8),
                     text_color=GREEN).pack(side="left")
        ctk.CTkLabel(header, text="  NOCTURA AI · SESSION INSIGHT",
                     font=ctk.CTkFont(family="Inter", size=8),
                     text_color=GREEN).pack(side="left")

        self._gemini_lbl = ctk.CTkLabel(gem_card,
                                        text="Monitoring active. No events yet.",
                                        font=ctk.CTkFont(family="Inter", size=9),
                                        text_color=TEXT2,
                                        wraplength=220, justify="left", anchor="w")
        self._gemini_lbl.pack(fill="x", padx=10, pady=(0, 10))

    def _draw_perclos_arc(self, perclos_val):
        c = self._perclos_canvas
        c.delete("all")
        cx, cy, r = 110, 105, 80
        c.create_arc(cx-r, cy-r, cx+r, cy+r,
                     start=0, extent=180,
                     outline=BORDER2, width=10, style="arc")
        pct    = max(0, min(1, perclos_val))
        extent = pct * 180
        color  = RED if pct > 0.15 else AMBER if pct > 0.08 else GREEN
        if extent > 0:
            c.create_arc(cx-r, cy-r, cx+r, cy+r,
                         start=180, extent=extent,
                         outline=color, width=10, style="arc")
        c.create_text(cx, cy - 14, text=f"{int(perclos_val * 100)}%",
                      font=("Inter", 20, "bold"), fill=color)
        c.create_text(cx, cy + 6, text="PERCLOS",
                      font=("Inter", 8), fill=TEXT2)

    def _on_slider(self, val):
        self._thresh_val_lbl.configure(text=f"{val/100:.2f}")

    # ── Center panel ──────────────────────────────────────────────────────────

    def _build_center(self, parent):
        self.dash_canvas = ctk.CTkCanvas(parent, bg="#000", highlightthickness=0)
        self.dash_canvas.pack(fill="both", expand=True)

        self.alert_overlay = ctk.CTkLabel(parent, text="",
                                          font=ctk.CTkFont(family="Inter", size=16, weight="bold"),
                                          text_color=RED, fg_color="transparent")
        self.alert_overlay.place(relx=0.5, rely=0.05, anchor="n")

        self.stop_btn = ctk.CTkButton(
            parent, text="STOP ALARM",
            command=self._stop_alarm,
            font=ctk.CTkFont(family="Inter", size=14, weight="bold"),
            fg_color=RED, hover_color="#CC2222",
            text_color="#FFFFFF", width=200, height=52, corner_radius=8
        )
        self.stop_btn.place_forget()

    # =========================================================================
    # Dashboard loop
    # =========================================================================

    def _dashboard_loop(self):
        if not self._dashboard_active:
            return

        if self._session_start:
            elapsed = int(time.time() - self._session_start)
            h = elapsed // 3600
            m = (elapsed % 3600) // 60
            s = elapsed % 60
            self._session_label.configure(text=f"{h:02d}:{m:02d}:{s:02d}")

        frame = state.get("frame")
        if frame is not None:
            try:
                cw = self.dash_canvas.winfo_width()
                ch = self.dash_canvas.winfo_height()
                if cw > 1 and ch > 1:
                    disp = cv2.resize(frame, (cw, ch))
                    frame_rgb = cv2.cvtColor(disp, cv2.COLOR_BGR2RGB)
                    img = Image.fromarray(frame_rgb)
                    self._photo = ImageTk.PhotoImage(image=img)
                    self.dash_canvas.delete("all")
                    self.dash_canvas.create_image(0, 0, anchor="nw", image=self._photo)
            except Exception:
                pass

        ear     = state.get("ear", 0.0)
        stage   = state.get("alert_stage", 0)
        perclos = state.get("perclos", 0.0)

        self._draw_ear_ring(ear)
        self._draw_perclos_arc(perclos)

        stage_colors = {0: GREEN, 1: AMBER, 2: "#FF8C00", 3: RED}
        stage_texts  = {0: "STAGE 0", 1: "STAGE 1", 2: "STAGE 2", 3: "SMS SENT"}
        self.stage_label.configure(text=stage_texts.get(stage, "STAGE 0"),
                                   text_color=stage_colors.get(stage, GREEN))

        if stage >= 2:
            self._status_label.configure(text="⚠  FATIGUE DETECTED", text_color=RED)
            self.alert_overlay.configure(text="⚠   DROWSINESS DETECTED — PULL OVER")
            self._add_log_entry(stage)
        elif stage == 1:
            self._status_label.configure(text="●  STAGE 1 WARNING", text_color=AMBER)
            self.alert_overlay.configure(text="")
            self._add_log_entry(stage)
        else:
            self._status_label.configure(text="●  MONITORING", text_color=GREEN)
            self.alert_overlay.configure(text="")

        if stage >= 1:
            self.stop_btn.place(relx=0.5, rely=0.88, anchor="center")
        else:
            self.stop_btn.place_forget()

        alert_count   = len(self._alert_log)
        fatigue_flags = state.get("fatigue_flags", [])
        if alert_count == 0:
            self._gemini_lbl.configure(text="Monitoring active. No events yet.")
        elif fatigue_flags:
            self._gemini_lbl.configure(text=f"Signals: {', '.join(fatigue_flags)}. {alert_count} alert(s).")
        elif alert_count == 1:
            self._gemini_lbl.configure(text="1 alert so far. Stay focused.")
        else:
            self._gemini_lbl.configure(text=f"{alert_count} alerts. Consider a break soon.")

        self.after(33, self._dashboard_loop)

    def _add_log_entry(self, stage):
        if self._session_start is None:
            return
        elapsed = int(time.time() - self._session_start)
        h = elapsed // 3600
        m = (elapsed % 3600) // 60
        s = elapsed % 60
        ts = f"{h:02d}:{m:02d}:{s:02d}"
        if self._alert_log and self._alert_log[-1][0] == ts:
            return
        self._alert_log.append((ts, stage))
        stage_colors = {1: AMBER, 2: "#FF8C00", 3: RED}
        label_texts  = {1: "Stage 1 — drowsiness", 2: "Stage 2 — danger", 3: "SMS sent"}
        recent = self._alert_log[-4:]
        for i, (dot, lbl) in enumerate(self._log_labels):
            if i < len(recent):
                _, s = recent[-(i+1)]
                dot.configure(text_color=stage_colors.get(s, TEXT2))
                lbl.configure(text=f"{recent[-(i+1)][0]}  {label_texts.get(s, '')}", text_color=TEXT2)
            else:
                dot.configure(text_color=BORDER)
                lbl.configure(text="—", text_color=TEXT3)

    def _stop_alarm(self):
        state["alarm_silenced"] = True
        state["alert_stage"]    = 0
        self._status_label.configure(text="●  SILENCED", text_color=TEXT2)
        self.stage_label.configure(text="STAGE 0", text_color=GREEN)
        self.alert_overlay.configure(text="")

    # =========================================================================
    # Page 6 — Session Report
    # =========================================================================

    def _show_report(self):
        self._clear()
        self._stop_camera()
        self._title_bar("SESSION REPORT")

        session_id = state.get("session_id")
        user       = self._user or {}
        user_name  = f"{user.get('first_name','')} {user.get('last_name','')}".strip() or "Driver"
        user_id    = user.get("user_id", "guest")

        outer = ctk.CTkFrame(self, fg_color=BG)
        outer.pack(fill="both", expand=True)

        tab_bar = ctk.CTkFrame(outer, fg_color=PANEL, height=40,
                               corner_radius=0, border_width=1, border_color=BORDER)
        tab_bar.pack(fill="x")
        tab_bar.pack_propagate(False)

        self._report_canvas = ctk.CTkCanvas(outer, bg="#0a0c0f", highlightthickness=0)
        self._report_canvas.pack(fill="both", expand=True)

        self._report_loading = ctk.CTkLabel(
            outer, text="Building your report...",
            font=ctk.CTkFont(family="Inter", size=13),
            text_color=TEXT2, fg_color="transparent"
        )
        self._report_loading.place(relx=0.5, rely=0.5, anchor="center")

        bottom = ctk.CTkFrame(outer, fg_color=PANEL, height=52,
                              corner_radius=0, border_width=1, border_color=BORDER)
        bottom.pack(fill="x", side="bottom")
        bottom.pack_propagate(False)

        ctk.CTkButton(bottom, text="CLOSE APP",
                      command=self._on_close,
                      font=ctk.CTkFont(family="Inter", size=12, weight="bold"),
                      fg_color=BORDER, hover_color=BORDER2,
                      text_color=TEXT, corner_radius=6,
                      width=160, height=34).pack(side="right", padx=16, pady=9)

        def show_session_tab():
            session_btn.configure(fg_color=AMBER, text_color="#000")
            history_btn.configure(fg_color="transparent", text_color=TEXT2)
            threading.Thread(target=self._render_report_figure,
                             args=(session_id, user_name, user_id, "session"),
                             daemon=True).start()

        def show_history_tab():
            history_btn.configure(fg_color=AMBER, text_color="#000")
            session_btn.configure(fg_color="transparent", text_color=TEXT2)
            threading.Thread(target=self._render_report_figure,
                             args=(session_id, user_name, user_id, "history"),
                             daemon=True).start()

        session_btn = ctk.CTkButton(tab_bar, text="THIS SESSION",
                                    command=show_session_tab,
                                    font=ctk.CTkFont(family="Inter", size=11, weight="bold"),
                                    fg_color=AMBER, hover_color=AMBER2,
                                    text_color="#000", width=140, height=28, corner_radius=4)
        session_btn.pack(side="left", padx=8, pady=6)

        history_btn = ctk.CTkButton(tab_bar, text="DRIVE HISTORY",
                                    command=show_history_tab,
                                    font=ctk.CTkFont(family="Inter", size=11, weight="bold"),
                                    fg_color="transparent", hover_color=PANEL,
                                    text_color=TEXT2, border_width=1, border_color=BORDER,
                                    width=140, height=28, corner_radius=4)
        history_btn.pack(side="left", padx=4, pady=6)

        ctk.CTkLabel(tab_bar, text="Session saved ✓",
                     font=ctk.CTkFont(family="Inter", size=10),
                     text_color=GREEN).pack(side="right", padx=16)

        threading.Thread(target=self._render_report_figure,
                         args=(session_id, user_name, user_id, "session"),
                         daemon=True).start()

    def _render_report_figure(self, session_id, user_name, user_id, tab):
        try:
            from report import get_session_figure, get_history_figure
            fig = get_session_figure(session_id or -1, user_name) if tab == "session" \
                  else get_history_figure(user_id, user_name)
            buf = io.BytesIO()
            fig.savefig(buf, format="png", dpi=96, bbox_inches="tight", facecolor="#0a0c0f")
            buf.seek(0)
            img = Image.open(buf).copy()

            def update():
                try:
                    cw = self._report_canvas.winfo_width()
                    ch = self._report_canvas.winfo_height()
                    img_resized = img.resize((cw, ch), Image.LANCZOS) if cw > 10 and ch > 10 else img
                    self._report_photo = ImageTk.PhotoImage(img_resized)
                    self._report_canvas.delete("all")
                    self._report_canvas.create_image(0, 0, anchor="nw", image=self._report_photo)
                    self._report_loading.place_forget()
                except Exception as e:
                    print(f"[Report] UI error: {e}")

            self.after(0, update)
        except Exception as e:
            print(f"[Report] Render error: {e}")
            self.after(0, lambda: self._report_loading.configure(text=f"Report error: {e}"))

    # =========================================================================
    # Profile badge
    # =========================================================================

    def _show_profile_badge(self):
        user     = self._user or {}
        initials = (user.get("first_name", "?")[:1] + user.get("last_name", "?")[:1]).upper() or "?"
        pic_path = os.path.join(os.path.dirname(__file__),
                                f"profile_{user.get('user_id', 'guest')}.png")

        self._badge_btn = ctk.CTkButton(
            self, text=initials,
            command=self._open_profile_modal,
            font=ctk.CTkFont(family="Inter", size=14, weight="bold"),
            fg_color=CYAN, hover_color="#3A6FBA",
            text_color="#FFF", width=48, height=48, corner_radius=24
        )

        if os.path.exists(pic_path):
            try:
                img  = Image.open(pic_path).resize((48, 48)).convert("RGBA")
                mask = Image.new("L", (48, 48), 0)
                ImageDraw.Draw(mask).ellipse((0, 0, 48, 48), fill=255)
                img.putalpha(mask)
                self._badge_photo = ctk.CTkImage(img, size=(48, 48))
                self._badge_btn.configure(image=self._badge_photo, text="")
            except Exception:
                pass

        # Place in top-right corner, stable position
        self._badge_btn.place(x=self.winfo_width() - 64, y=8)

    def _hide_profile_badge(self):
        if self._badge_btn is not None:
            try:
                self._badge_btn.destroy()
            except Exception:
                pass
            self._badge_btn = None

    def _reposition_badge(self, event=None):
        if self._badge_btn is not None:
            try:
                self._badge_btn.place(x=self.winfo_width() - 64, y=8)
            except Exception:
                pass

    def _open_profile_modal(self):
        import sqlite3
        from auth import get_driver_profile

        user     = self._user or {}
        user_id  = user.get("user_id", "guest")
        initials = (user.get("first_name", "?")[:1] + user.get("last_name", "?")[:1]).upper()
        pic_path = os.path.join(os.path.dirname(__file__), f"profile_{user_id}.png")

        overlay = ctk.CTkFrame(self, fg_color="#000000", corner_radius=0)
        overlay.place(x=0, y=0, relwidth=1, relheight=1)

        card = ctk.CTkFrame(overlay, fg_color=CARD, corner_radius=16,
                            border_width=1, border_color=BORDER, width=480, height=680)
        card.place(relx=0.5, rely=0.5, anchor="center")
        card.pack_propagate(False)

        inner = ctk.CTkScrollableFrame(card, fg_color="transparent",
                                       scrollbar_button_color=BORDER,
                                       scrollbar_button_hover_color=BORDER2)
        inner.pack(fill="both", expand=True, padx=28, pady=24)

        # Mac scroll fix
        def _on_modal_scroll(e):
            inner._parent_canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
        inner.bind_all("<MouseWheel>", _on_modal_scroll)

        # ── Avatar ────────────────────────────────────────────────────────────
        avatar_frame = ctk.CTkFrame(inner, fg_color=CYAN,
                                    width=84, height=84, corner_radius=42)
        avatar_frame.pack(pady=(0, 6))
        avatar_frame.pack_propagate(False)

        if os.path.exists(pic_path):
            try:
                img     = Image.open(pic_path).resize((84, 84)).convert("RGBA")
                pic_img = ctk.CTkImage(img, size=(84, 84))
                ctk.CTkLabel(avatar_frame, image=pic_img, text="").place(
                    relx=0.5, rely=0.5, anchor="center")
            except Exception:
                ctk.CTkLabel(avatar_frame, text=initials,
                             font=ctk.CTkFont(family="Inter", size=26, weight="bold"),
                             text_color="#FFF").place(relx=0.5, rely=0.5, anchor="center")
        else:
            ctk.CTkLabel(avatar_frame, text=initials,
                         font=ctk.CTkFont(family="Inter", size=26, weight="bold"),
                         text_color="#FFF").place(relx=0.5, rely=0.5, anchor="center")

        def upload_pic():
            from tkinter import filedialog
            path = filedialog.askopenfilename(
                title="Select profile picture",
                filetypes=[("Image files", "*.png *.jpg *.jpeg")]
            )
            if path:
                try:
                    img = Image.open(path).resize((256, 256))
                    img.save(pic_path)
                    overlay.destroy()
                    self._hide_profile_badge()
                    self._show_profile_badge()
                    self._open_profile_modal()
                except Exception as e:
                    print(f"[Profile] Error: {e}")

        ctk.CTkButton(inner, text="📷  Change Photo", command=upload_pic,
                      font=ctk.CTkFont(family="Inter", size=10),
                      fg_color="transparent", hover_color=PANEL,
                      text_color=TEXT2, border_width=1, border_color=BORDER,
                      width=150, height=28, corner_radius=6).pack(pady=(0, 16))

        # ── Editable name + user ID ───────────────────────────────────────────
        ctk.CTkLabel(inner, text="ACCOUNT INFO",
                     font=ctk.CTkFont(family="Inter", size=9),
                     text_color=TEXT2).pack(anchor="w", pady=(0, 6))

        name_row = ctk.CTkFrame(inner, fg_color="transparent")
        name_row.pack(fill="x", pady=(0, 8))
        first_e = ctk.CTkEntry(name_row, placeholder_text="First name",
                               font=ctk.CTkFont(family="Inter", size=12),
                               fg_color=PANEL, border_color=BORDER, border_width=1,
                               text_color=TEXT, placeholder_text_color=TEXT2,
                               width=196, height=38, corner_radius=6)
        first_e.insert(0, user.get("first_name", ""))
        first_e.pack(side="left", padx=(0, 8))

        last_e = ctk.CTkEntry(name_row, placeholder_text="Last name",
                              font=ctk.CTkFont(family="Inter", size=12),
                              fg_color=PANEL, border_color=BORDER, border_width=1,
                              text_color=TEXT, placeholder_text_color=TEXT2,
                              width=196, height=38, corner_radius=6)
        last_e.insert(0, user.get("last_name", ""))
        last_e.pack(side="left")

        uid_e = ctk.CTkEntry(inner, placeholder_text="User ID",
                             font=ctk.CTkFont(family="Inter", size=12),
                             fg_color=PANEL, border_color=BORDER, border_width=1,
                             text_color=TEXT, placeholder_text_color=TEXT2,
                             width=400, height=38, corner_radius=6)
        uid_e.insert(0, user_id)
        uid_e.pack(pady=(0, 4))
        if user_id == "guest":
            uid_e.configure(state="disabled")

        ctk.CTkFrame(inner, fg_color=BORDER, height=1,
                     corner_radius=0).pack(fill="x", pady=12)
        
        ctk.CTkFrame(inner, fg_color=BORDER, height=1,
                     corner_radius=0).pack(fill="x", pady=12)

        # ── Emergency contact ─────────────────────────────────────────────────
        ctk.CTkLabel(inner, text="EMERGENCY CONTACT",
                     font=ctk.CTkFont(family="Inter", size=9),
                     text_color=TEXT2).pack(anchor="w", pady=(0, 6))

        ec_name_e = ctk.CTkEntry(inner, placeholder_text="Contact name",
                                 font=ctk.CTkFont(family="Inter", size=12),
                                 fg_color=PANEL, border_color=BORDER, border_width=1,
                                 text_color=TEXT, placeholder_text_color=TEXT2,
                                 width=400, height=38, corner_radius=6)
        ec_name_e.insert(0, user.get("emergency_email", "").split("|")[0] if "|" in user.get("emergency_email", "") else state.get("contact_name", ""))
        ec_name_e.pack(pady=(0, 8))

        ec_email_e = ctk.CTkEntry(inner, placeholder_text="Contact email",
                                  font=ctk.CTkFont(family="Inter", size=12),
                                  fg_color=PANEL, border_color=BORDER, border_width=1,
                                  text_color=TEXT, placeholder_text_color=TEXT2,
                                  width=400, height=38, corner_radius=6)
        ec_email_e.insert(0, user.get("emergency_email", ""))
        ec_email_e.pack(pady=(0, 4))

        ctk.CTkFrame(inner, fg_color=BORDER, height=1,
                     corner_radius=0).pack(fill="x", pady=12)


        # ── Editable driver profile ───────────────────────────────────────────
        ctk.CTkLabel(inner, text="DRIVER PROFILE",
                     font=ctk.CTkFont(family="Inter", size=9),
                     text_color=TEXT2).pack(anchor="w", pady=(0, 8))

        profile   = get_driver_profile(user_id)
        answers   = {}

        for q in PROFILE_QUESTIONS:
            ctk.CTkLabel(inner, text=q["label"],
                         font=ctk.CTkFont(family="Inter", size=10, weight="bold"),
                         text_color=TEXT, anchor="w").pack(fill="x", pady=(6, 2))

            if q["type"] == "choice":
                current_vals = profile.get(q["key"], "").split(",") if profile.get(q["key"]) else []
                selected     = list(current_vals)
                answers[q["key"]] = selected
                btn_row = ctk.CTkFrame(inner, fg_color="transparent")
                btn_row.pack(fill="x", pady=(0, 4))
                btn_refs = []

                def make_cmd(v, sel_list, refs):
                    def cmd():
                        if v in sel_list:
                            sel_list.remove(v)
                        else:
                            sel_list.append(v)
                        for b, bv in refs:
                            b.configure(
                                fg_color=AMBER if bv in sel_list else "transparent",
                                text_color="#000" if bv in sel_list else TEXT2
                            )
                    return cmd

                for label, value in zip(q["options"], q["values"]):
                    is_sel = value in current_vals
                    btn = ctk.CTkButton(btn_row, text=label,
                                        font=ctk.CTkFont(family="Inter", size=10),
                                        fg_color=AMBER if is_sel else "transparent",
                                        hover_color=BORDER2,
                                        text_color="#000" if is_sel else TEXT2,
                                        border_width=1, border_color=BORDER,
                                        height=32, corner_radius=6)
                    btn.pack(side="left", padx=(0, 6), pady=2)
                    btn_refs.append((btn, value))

                for btn, value in btn_refs:
                    btn.configure(command=make_cmd(value, selected, btn_refs))

            elif q["type"] == "text":
                entry = ctk.CTkEntry(inner, placeholder_text=q.get("placeholder", ""),
                                     font=ctk.CTkFont(family="Inter", size=12),
                                     fg_color=PANEL, border_color=BORDER, border_width=1,
                                     text_color=TEXT, placeholder_text_color=TEXT2,
                                     width=400, height=38, corner_radius=6)
                current_val = profile.get(q["key"], "")
                if current_val:
                    entry.insert(0, current_val)
                entry.pack(pady=(0, 4))
                answers[q["key"]] = entry

        ctk.CTkFrame(inner, fg_color=BORDER, height=1,
                     corner_radius=0).pack(fill="x", pady=12)

        err_lbl = ctk.CTkLabel(inner, text="",
                               font=ctk.CTkFont(family="Inter", size=10),
                               text_color=RED)
        err_lbl.pack(pady=(0, 8))

        # ── Save ──────────────────────────────────────────────────────────────
        def save_changes():
            new_first = first_e.get().strip()
            new_last  = last_e.get().strip()
            new_uid   = uid_e.get().strip()

            if not new_first or not new_last:
                err_lbl.configure(text="First and last name are required.")
                return

            # Save name to DB
            if user_id != "guest":
                try:
                    import sqlite3
                    from auth import DB_PATH
                    con = sqlite3.connect(DB_PATH)
                    con.execute(
                        "UPDATE users SET first_name=?, last_name=? WHERE user_id=?",
                        (new_first, new_last, user_id)
                    )
                    con.commit()
                    con.close()
                    # Update in-memory user
                    self._user["first_name"] = new_first
                    self._user["last_name"]  = new_last
                except Exception as e:
                    err_lbl.configure(text=f"Error saving: {e}")
                    return
            # Save emergency contact to state + DB
            new_ec_name  = ec_name_e.get().strip()
            new_ec_email = ec_email_e.get().strip()
            state["contact_name"]  = new_ec_name
            state["contact_email"] = new_ec_email
            if user_id != "guest":
                try:
                    from auth import DB_PATH
                    con = sqlite3.connect(DB_PATH)
                    con.execute(
                        "UPDATE users SET emergency_email=? WHERE user_id=?",
                        (new_ec_email, user_id)
                    )
                    con.commit()
                    con.close()
                    self._user["emergency_email"] = new_ec_email
                except Exception as e:
                    err_lbl.configure(text=f"Error saving contact: {e}")
                    return

            # Save driver profile
            profile_data = {}
            for key, widget in answers.items():
                if isinstance(widget, list):
                    if widget:
                        profile_data[key] = ",".join(widget)
                else:
                    val = widget.get().strip()
                    if val:
                        profile_data[key] = val

            if user_id != "guest":
                save_driver_profile(user_id, profile_data)

            # Update badge initials in place
            overlay.destroy()
            if self._badge_btn is not None:
                new_initials = (new_first[:1] + new_last[:1]).upper()
                try:
                    self._badge_btn.configure(text=new_initials)
                except Exception:
                    pass

        btn_row2 = ctk.CTkFrame(inner, fg_color="transparent")
        btn_row2.pack(pady=(0, 8))

        ctk.CTkButton(btn_row2, text="SAVE CHANGES",
                      command=save_changes,
                      font=ctk.CTkFont(family="Inter", size=12, weight="bold"),
                      fg_color=AMBER, hover_color=AMBER2,
                      text_color="#000", width=200, height=40, corner_radius=6).pack(side="left", padx=(0, 8))

        ctk.CTkButton(btn_row2, text="CLOSE",
                      command=overlay.destroy,
                      font=ctk.CTkFont(family="Inter", size=12, weight="bold"),
                      fg_color=BORDER, hover_color=BORDER2,
                      text_color=TEXT, width=140, height=40, corner_radius=6).pack(side="left")

    # =========================================================================
    # Camera management
    # =========================================================================

    def _start_camera(self):
        if self._cam_active:
            return
        self._cap = cv2.VideoCapture(0, cv2.CAP_AVFOUNDATION)
        self._face_mesh = mp.solutions.face_mesh.FaceMesh(
            max_num_faces=1, refine_landmarks=True,
            min_detection_confidence=0.5, min_tracking_confidence=0.5
        )
        self._cam_active = True

    def _stop_camera(self):
        self._cam_active = False
        if self._cap:
            self._cap.release()
            self._cap = None
        if self._face_mesh:
            self._face_mesh.close()
            self._face_mesh = None

    def _on_close(self):
        self._dashboard_active = False
        self._welcome_playing  = False
        if self._welcome_cap:
            self._welcome_cap.release()
        self._stop_camera()
        self.destroy()