"""
main.py — Entry point for AlertEye.

Connects core (detection), ui (window), and alert (sound + SMS) modules.
Runs a background SMS-monitor thread that calls send_emergency_sms() whenever
the drowsiness state reaches "SMS" level — the only integration step that
ui.py delegates to the entry point.
"""

import threading
import time

# ---------------------------------------------------------------------------
# MediaPipe 0.10 compatibility shim
# mp.solutions was removed; patch it back from the legacy path before any
# module (core.py) tries to access it.
# ---------------------------------------------------------------------------
import mediapipe as _mp
if not hasattr(_mp, "solutions"):
    import mediapipe.python.solutions as _solutions_pkg
    _mp.solutions = _solutions_pkg

import config
import core
import alert
from ui import launch_app


# ---------------------------------------------------------------------------
# SMS monitor thread
# ---------------------------------------------------------------------------

def _sms_monitor_loop() -> None:
    """Poll drowsiness state every second; fire SMS when status == 'SMS'.

    Uses alert.SMS_COOLDOWN (via alert internals) to avoid spam.
    Only runs when detection is active (core._running).
    """
    while True:
        try:
            if core._running:
                state = core.get_drowsiness_state()
                if state.get("status") == "SMS":
                    alert.send_emergency_sms(
                        config.EMERGENCY_CONTACT,
                        state.get("closed_seconds", 0.0),
                    )
        except Exception as exc:
            print(f"[main] SMS monitor error: {exc}")
        time.sleep(1.0)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Start the AlertEye application.

    Launches the SMS monitor as a daemon thread, then hands control to the
    Tkinter UI.  Blocks until the window is closed.
    """
    sms_thread = threading.Thread(target=_sms_monitor_loop, daemon=True, name="sms-monitor")
    sms_thread.start()

    # launch_app() runs the Tkinter mainloop — returns only after window close.
    launch_app()


if __name__ == "__main__":
    main()
