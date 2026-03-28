# Dependencies:
#   - customtkinter  : modern dark-themed Tkinter wrapper
#   - opencv-python  : webcam frame capture
#   - Pillow         : converts OpenCV frames to Tkinter-compatible images
#   - config.py      : shared state dict read/written by all modules

import customtkinter as ctk
import cv2
from PIL import Image, ImageTk

from config import state

# Theme & color constants
# Cockpit instrument panel aesthetic — dark bg, amber accents, status colors.
# All colors defined here so they're easy to tweak in one place.
 
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")
 
BG     = "#080C12"   # main window background
PANEL  = "#0D1219"   # sidebar / panel background
BORDER = "#1A2332"   # subtle border color
AMBER  = "#F5A623"   # primary accent — EAR value, headings
RED    = "#FF3A3A"   # danger — Stage 2 alert, stop button
GREEN  = "#00E87A"   # safe — monitoring state, good EAR
TEXT   = "#C8D8E8"   # primary text
TEXT2  = "#607080"   # secondary / muted text

# main application class

class AlertEyeApp(ctk.CTk):
    """
    Main window class. Inherits from ctk.CTk (customtkinter's root window).
    Builds the full UI layout and runs a 33ms update loop for the webcam feed.
    """
 
    def __init__(self):
        super().__init__()
 
        # Window configuration 
        self.title("AlertEye — Driver Monitoring System")
        self.geometry("860x520")       # width x height in pixels
        self.resizable(False, False)   # lock size so layout doesn't break
        self.configure(fg_color=BG)    # set background to cockpit dark color
 
        # Camera initialization 
        # Index 1 for built-in MacBook webcam.
        self.cap = cv2.VideoCapture(1)
 
        # Build UI then start the update loop
        self._build_ui()
        self._update()    # starts the 33ms webcam + state refresh loop
 
 # UI Layout
 
    def _build_ui(self):
        """
        Constructs the full window layout:
          - Title bar across the top
          - Left panel (EAR value, alert stage, thresholds, stop button)
          - Center area (live webcam canvas + alert overlay text)
        """
        self._build_title_bar()
        self._build_body()
 
    def _build_title_bar(self):
        """
        Thin bar across the top of the window showing:
          - App name (left)
          - Session label (center)
          - Live status indicator (right) — updates with alert state
        """
        title_bar = ctk.CTkFrame(self, fg_color=PANEL, height=36, corner_radius=0)
        title_bar.pack(fill="x", side="top")
        title_bar.pack_propagate(False)   # prevent frame from shrinking to fit children
 
        # App name
        ctk.CTkLabel(
            title_bar,
            text="AlertEye",
            font=ctk.CTkFont(family="Courier", size=14, weight="bold"),
            text_color=AMBER
        ).pack(side="left", padx=16)
 
        # Session subtitle
        ctk.CTkLabel(
            title_bar,
            text="DRIVER MONITORING SYSTEM · ACTIVE SESSION",
            font=ctk.CTkFont(size=11),
            text_color=TEXT2
        ).pack(side="left", padx=8)
 
        # Status indicator — updated every frame in _sync_state()
        self.status_label = ctk.CTkLabel(
            title_bar,
            text="● MONITORING",
            font=ctk.CTkFont(family="Courier", size=11),
            text_color=GREEN
        )
        self.status_label.pack(side="right", padx=16)
 
    def _build_body(self):
        """
        Main content area below the title bar.
        Two columns: left info panel + center webcam feed.
        """
        body = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        body.pack(fill="both", expand=True)
 
        # Left stats panel (fixed width)
        left = ctk.CTkFrame(
            body,
            fg_color=PANEL,
            width=220,
            corner_radius=0,
            border_width=1,
            border_color=BORDER
        )
        left.pack(side="left", fill="y")
        left.pack_propagate(False)   # keep fixed width regardless of content
        self._build_left_panel(left)
 
        # Center webcam area (fills remaining width)
        center = ctk.CTkFrame(body, fg_color="#000000", corner_radius=0)
        center.pack(side="left", fill="both", expand=True)
        self._build_center(center)
 
    def _build_left_panel(self, parent):
        """
        Left sidebar content:
          - Large EAR number (changes color based on threshold)
          - Current alert stage
          - Threshold reference (Stage 1 / Stage 2 / SMS)
          - Stop Alarm button pinned to the bottom
        """
        pad = {"padx": 16, "pady": (12, 4)}
 
        # EAR value display
        ctk.CTkLabel(
            parent, text="EAR VALUE",
            font=ctk.CTkFont(family="Courier", size=9),
            text_color=TEXT2
        ).pack(anchor="w", **pad)
 
        # Large number — color changes green → amber → red as eyes close
        self.ear_label = ctk.CTkLabel(
            parent,
            text="0.00",
            font=ctk.CTkFont(family="Courier", size=40, weight="bold"),
            text_color=AMBER
        )
        self.ear_label.pack(anchor="w", padx=16, pady=(0, 8))
 
        # Visual divider
        ctk.CTkFrame(parent, fg_color=BORDER, height=1, corner_radius=0).pack(
            fill="x", padx=16, pady=4)
 
        # Alert stage display
        ctk.CTkLabel(
            parent, text="ALERT STAGE",
            font=ctk.CTkFont(family="Courier", size=9),
            text_color=TEXT2
        ).pack(anchor="w", **pad)
 
        # Stage label — updated by _sync_state() based on state["alert_stage"]
        self.stage_label = ctk.CTkLabel(
            parent,
            text="STAGE 0",
            font=ctk.CTkFont(family="Courier", size=18, weight="bold"),
            text_color=GREEN
        )
        self.stage_label.pack(anchor="w", padx=16, pady=(0, 8))
 
        # Visual divider
        ctk.CTkFrame(parent, fg_color=BORDER, height=1, corner_radius=0).pack(
            fill="x", padx=16, pady=4)
 
        # Threshold reference rows
        # Static info labels so the driver knows what each stage triggers.
        # Actual threshold logic lives in core.py.
        for stage, description, color in [
            ("Stage 1", "3s — audio alarm",  AMBER),
            ("Stage 2", "5s — loud alarm",   "#FF8C00"),
            ("SMS",     "8s — Twilio send",  RED),
        ]:
            row = ctk.CTkFrame(parent, fg_color="transparent", corner_radius=0)
            row.pack(fill="x", padx=16, pady=2)
 
            ctk.CTkLabel(
                row, text=stage,
                font=ctk.CTkFont(family="Courier", size=11, weight="bold"),
                text_color=color, width=60, anchor="w"
            ).pack(side="left")
 
            ctk.CTkLabel(
                row, text=description,
                font=ctk.CTkFont(size=10),
                text_color=TEXT2
            ).pack(side="left", padx=4)
 
        # Spacer — pushes stop button to the bottom of the panel
        ctk.CTkFrame(parent, fg_color="transparent").pack(fill="y", expand=True)
 
        # ── Stop Alarm button ─────────────────────────────────────────────────
        # Pinned to bottom. On click calls _stop_alarm() which writes back
        # to state so alert.py knows to silence the sound.
        ctk.CTkFrame(parent, fg_color=BORDER, height=1, corner_radius=0).pack(
            fill="x", padx=0, pady=0)
 
        self.stop_btn = ctk.CTkButton(
            parent,
            text="STOP ALARM",
            font=ctk.CTkFont(family="Courier", size=13, weight="bold"),
            fg_color=RED,
            hover_color="#CC2222",
            text_color="#FFFFFF",
            corner_radius=0,
            height=48,
            command=self._stop_alarm
        )
        self.stop_btn.pack(fill="x", side="bottom")
 
    def _build_center(self, parent):
        """
        Center webcam area:
          - Canvas where each OpenCV frame is drawn every 33ms
          - Alert overlay label that floats on top when fatigue detected
        """
        # Canvas fills the entire center column
        self.canvas = ctk.CTkCanvas(
            parent,
            bg="#000000",
            highlightthickness=0   # removes default white Tkinter border
        )
        self.canvas.pack(fill="both", expand=True)
 
        # Overlay warning text — empty normally, shown on Stage 2+ alert
        self.alert_overlay = ctk.CTkLabel(
            parent,
            text="",
            font=ctk.CTkFont(family="Courier", size=16, weight="bold"),
            text_color=RED,
            fg_color="transparent"
        )
        self.alert_overlay.place(relx=0.5, rely=0.05, anchor="n")

