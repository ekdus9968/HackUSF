# =============================================================================
# calibration.py — Noctua personal calibration
# =============================================================================
# Replaces cv2 imshow windows with a full Tkinter screen.
# Live camera feed shown in canvas. 3 steps in sequence with progress bar.
# Returns (ear_threshold, pitch_baseline) same as original.
# =============================================================================

import cv2
import numpy as np
import customtkinter as ctk
from PIL import Image, ImageTk
import threading
import time

from constants import LEFT_EYE, RIGHT_EYE, calculate_EAR, calculate_pitch

# ── Theme ─────────────────────────────────────────────────────────────────────
BG     = "#080C12"
PANEL  = "#0D1219"
BORDER = "#1A2332"
AMBER  = "#F5A623"
GREEN  = "#00E87A"
RED    = "#FF3A3A"
CYAN   = "#00C8E8"
TEXT   = "#C8D8E8"
TEXT2  = "#607080"
CARD   = "#0F1520"

# ── Step definitions ──────────────────────────────────────────────────────────
STEPS = [
    {
        "title":       "OPEN EYES",
        "instruction": "Look straight at the camera with your eyes fully open.",
        "sub":         "Hold still — we're measuring your natural eye openness.",
        "color":       GREEN,
        "samples":     60,
    },
    {
        "title":       "CLOSE EYES",
        "instruction": "Now slowly close your eyes completely.",
        "sub":         "Keep your head still — this sets your closed-eye baseline.",
        "color":       AMBER,
        "samples":     60,
    },
    {
        "title":       "LOOK STRAIGHT",
        "instruction": "Open your eyes and look straight ahead naturally.",
        "sub":         "This calibrates your head pose — no need to tilt.",
        "color":       CYAN,
        "samples":     60,
    },
]


