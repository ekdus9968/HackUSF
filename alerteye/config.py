"""
config.py — Single source of truth for all AlertEye settings.
All modules must import from here. Never hardcode values elsewhere.
"""

import os

# ---------------------------------------------------------------------------
# EAR Detection Thresholds
# ---------------------------------------------------------------------------

EAR_THRESHOLD = 0.25        # Eye considered closed if EAR drops below this

SENSITIVITY_LEVELS = {
    "Low":    0.20,
    "Medium": 0.25,
    "High":   0.30,
}

# ---------------------------------------------------------------------------
# Alert Timing (seconds of continuous eye closure)
# ---------------------------------------------------------------------------

STAGE1_SECONDS = 3          # Short beep warning
STAGE2_SECONDS = 5          # Loud continuous alarm
SMS_SECONDS    = 8          # Automatic emergency SMS

SMS_COOLDOWN   = 60         # Minimum seconds between consecutive SMS sends

# ---------------------------------------------------------------------------
# Camera
# ---------------------------------------------------------------------------

CAMERA_INDEX  = 0           # Default webcam
FRAME_WIDTH   = 640
FRAME_HEIGHT  = 480

# ---------------------------------------------------------------------------
# MediaPipe landmark indices for left and right eyes
# (from MediaPipe Face Mesh 468-point model)
# ---------------------------------------------------------------------------

# [p1, p2, p3, p4, p5, p6] — top-bottom-top-bottom-left-right order
LEFT_EYE_IDX  = [362, 385, 387, 263, 373, 380]
RIGHT_EYE_IDX = [33,  160, 158, 133, 153, 144]

# ---------------------------------------------------------------------------
# Emergency Contact (overwritten at runtime by UI input)
# ---------------------------------------------------------------------------

EMERGENCY_CONTACT = ""      # E.164 format, e.g. "+821012345678"

# ---------------------------------------------------------------------------
# Twilio Credentials (load from environment — never hardcode)
# ---------------------------------------------------------------------------

TWILIO_SID   = os.environ.get("TWILIO_SID",   "")
TWILIO_TOKEN = os.environ.get("TWILIO_TOKEN",  "")
TWILIO_FROM  = os.environ.get("TWILIO_FROM",   "")  # Your Twilio number

# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

WINDOW_TITLE  = "AlertEye"
WINDOW_WIDTH  = 860
WINDOW_HEIGHT = 520

VIDEO_WIDTH   = 560         # Webcam panel width inside window
VIDEO_HEIGHT  = 420         # Webcam panel height inside window

STATUS_COLORS = {
    "NORMAL": "#2ecc71",    # green
    "STAGE1": "#f39c12",    # amber
    "STAGE2": "#e74c3c",    # red
    "SMS":    "#8e44ad",    # purple
}

# ---------------------------------------------------------------------------
# Audio Assets (relative to project root)
# ---------------------------------------------------------------------------

SOUND_STAGE1 = "assets/beep.wav"       # Short warning beep
SOUND_STAGE2 = "assets/alarm.wav"      # Loud continuous alarm
