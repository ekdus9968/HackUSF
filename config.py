# =============================================================================
# config.py — shared state dictionary
# =============================================================================
# Every module imports this and reads/writes to it.
# This is the single source of truth for the app's live data.
#
# Who writes what:
#   detection.py  → ear, alert_stage, frame
#   ui.py         → alarm_silenced
# =============================================================================

state = {
    "ear":             0.0,    # current Eye Aspect Ratio (float)
    "alert_stage":     0,      # 0=ok, 1=warning, 2=danger, 3=critical
    "alarm_silenced":  False,  # True when stop button pressed
    "yawn_count":      0,      # total yawns this session
    "session_active":  True,   # whether session is running
    "frame":           None,   # latest processed frame from detection.py
}