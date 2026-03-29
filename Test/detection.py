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
import time

from calibration import calibrate
from constants import *
from sound import play_beep, play_warning
from sms import send_critical_alert
from voice import start_voice_listener, consume_stop
from alert import speak
from chat import handle_chat
from auth import save_calibration
from config import state

mp_face_mesh = mp.solutions.face_mesh

LEFT_EYE  = [362, 385, 387, 263, 373, 380]
RIGHT_EYE = [33, 160, 158, 133, 153, 144]

def calculate_EAR(eye_landmarks):
    A = np.linalg.norm(np.array(eye_landmarks[1]) - np.array(eye_landmarks[5]))
    B = np.linalg.norm(np.array(eye_landmarks[2]) - np.array(eye_landmarks[4]))
    C = np.linalg.norm(np.array(eye_landmarks[0]) - np.array(eye_landmarks[3]))
    return (A + B) / (2.0 * C)


def run():
    # ── Voice listener ────────────────────────────────────────────────────────
    start_voice_listener(chat_handler=handle_chat)

    # ── Emergency contact from state (set by main.py) ─────────────────────────
    contact_name  = state.get("contact_name", "")
    contact_email = state.get("contact_email", "")

    # ── Camera ────────────────────────────────────────────────────────────────
    cap = cv2.VideoCapture(0, cv2.CAP_AVFOUNDATION)

    # ── Alert state ───────────────────────────────────────────────────────────
    closed_start   = None
    alert_level    = 0
    prev_level     = 0

    BEEP_INTERVAL  = 2.0
    last_sound_t   = 0.0

    # Waiting mode: eyes opened but STOP not yet said
    waiting_stop   = False
    waiting_level  = 0

    # Prevent duplicate critical voice alert
    spoke_critical = False

    with mp_face_mesh.FaceMesh(
        max_num_faces=1,
        refine_landmarks=True,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5
    ) as face_mesh:

        # ── Load calibration from state (set during onboarding in main.py) ────
        EAR_THRESHOLD  = state.get("ear_threshold", 0.25)
        PITCH_BASELINE = state.get("pitch_baseline", 0.0)
        NOD_THRESHOLD  = PITCH_BASELINE + NOD_PITCH_OFFSET

        # ── Main detection loop ───────────────────────────────────────────────
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret or frame is None:
                continue

            now    = time.time()
            h, w   = frame.shape[:2]
            rgb    = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = face_mesh.process(rgb)

            if results.multi_face_landmarks:
                for face_landmarks in results.multi_face_landmarks:

                    def get_point(idx):
                        lm = face_landmarks.landmark[idx]
                        return (lm.x * w, lm.y * h)

                    # ── EAR + pitch ───────────────────────────────────────────
                    left_pts   = [get_point(i) for i in LEFT_EYE]
                    right_pts  = [get_point(i) for i in RIGHT_EYE]
                    avg_EAR    = (calculate_EAR(left_pts) + calculate_EAR(right_pts)) / 2.0
                    eye_closed = avg_EAR < EAR_THRESHOLD

                    pitch     = calculate_pitch(face_landmarks, w, h)
                    head_down = pitch is not None and pitch > NOD_THRESHOLD

                    danger = eye_closed or head_down

                    # ── Write EAR to shared state ─────────────────────────────
                    state["ear"] = round(avg_EAR, 3)

                    # ── STOP: voice command or UI button ──────────────────────
                    voice_stop = consume_stop()
                    ui_stop    = state.get("alarm_silenced", False)

                    if voice_stop or ui_stop:
                        closed_start   = None
                        alert_level    = 0
                        prev_level     = 0
                        waiting_stop   = False
                        waiting_level  = 0
                        last_sound_t   = 0.0
                        spoke_critical = False
                        state["alarm_silenced"] = False
                        state["alert_stage"]    = 0

                    # ── Waiting mode: eyes open but STOP not yet said ─────────
                    if waiting_stop:
                        if now - last_sound_t >= BEEP_INTERVAL:
                            if waiting_level == 1:
                                play_beep()
                            else:
                                play_warning()
                            last_sound_t = now

                        # Keep alert stage visible in UI during waiting mode
                        state["alert_stage"] = waiting_level

                    else:
                        # ── Alert timer logic ─────────────────────────────────
                        if danger:
                            if closed_start is None:
                                closed_start   = now
                                spoke_critical = False
                            duration = now - closed_start

                            if   duration >= ALERT_3: alert_level = 3
                            elif duration >= ALERT_2: alert_level = 2
                            elif duration >= ALERT_1: alert_level = 1
                            else:                     alert_level = 0
                        else:
                            if alert_level in (1, 2):
                                # Eyes opened before critical — enter waiting mode
                                waiting_stop  = True
                                waiting_level = alert_level
                                closed_start  = None
                                alert_level   = 0
                                last_sound_t  = 0.0
                            else:
                                closed_start = None
                                alert_level  = 0

                        # ── Write alert stage to shared state ─────────────────
                        state["alert_stage"] = alert_level

                        # ── Sound / voice / email on level change ─────────────
                        if alert_level != prev_level:
                            if alert_level == 1:
                                play_beep()
                                last_sound_t = now
                            elif alert_level == 2:
                                play_warning()
                                speak("Warning. Drowsiness detected. Please stay alert.")
                                last_sound_t = now
                            elif alert_level == 3:
                                print("CRITICAL")
                                send_critical_alert(contact_name, contact_email)
                            elif alert_level == 0:
                                last_sound_t   = 0.0
                                spoke_critical = False
                            prev_level = alert_level

                        # ── Critical voice alert (once only) ─────────────────
                        if alert_level == 3 and not spoke_critical:
                            label = "eyes closed" if eye_closed else "head down"
                            speak(f"Warning! You have been driving with your {label}. Please pull over immediately.")
                            spoke_critical = True

                        # ── Repeat sound while alert persists ─────────────────
                        if alert_level == 1 and now - last_sound_t >= BEEP_INTERVAL:
                            play_beep()
                            last_sound_t = now
                        elif alert_level == 2 and now - last_sound_t >= BEEP_INTERVAL:
                            play_warning()
                            last_sound_t = now

                    # ── Draw landmarks on frame ───────────────────────────────
                    color = alert_colors[max(alert_level, waiting_level if waiting_stop else 0)]
                    for pt in left_pts + right_pts:
                        cv2.circle(frame, (int(pt[0]), int(pt[1])), 2, color, -1)

                    pts_left  = np.array([(int(p[0]), int(p[1])) for p in left_pts],  np.int32)
                    pts_right = np.array([(int(p[0]), int(p[1])) for p in right_pts], np.int32)
                    cv2.polylines(frame, [pts_left],  isClosed=True, color=color, thickness=1)
                    cv2.polylines(frame, [pts_right], isClosed=True, color=color, thickness=1)

            # ── Write processed frame to shared state (ui.py displays this) ───
            state["frame"] = frame

    cap.release()