# Update loop — runs every 33ms (~30fps)
 
    def _update(self):
        """
        Main application loop. Schedules itself every 33ms using after().
        Each tick: grab webcam frame + sync UI to latest state values.
        """
        self._read_webcam()
        self._sync_state()
        self.after(33, self._update)   # reschedule — this is what keeps it looping
 
    def _read_webcam(self):
        """
        Captures one frame from the webcam and draws it onto the canvas.
 
        Frame conversion pipeline:
          cv2.VideoCapture → numpy BGR array
            → flip horizontal (mirror effect for driver-facing camera)
            → resize to canvas dimensions
            → BGR to RGB conversion (OpenCV and PIL use different channel order)
            → PIL Image
            → ImageTk.PhotoImage
            → canvas.create_image()
 
        Note: self._photo must be stored as an instance variable (self._photo).
        If stored as a local variable, Python garbage collects it before
        Tkinter finishes rendering, resulting in a blank canvas.
        """
        ret, frame = self.cap.read()
 
        if not ret:
            return   # no frame available, skip tick
 
        # Mirror horizontally — feels more natural for a driver-facing camera
        frame = cv2.flip(frame, 1)
 
        # Resize to match canvas — guard against canvas not yet drawn (size = 1)
        canvas_w = self.canvas.winfo_width()
        canvas_h = self.canvas.winfo_height()
        if canvas_w > 1 and canvas_h > 1:
            frame = cv2.resize(frame, (canvas_w, canvas_h))
 
        # Convert BGR (OpenCV default) → RGB (PIL requirement)
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
 
        # Build Tkinter-compatible image and keep reference on self
        img = Image.fromarray(frame_rgb)
        self._photo = ImageTk.PhotoImage(image=img)   # ← must stay on self!
 
        # Draw to canvas
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self._photo)
 
    def _sync_state(self):
        """
        Reads shared state dict and updates all UI labels to reflect
        the latest detection values from core.py and detector.py.
 
        Reads from state:
          "ear"          → float, set by core.py each frame
          "alert_stage"  → int 0-3, set by core.py based on PERCLOS
          "yawn_count"   → int, set by detector.py (used in future panels)
        """
        ear   = state.get("ear", 0.0)
        stage = state.get("alert_stage", 0)
 
        # EAR display
        self.ear_label.configure(text=f"{ear:.2f}")
 
        # Color encodes urgency — green is safe, red is critical
        if ear < 0.20:
            self.ear_label.configure(text_color=RED)
        elif ear < 0.25:
            self.ear_label.configure(text_color=AMBER)
        else:
            self.ear_label.configure(text_color=GREEN)
 
        # ── Stage display ─────────────────────────────────────────────────────
        stage_colors = {0: GREEN, 1: AMBER, 2: "#FF8C00", 3: RED}
        stage_texts  = {0: "STAGE 0", 1: "STAGE 1", 2: "STAGE 2", 3: "SMS SENT"}
 
        self.stage_label.configure(
            text=stage_texts.get(stage, "STAGE 0"),
            text_color=stage_colors.get(stage, GREEN)
        )
 
        # Status bar + video overlay
        if stage >= 2:
            self.status_label.configure(text="⚠ FATIGUE DETECTED", text_color=RED)
            self.alert_overlay.configure(text="⚠  DROWSINESS DETECTED — PULL OVER")
        elif stage == 1:
            self.status_label.configure(text="● STAGE 1 WARNING", text_color=AMBER)
            self.alert_overlay.configure(text="")
        else:
            self.status_label.configure(text="● MONITORING", text_color=GREEN)
            self.alert_overlay.configure(text="")
 
    # Button handlers
 
    def _stop_alarm(self):
        """
        Handles STOP ALARM button press.
 
        Writes to shared state:
          "alarm_silenced" → True  : alert.py watches this to kill audio
          "alert_stage"    → 0     : resets detection stage to normal
 
        Then resets all UI elements back to safe/monitoring state.
        """
        state["alarm_silenced"] = True
        state["alert_stage"]    = 0
 
        self.status_label.configure(text="● SILENCED", text_color=TEXT2)
        self.stage_label.configure(text="STAGE 0", text_color=GREEN)
        self.alert_overlay.configure(text="")
 
    # Cleanup
 
    def on_close(self):
        """
        Called when the window close button is pressed.
        Always release the webcam before destroying the window —
        otherwise the camera stays locked at the OS level.
        """
        self.cap.release()
        self.destroy()
 
# Entry point
 
if __name__ == "__main__":
    app = AlertEyeApp()
    app.protocol("WM_DELETE_WINDOW", app.on_close)   # wire close button to cleanup
    app.mainloop()