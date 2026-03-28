"""
ui.py — Tkinter UI for AlertEye.
Agent 2: builds and manages the full application window.

Exposes:
    launch_app() -> None
"""

import tkinter as tk
from tkinter import ttk, messagebox
import time
import threading
import numpy as np

import config

# ---------------------------------------------------------------------------
# Graceful imports — stubs used if partner modules aren't ready yet
# ---------------------------------------------------------------------------

try:
    from core import get_frame_with_overlay, get_drowsiness_state, start_detection, stop_detection
    _CORE_READY = True
except Exception:
    _CORE_READY = False

    def get_frame_with_overlay() -> np.ndarray:
        """Placeholder: returns a dark blank frame."""
        return np.zeros((config.VIDEO_HEIGHT, config.VIDEO_WIDTH, 3), dtype=np.uint8)

    def get_drowsiness_state() -> dict:
        """Placeholder: returns default safe state."""
        return {
            "status": "NORMAL",
            "ear_value": 0.0,
            "closed_seconds": 0.0,
            "face_detected": False,
            "head_status": "straight",
            "yawn_count": 0,
        }

    def start_detection() -> None:
        """Placeholder: no-op."""
        pass

    def stop_detection() -> None:
        """Placeholder: no-op."""
        pass


try:
    from alert import stop_alarm, trigger_alert
    _ALERT_READY = True
except Exception:
    _ALERT_READY = False

    def stop_alarm() -> None:
        """Placeholder: silences alarm."""
        pass

    def trigger_alert(stage: str) -> None:
        """Placeholder: triggers alert."""
        pass


try:
    from calibration import run_calibration
    _CALIB_READY = True
except Exception:
    _CALIB_READY = False

    def run_calibration(duration_seconds: int = 5) -> float:
        """Placeholder: returns current threshold as baseline."""
        return config.EAR_THRESHOLD


# ---------------------------------------------------------------------------
# Pillow import — required for converting OpenCV frames to Tkinter images
# ---------------------------------------------------------------------------

try:
    from PIL import Image, ImageTk
    _PIL_READY = True
except ImportError:
    _PIL_READY = False


