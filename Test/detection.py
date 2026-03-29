# =============================================================================
# detection.py — AlertEye core detection module
# =============================================================================
# Refactored from a standalone script into a callable run() function so that
# ui.py can drive the loop and display frames on the Tkinter canvas instead
# of a separate cv2.imshow window.
#
# Flow:
#   1. main.py calls run()
#   2. run() does calibration, then starts the detection loop
#   3. Each frame: computes EAR + pitch, updates shared state dict
#   4. ui.py reads state every 33ms and updates the UI accordingly
# =============================================================================

import cv2
import mediapipe as mp
import numpy as np
from alert import speak
import time

from calibration import calibrate
from constants import *
from sound import play_beep, play_warning
from emergency import get_emergency_contact
from sms import send_critical_alert
from config import state   # shared state — bridge to ui.py

mp_face_mesh = mp.solutions.face_mesh
mp_drawing   = mp.solutions.drawing_utils

LEFT_EYE  = [362, 385, 387, 263, 373, 380]
RIGHT_EYE = [33, 160, 158, 133, 153, 144]

def calculate_EAR(eye_landmarks):
    A = np.linalg.norm(np.array(eye_landmarks[1]) - np.array(eye_landmarks[5]))
    B = np.linalg.norm(np.array(eye_landmarks[2]) - np.array(eye_landmarks[4]))
    C = np.linalg.norm(np.array(eye_landmarks[0]) - np.array(eye_landmarks[3]))
    return (A + B) / (2.0 * C)


def run():
    # ── Emergency contact setup ───────────────────────────────────────────────
    contact_name  = state.get("contact_name", "")
    contact_email = state.get("contact_email", "")
    if contact_name or contact_email:
        print(f"Emergency contact saved: {contact_name}  {contact_email}")

    # ── Camera ────────────────────────────────────────────────────────────────
    cap = cv2.VideoCapture(0, cv2.CAP_AVFOUNDATION)

    # ── Alert state ───────────────────────────────────────────────────────────
    eyes_closed_start = None
    eye_alert_level   = 0
    eye_prev_level    = 0

    nod_start         = None
    nod_alert_level   = 0
    nod_prev_level    = 0

    with mp_face_mesh.FaceMesh(
        max_num_faces=1,
        refine_landmarks=True,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5
    ) as face_mesh:

        # ── Calibration (runs before main loop) ───────────────────────────────
        EAR_THRESHOLD  = state.get("ear_threshold", 0.25)
        PITCH_BASELINE = state.get("pitch_baseline", 0.0)
        NOD_THRESHOLD  = PITCH_BASELINE + NOD_PITCH_OFFSET

        # ── Main detection loop ───────────────────────────────────────────────
        while cap.isOpened():

            # Check if UI silenced the alarm
            if state.get("alarm_silenced"):
                eye_alert_level   = 0
                nod_alert_level   = 0
                eyes_closed_start = None
                nod_start         = None
                state["alarm_silenced"] = False   # reset flag

            ret, frame = cap.read()
            if not ret:
                break

            h, w    = frame.shape[:2]
            rgb     = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = face_mesh.process(rgb)

            if results.multi_face_landmarks:
                for face_landmarks in results.multi_face_landmarks:

                    def get_point(idx):
                        lm = face_landmarks.landmark[idx]
                        return (lm.x * w, lm.y * h)

                    # ── EAR ───────────────────────────────────────────────────
                    left_pts   = [get_point(i) for i in LEFT_EYE]
                    right_pts  = [get_point(i) for i in RIGHT_EYE]
                    avg_EAR    = (calculate_EAR(left_pts) + calculate_EAR(right_pts)) / 2.0
                    eye_closed = avg_EAR < EAR_THRESHOLD

                    # ── Pitch ─────────────────────────────────────────────────
                    pitch     = calculate_pitch(face_landmarks, w, h)
                    head_down = pitch is not None and pitch > NOD_THRESHOLD

                    # ── Write EAR to shared state (ui.py reads this) ──────────
                    state["ear"] = round(avg_EAR, 3)

                    # ── Closed eyes timer ──────────────────────────────────────
                    if eye_closed:
                        if eyes_closed_start is None:
                            eyes_closed_start = time.time()
                        closed_duration = time.time() - eyes_closed_start
                        if closed_duration >= ALERT_3:
                            eye_alert_level = 3
                        elif closed_duration >= ALERT_2:
                            eye_alert_level = 2
                        elif closed_duration >= ALERT_1:
                            eye_alert_level = 1
                        else:
                            eye_alert_level = 0
                    else:
                        eyes_closed_start = None
                        eye_alert_level   = 0
                        closed_duration   = 0

                    # ── Head down timer ───────────────────────────────────────
                    if head_down:
                        if nod_start is None:
                            nod_start = time.time()
                        nod_duration = time.time() - nod_start
                        if nod_duration >= NOD_ALERT_3:
                            nod_alert_level = 3
                        elif nod_duration >= NOD_ALERT_2:
                            nod_alert_level = 2
                        elif nod_duration >= NOD_ALERT_1:
                            nod_alert_level = 1
                        else:
                            nod_alert_level = 0
                    else:
                        nod_start       = None
                        nod_alert_level = 0
                        nod_duration    = 0

                    # ── Final alert level ─────────────────────────────────────
                    alert_level = max(eye_alert_level, nod_alert_level)

                    # ── Write alert stage to shared state (ui.py reads this) ──
                    state["alert_stage"] = alert_level

                    # ── Sound triggers ────────────────────────────────────────
                if eye_alert_level != eye_prev_level:
                    if eye_alert_level == 1:
                        play_beep()
                    elif eye_alert_level == 2:
                        play_warning()
                    elif eye_alert_level == 3:
                        print("CRITICAL (eyes)")
                        speak("Critical alert. You have been driving with your eyes closed. Please pull over.")
                        send_critical_alert(contact_name, contact_email)
                    eye_prev_level = eye_alert_level

                if nod_alert_level != nod_prev_level:
                    if nod_alert_level == 1:
                        play_beep()
                    elif nod_alert_level == 2:
                        play_warning()
                        speak("Warning. Head nodding detected. Please stay alert.")
                    elif nod_alert_level == 3:
                        print("CRITICAL (head nod)")
                        speak("Critical alert. Head nodding detected. You may be falling asleep. Please pull over.")
                        send_critical_alert(contact_name, contact_email)
                    nod_prev_level = nod_alert_level

                    # ── Draw landmarks on frame ───────────────────────────────
                    color = alert_colors[alert_level]
                    for pt in left_pts + right_pts:
                        cv2.circle(frame, (int(pt[0]), int(pt[1])), 2, color, -1)

                    pts_left  = np.array([(int(p[0]), int(p[1])) for p in left_pts],  np.int32)
                    pts_right = np.array([(int(p[0]), int(p[1])) for p in right_pts], np.int32)
                    cv2.polylines(frame, [pts_left],  isClosed=True, color=color, thickness=1)
                    cv2.polylines(frame, [pts_right], isClosed=True, color=color, thickness=1)

            # ── Write processed frame to shared state (ui.py displays this) ───
            state["frame"] = frame

    cap.release()