class CalibrationWindow(ctk.CTk):
    """
    Full-screen calibration window.
    Shows live camera feed + step-by-step instructions.
    Stores results in self.ear_threshold and self.pitch_baseline.
    """

    def __init__(self, face_mesh, cap):
        super().__init__()
        self.title("Noctua — Calibration")
        self.configure(fg_color=BG)
        self.resizable(True, True)
        self.after(100, lambda: self.state("zoomed"))

        self.face_mesh  = face_mesh
        self.cap        = cap
        self.done       = False

        # Results
        self.ear_threshold  = 0.25
        self.pitch_baseline = 0.0

        # State
        self._step        = 0        # 0, 1, 2
        self._collecting  = False
        self._samples     = []
        self._status_text = ""
        self._ready       = False    # True after face detected

        self._build_ui()
        self._update_camera()        # start 33ms camera loop

    # =========================================================================
    # UI
    # =========================================================================

    def _build_ui(self):
        # ── Title bar ──────────────────────────────────────────────────────────
        bar = ctk.CTkFrame(self, fg_color=PANEL, height=40, corner_radius=0,
                           border_width=1, border_color=BORDER)
        bar.pack(fill="x", side="top")
        bar.pack_propagate(False)

        ctk.CTkLabel(bar, text="Noctua",
                     font=ctk.CTkFont(family="Courier", size=13, weight="bold"),
                     text_color=AMBER).pack(side="left", padx=16)

        ctk.CTkLabel(bar, text="PERSONAL CALIBRATION",
                     font=ctk.CTkFont(family="Courier", size=11),
                     text_color=TEXT2).pack(side="left", padx=8)

        # ── Progress bar (3 dots) ──────────────────────────────────────────────
        prog_frame = ctk.CTkFrame(self, fg_color=BG, height=48)
        prog_frame.pack(fill="x", padx=60, pady=(16, 0))

        self._step_dots = []
        self._step_labels = []
        dot_row = ctk.CTkFrame(prog_frame, fg_color="transparent")
        dot_row.pack(anchor="center")

        for i, step in enumerate(STEPS):
            col = ctk.CTkFrame(dot_row, fg_color="transparent")
            col.pack(side="left", padx=24)

            dot = ctk.CTkLabel(col, text="●",
                               font=ctk.CTkFont(family="Courier", size=18),
                               text_color=BORDER)
            dot.pack()
            self._step_dots.append(dot)

            lbl = ctk.CTkLabel(col, text=step["title"],
                               font=ctk.CTkFont(family="Courier", size=9),
                               text_color=TEXT2)
            lbl.pack()
            self._step_labels.append(lbl)

        # ── Main body ──────────────────────────────────────────────────────────
        body = ctk.CTkFrame(self, fg_color=BG)
        body.pack(fill="both", expand=True, padx=60, pady=16)

        # Left — camera feed
        cam_frame = ctk.CTkFrame(body, fg_color=CARD, corner_radius=12,
                                 border_width=1, border_color=BORDER)
        cam_frame.pack(side="left", fill="both", expand=True, padx=(0, 16))

        self.canvas = ctk.CTkCanvas(cam_frame, bg="#000000",
                                    highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, padx=2, pady=2)

        # Right — instructions panel
        right = ctk.CTkFrame(body, fg_color=CARD, corner_radius=12,
                             border_width=1, border_color=BORDER,
                             width=340)
        right.pack(side="right", fill="y")
        right.pack_propagate(False)

        inner = ctk.CTkFrame(right, fg_color="transparent")
        inner.place(relx=0.5, rely=0.4, anchor="center")

        # Step number
        self._step_num_lbl = ctk.CTkLabel(
            inner, text="STEP 1 OF 3",
            font=ctk.CTkFont(family="Courier", size=10),
            text_color=TEXT2)
        self._step_num_lbl.pack(pady=(0, 8))

        # Big icon
        self._icon_lbl = ctk.CTkLabel(
            inner, text="👁",
            font=ctk.CTkFont(size=56))
        self._icon_lbl.pack(pady=(0, 12))

        # Step title
        self._title_lbl = ctk.CTkLabel(
            inner, text="",
            font=ctk.CTkFont(family="Courier", size=20, weight="bold"),
            text_color=GREEN)
        self._title_lbl.pack(pady=(0, 8))

        # Instruction
        self._instr_lbl = ctk.CTkLabel(
            inner, text="",
            font=ctk.CTkFont(family="Courier", size=12),
            text_color=TEXT,
            wraplength=280, justify="center")
        self._instr_lbl.pack(pady=(0, 6))

        # Sub instruction
        self._sub_lbl = ctk.CTkLabel(
            inner, text="",
            font=ctk.CTkFont(family="Courier", size=10),
            text_color=TEXT2,
            wraplength=280, justify="center")
        self._sub_lbl.pack(pady=(0, 24))

        # Progress bar (sample collection)
        self._prog_bar = ctk.CTkProgressBar(inner, width=280,
                                            fg_color=PANEL,
                                            progress_color=AMBER)
        self._prog_bar.set(0)
        self._prog_bar.pack(pady=(0, 12))

        # Status text
        self._status_lbl = ctk.CTkLabel(
            inner, text="Position your face in the camera",
            font=ctk.CTkFont(family="Courier", size=10),
            text_color=TEXT2)
        self._status_lbl.pack(pady=(0, 20))

        # Action button
        self._btn = ctk.CTkButton(
            inner, text="START COLLECTING",
            command=self._on_btn,
            font=ctk.CTkFont(family="Courier", size=12, weight="bold"),
            fg_color=AMBER, hover_color="#E8920D",
            text_color="#000000",
            width=280, height=44, corner_radius=6)
        self._btn.pack()

        self._update_step_ui()

    # =========================================================================
    # Step UI updates
    # =========================================================================

    def _update_step_ui(self):
        step = STEPS[self._step]
        icons = ["👁", "😑", "⬆"]

        # Progress dots
        for i, (dot, lbl) in enumerate(zip(self._step_dots, self._step_labels)):
            if i < self._step:
                dot.configure(text_color=GREEN)
                lbl.configure(text_color=GREEN)
            elif i == self._step:
                dot.configure(text_color=step["color"])
                lbl.configure(text_color=step["color"])
            else:
                dot.configure(text_color=BORDER)
                lbl.configure(text_color=TEXT2)

        self._step_num_lbl.configure(text=f"STEP {self._step + 1} OF 3")
        self._icon_lbl.configure(text=icons[self._step])
        self._title_lbl.configure(text=step["title"],
                                  text_color=step["color"])
        self._instr_lbl.configure(text=step["instruction"])
        self._sub_lbl.configure(text=step["sub"])
        self._prog_bar.set(0)
        self._prog_bar.configure(progress_color=step["color"])
        self._status_lbl.configure(text="Position your face in the camera",
                                   text_color=TEXT2)
        self._btn.configure(text="START COLLECTING",
                            state="normal",
                            fg_color=AMBER)
        self._collecting = False
        self._samples    = []

    # =========================================================================
    # Button handler
    # =========================================================================

    def _on_btn(self):
        if not self._collecting:
            self._collecting = True
            self._btn.configure(text="COLLECTING...", state="disabled",
                                fg_color=BORDER)
            self._status_lbl.configure(text="Hold still...",
                                       text_color=STEPS[self._step]["color"])

    # =========================================================================
    # Camera loop
    # =========================================================================

    def _update_camera(self):
        ret, frame = self.cap.read()
        if ret and frame is not None:
            frame = cv2.flip(frame, 1)
            h, w  = frame.shape[:2]
            rgb   = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            results = self.face_mesh.process(rgb)
            face_detected = False

            if results.multi_face_landmarks:
                face_detected = True

                for face_landmarks in results.multi_face_landmarks:

                    def get_point(idx):
                        lm = face_landmarks.landmark[idx]
                        return (lm.x * w, lm.y * h)

                    left_pts  = [get_point(i) for i in LEFT_EYE]
                    right_pts = [get_point(i) for i in RIGHT_EYE]
                    avg_EAR   = (calculate_EAR(left_pts) + calculate_EAR(right_pts)) / 2.0
                    pitch     = calculate_pitch(face_landmarks, w, h)

                    # Draw eye landmarks
                    step_color_bgr = self._hex_to_bgr(STEPS[self._step]["color"])
                    for pt in left_pts + right_pts:
                        cv2.circle(frame, (int(pt[0]), int(pt[1])), 2,
                                   step_color_bgr, -1)
                    pts_l = np.array([(int(p[0]), int(p[1])) for p in left_pts],  np.int32)
                    pts_r = np.array([(int(p[0]), int(p[1])) for p in right_pts], np.int32)
                    cv2.polylines(frame, [pts_l], isClosed=True,
                                  color=step_color_bgr, thickness=1)
                    cv2.polylines(frame, [pts_r], isClosed=True,
                                  color=step_color_bgr, thickness=1)

                    # Collect samples
                    if self._collecting:
                        if self._step == 0:
                            self._samples.append(avg_EAR)
                        elif self._step == 1:
                            self._samples.append(avg_EAR)
                        elif self._step == 2 and pitch is not None:
                            self._samples.append(pitch)

                        target = STEPS[self._step]["samples"]
                        count  = len(self._samples)
                        self._prog_bar.set(count / target)

                        if count >= target:
                            self._finish_step()

            # Face detection hint
            if not face_detected and self._btn.cget("state") == "normal":
                self._status_lbl.configure(
                    text="No face detected — move closer",
                    text_color=RED)
            elif face_detected and not self._collecting:
                self._status_lbl.configure(
                    text="Face detected ✓ — press START when ready",
                    text_color=GREEN)

            # Draw to canvas
            cw = self.canvas.winfo_width()
            ch = self.canvas.winfo_height()
            if cw > 1 and ch > 1:
                frame = cv2.resize(frame, (cw, ch))
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(frame_rgb)
            self._photo = ImageTk.PhotoImage(image=img)
            self.canvas.delete("all")
            self.canvas.create_image(0, 0, anchor="nw", image=self._photo)

        if not self.done:
            self.after(33, self._update_camera)

    # =========================================================================
    # Step completion
    # =========================================================================

    def _finish_step(self):
        self._collecting = False
        samples = self._samples[:]

        step = STEPS[self._step]
        self._status_lbl.configure(text=f"✓ {step['title']} captured!",
                                   text_color=GREEN)
        self._prog_bar.set(1)

        if self._step == 0:
            self._open_avg = float(np.mean(samples))
        elif self._step == 1:
            self._closed_avg = float(np.mean(samples))
            self.ear_threshold = (self._open_avg + self._closed_avg) / 2.0
            print(f"[Calibration] EAR — Open: {self._open_avg:.3f}, "
                  f"Closed: {self._closed_avg:.3f}, "
                  f"Threshold: {self.ear_threshold:.3f}")
        elif self._step == 2:
            self.pitch_baseline = float(np.mean(samples))
            print(f"[Calibration] Pitch baseline: {self.pitch_baseline:.2f}°")

        if self._step < 2:
            self._step += 1
            self.after(800, self._update_step_ui)
        else:
            self._finish_all()

    def _finish_all(self):
        self.done = True
        self._btn.configure(text="CALIBRATION COMPLETE ✓",
                            fg_color=GREEN, text_color="#000",
                            state="disabled")
        self._title_lbl.configure(text="ALL DONE!", text_color=GREEN)
        self._instr_lbl.configure(
            text="Your personal profile has been saved.")
        self._sub_lbl.configure(text="Starting Noctua...")

        # All dots green
        for dot, lbl in zip(self._step_dots, self._step_labels):
            dot.configure(text_color=GREEN)
            lbl.configure(text_color=GREEN)

        self.after(1500, self.destroy)

    # =========================================================================
    # Utility
    # =========================================================================

    @staticmethod
    def _hex_to_bgr(hex_color):
        h = hex_color.lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return (b, g, r)


# =============================================================================
# Public entry point — drop-in replacement for original calibrate()
# =============================================================================

def calibrate(face_mesh, cap):
    """
    Shows Tkinter calibration window.
    Returns (ear_threshold, pitch_baseline) — same as original.
    Must be called from the main thread before Tkinter UI starts,
    or from within an existing Tkinter context as a Toplevel.
    """
    win = CalibrationWindow(face_mesh, cap)
    win.mainloop()
    return win.ear_threshold, win.pitch_baseline