class AlertEyeApp:
    """Main Tkinter application window for AlertEye drowsiness detection."""

    SENSITIVITY_OPTIONS = ["Low", "Medium", "High"]
    VIDEO_INTERVAL_MS   = 30    # webcam canvas refresh rate
    TIMER_INTERVAL_MS   = 1000  # drive-timer refresh rate

    def __init__(self, root: tk.Tk) -> None:
        """Initialise all state and build the UI."""
        self.root = root
        self.root.title(config.WINDOW_TITLE)
        self.root.geometry(f"{config.WINDOW_WIDTH}x{config.WINDOW_HEIGHT}")
        self.root.resizable(False, False)
        self.root.configure(bg="#1a1a2e")

        # Runtime state
        self._running      = False
        self._alert_count  = 0
        self._yawn_count   = 0
        self._drive_start: float | None = None
        self._last_status  = "NORMAL"
        self._image_ref    = None   # keep PhotoImage alive to prevent GC

        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        """Construct all panels.

        Bottom bar must be packed first so Tkinter reserves space for it
        before the LEFT-packed side panels consume the full window height.
        """
        self._build_bottom_bar()
        self._build_left_panel()
        self._build_right_panel()

    def _build_left_panel(self) -> None:
        """Left panel: live webcam canvas."""
        self.left_frame = tk.Frame(
            self.root,
            width=config.VIDEO_WIDTH,
            height=config.VIDEO_HEIGHT,
            bg="#0d0d1a",
        )
        self.left_frame.pack(side=tk.LEFT, padx=8, pady=8)
        self.left_frame.pack_propagate(False)

        self.canvas = tk.Canvas(
            self.left_frame,
            width=config.VIDEO_WIDTH,
            height=config.VIDEO_HEIGHT,
            bg="#0d0d1a",
            highlightthickness=0,
        )
        self.canvas.pack()
        self._draw_placeholder()

    def _build_right_panel(self) -> None:
        """Right panel: status readouts, sensitivity slider, emergency contact."""
        self.right_frame = tk.Frame(self.root, bg="#1a1a2e")
        self.right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8), pady=8)

        lbl = dict(bg="#1a1a2e", fg="#aaaacc", font=("Helvetica", 12))
        val = dict(bg="#1a1a2e", fg="#ffffff",  font=("Helvetica", 12, "bold"))

        row = 0

        # Status
        tk.Label(self.right_frame, text="Status", **lbl).grid(row=row, column=0, sticky="w", pady=(6, 2))
        self.lbl_status = tk.Label(
            self.right_frame,
            text="NORMAL",
            font=("Helvetica", 14, "bold"),
            bg="#1a1a2e",
            fg=config.STATUS_COLORS["NORMAL"],
        )
        self.lbl_status.grid(row=row, column=1, sticky="w", padx=10)
        row += 1

        # EAR
        tk.Label(self.right_frame, text="EAR", **lbl).grid(row=row, column=0, sticky="w", pady=2)
        self.lbl_ear = tk.Label(self.right_frame, text="—", **val)
        self.lbl_ear.grid(row=row, column=1, sticky="w", padx=10)
        row += 1

        # Head
        tk.Label(self.right_frame, text="Head", **lbl).grid(row=row, column=0, sticky="w", pady=2)
        self.lbl_head = tk.Label(self.right_frame, text="—", **val)
        self.lbl_head.grid(row=row, column=1, sticky="w", padx=10)
        row += 1

        # Yawns
        tk.Label(self.right_frame, text="Yawns", **lbl).grid(row=row, column=0, sticky="w", pady=2)
        self.lbl_yawns = tk.Label(self.right_frame, text="0", **val)
        self.lbl_yawns.grid(row=row, column=1, sticky="w", padx=10)
        row += 1

        # Alerts
        tk.Label(self.right_frame, text="Alerts", **lbl).grid(row=row, column=0, sticky="w", pady=2)
        self.lbl_alerts = tk.Label(self.right_frame, text="0", **val)
        self.lbl_alerts.grid(row=row, column=1, sticky="w", padx=10)
        row += 1

        # Drive timer
        tk.Label(self.right_frame, text="Drive", **lbl).grid(row=row, column=0, sticky="w", pady=2)
        self.lbl_timer = tk.Label(self.right_frame, text="00:00:00", **val)
        self.lbl_timer.grid(row=row, column=1, sticky="w", padx=10)
        row += 1

        # Divider
        ttk.Separator(self.right_frame, orient="horizontal").grid(
            row=row, column=0, columnspan=2, sticky="ew", pady=10
        )
        row += 1

        # Sensitivity radio buttons
        tk.Label(self.right_frame, text="Sensitivity", **lbl).grid(row=row, column=0, sticky="w", pady=2)
        self._sensitivity_var = tk.StringVar(value="Medium")
        sens_frame = tk.Frame(self.right_frame, bg="#1a1a2e")
        sens_frame.grid(row=row, column=1, sticky="w", padx=10)
        for opt in self.SENSITIVITY_OPTIONS:
            tk.Radiobutton(
                sens_frame,
                text=opt,
                variable=self._sensitivity_var,
                value=opt,
                command=self._on_sensitivity_change,
                bg="#1a1a2e",
                fg="#cccccc",
                selectcolor="#333355",
                activebackground="#1a1a2e",
                font=("Helvetica", 11),
            ).pack(side=tk.LEFT, padx=3)
        row += 1

        # Emergency contact
        tk.Label(self.right_frame, text="Emergency\nContact", **lbl).grid(
            row=row, column=0, sticky="w", pady=(12, 2)
        )
        self._contact_var = tk.StringVar(value=config.EMERGENCY_CONTACT)
        self.entry_contact = tk.Entry(
            self.right_frame,
            textvariable=self._contact_var,
            font=("Helvetica", 12),
            width=16,
            bg="#2a2a3e",
            fg="#ffffff",
            insertbackground="#ffffff",
            relief=tk.FLAT,
        )
        self.entry_contact.grid(row=row, column=1, sticky="w", padx=10, pady=(12, 2))
        self.entry_contact.bind("<FocusOut>", self._on_contact_change)
        self.entry_contact.bind("<Return>",   self._on_contact_change)

    def _build_bottom_bar(self) -> None:
        """Bottom bar: Start Monitoring, Calibrate, Stop Alarm."""
        bar = tk.Frame(self.root, bg="#0d0d1a", height=56)
        bar.pack(side=tk.BOTTOM, fill=tk.X)

        btn_cfg = dict(
            font=("Helvetica", 12, "bold"),
            relief=tk.FLAT,
            padx=16,
            pady=8,
            cursor="hand2",
            bd=0,
        )

        self.btn_start = tk.Button(
            bar,
            text="\u25b6  Start Monitoring",
            bg="#2ecc71",
            fg="#1a1a2e",
            command=self._on_start,
            **btn_cfg,
        )
        self.btn_start.pack(side=tk.LEFT, padx=10, pady=10)

        self.btn_calibrate = tk.Button(
            bar,
            text="\u2699  Calibrate",
            bg="#3498db",
            fg="#ffffff",
            command=self._on_calibrate,
            **btn_cfg,
        )
        self.btn_calibrate.pack(side=tk.LEFT, padx=10, pady=10)

        self.btn_stop = tk.Button(
            bar,
            text="\U0001f515  Stop Alarm",
            bg="#e74c3c",
            fg="#ffffff",
            command=self._on_stop_alarm,
            **btn_cfg,
        )
        self.btn_stop.pack(side=tk.LEFT, padx=10, pady=10)

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_start(self) -> None:
        """Toggle monitoring on/off."""
        if not self._running:
            self._running     = True
            self._drive_start = time.time()
            self._alert_count = 0
            self._yawn_count  = 0
            self._last_status = "NORMAL"
            self.btn_start.config(text="\u23f9  Stop Monitoring", bg="#e67e22", fg="#ffffff")
            try:
                start_detection()
            except Exception as exc:
                print(f"[UI] start_detection error: {exc}")
            self.canvas.delete("placeholder")
            self._loop_video()
            self._loop_timer()
        else:
            self._stop_monitoring()

    def _stop_monitoring(self) -> None:
        """Stop detection, silence alarm, reset display."""
        self._running = False
        try:
            stop_detection()
        except Exception as exc:
            print(f"[UI] stop_detection error: {exc}")
        try:
            stop_alarm()
        except Exception as exc:
            print(f"[UI] stop_alarm error: {exc}")
        self.btn_start.config(text="\u25b6  Start Monitoring", bg="#2ecc71", fg="#1a1a2e")
        self._update_status_label("NORMAL")
        self.lbl_ear.config(text="—")
        self.lbl_head.config(text="—")
        self._draw_placeholder()

    def _on_stop_alarm(self) -> None:
        """Immediately silence alarm — always responsive."""
        try:
            stop_alarm()
        except Exception as exc:
            print(f"[UI] stop_alarm error: {exc}")
        self._update_status_label("NORMAL")

    def _on_sensitivity_change(self) -> None:
        """Update config.EAR_THRESHOLD when sensitivity radio changes."""
        level = self._sensitivity_var.get()
        config.EAR_THRESHOLD = config.SENSITIVITY_LEVELS.get(level, 0.25)

    def _on_contact_change(self, _event=None) -> None:
        """Persist emergency contact number to config."""
        config.EMERGENCY_CONTACT = self._contact_var.get().strip()

    def _on_calibrate(self) -> None:
        """Run calibration in a background thread to keep UI responsive."""
        if self._running:
            messagebox.showinfo(
                "Calibrate",
                "Stop monitoring before calibrating.",
                parent=self.root,
            )
            return

        self.btn_calibrate.config(state=tk.DISABLED, text="Calibrating…")
        self.root.update_idletasks()

        def _worker() -> None:
            try:
                baseline = run_calibration(duration_seconds=5)
                config.EAR_THRESHOLD = baseline
                self.root.after(
                    0,
                    lambda: messagebox.showinfo(
                        "Calibration Complete",
                        f"Personal EAR baseline set to {baseline:.3f}",
                        parent=self.root,
                    ),
                )
            except Exception as exc:
                self.root.after(
                    0,
                    lambda: messagebox.showerror("Calibration Error", str(exc), parent=self.root),
                )
            finally:
                self.root.after(
                    0,
                    lambda: self.btn_calibrate.config(state=tk.NORMAL, text="\u2699  Calibrate"),
                )

        threading.Thread(target=_worker, daemon=True).start()

    # ------------------------------------------------------------------
    # Update loops
    # ------------------------------------------------------------------

    def _loop_video(self) -> None:
        """Refresh the webcam canvas every VIDEO_INTERVAL_MS ms."""
        if not self._running:
            return

        try:
            frame = get_frame_with_overlay()
            if frame is not None and frame.size > 0:
                self._render_frame(frame)
        except Exception as exc:
            print(f"[UI] frame error: {exc}")

        try:
            state = get_drowsiness_state()
            self._apply_state(state)
        except Exception as exc:
            print(f"[UI] state error: {exc}")

        self.root.after(self.VIDEO_INTERVAL_MS, self._loop_video)

    def _loop_timer(self) -> None:
        """Update the drive timer label every second."""
        if not self._running:
            return
        elapsed = int(time.time() - self._drive_start)
        h, rem = divmod(elapsed, 3600)
        m, s   = divmod(rem, 60)
        self.lbl_timer.config(text=f"{h:02d}:{m:02d}:{s:02d}")
        self.root.after(self.TIMER_INTERVAL_MS, self._loop_timer)

    # ------------------------------------------------------------------
    # Rendering helpers
    # ------------------------------------------------------------------

    def _render_frame(self, frame: np.ndarray) -> None:
        """Convert a BGR/RGB numpy frame and blit it to the canvas."""
        try:
            if _PIL_READY:
                import cv2 as _cv2
                img = Image.fromarray(_cv2.cvtColor(frame, _cv2.COLOR_BGR2RGB)).resize(
                    (config.VIDEO_WIDTH, config.VIDEO_HEIGHT), Image.LANCZOS
                )
                self._image_ref = ImageTk.PhotoImage(image=img)
                self.canvas.delete("all")
                self.canvas.create_image(0, 0, anchor=tk.NW, image=self._image_ref)
            else:
                # Pillow unavailable: show text fallback
                self.canvas.delete("all")
                self.canvas.create_text(
                    config.VIDEO_WIDTH // 2,
                    config.VIDEO_HEIGHT // 2,
                    text="Install Pillow for video feed\npip install Pillow",
                    fill="#ff6666",
                    font=("Helvetica", 13),
                    justify=tk.CENTER,
                )
        except Exception as exc:
            print(f"[UI] render error: {exc}")

    def _draw_placeholder(self) -> None:
        """Draw idle placeholder text on the canvas."""
        self.canvas.delete("all")
        self.canvas.create_text(
            config.VIDEO_WIDTH // 2,
            config.VIDEO_HEIGHT // 2,
            text="Press  \u25b6  Start  to begin",
            fill="#555577",
            font=("Helvetica", 16),
            tags="placeholder",
        )

    def _apply_state(self, state: dict) -> None:
        """Apply a drowsiness-state dict to right-panel labels and trigger alerts."""
        status      = state.get("status", "NORMAL")
        ear_value   = state.get("ear_value", 0.0)
        head_status = state.get("head_status", "straight")
        yawn_count  = state.get("yawn_count", 0)

        self._update_status_label(status)
        self.lbl_ear.config(text=f"{ear_value:.3f}")
        self.lbl_head.config(text=str(head_status))

        # Yawn counter (monotonically increasing from core)
        if yawn_count > self._yawn_count:
            self._yawn_count = yawn_count
        self.lbl_yawns.config(text=str(self._yawn_count))

        # Alert counter: increment on each NORMAL→alert edge
        if status != "NORMAL" and self._last_status == "NORMAL":
            self._alert_count += 1
        self.lbl_alerts.config(text=str(self._alert_count))

        # Trigger audio/SMS when status escalates
        if status in ("STAGE1", "STAGE2", "SMS") and status != self._last_status:
            try:
                trigger_alert(status)
            except Exception as exc:
                print(f"[UI] trigger_alert error: {exc}")

        self._last_status = status

    def _update_status_label(self, status: str) -> None:
        """Set status label text and colour."""
        color = config.STATUS_COLORS.get(status, "#ffffff")
        self.lbl_status.config(text=status, fg=color)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def launch_app() -> None:
    """Start the AlertEye Tkinter main loop."""
    root = tk.Tk()
    app  = AlertEyeApp(root)
    root.protocol("WM_DELETE_WINDOW", lambda: _on_close(root, app))
    root.mainloop()


def _on_close(root: tk.Tk, app: AlertEyeApp) -> None:
    """Clean up gracefully on window-close."""
    try:
        if app._running:
            app._stop_monitoring()
    except Exception:
        pass
    root.destroy()


# ---------------------------------------------------------------------------
# Standalone test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    launch_app()
