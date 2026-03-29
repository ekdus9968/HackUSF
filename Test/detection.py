import cv2
import mediapipe as mp
import numpy as np
import time
from calibration import calibrate
from constants import *
from sound import play_beep, play_warning
from emergency import get_emergency_contact
from sms import send_critical_alert
from voice import start_voice_listener, consume_stop
from alert import speak
from chat import handle_chat
from auth import run_auth, save_calibration

mp_face_mesh = mp.solutions.face_mesh

# ── STOP button ───────────────────────────────────────────────────
BTN = {"x": 20, "y": 210, "w": 110, "h": 42}

def draw_stop_button(frame):
    cv2.rectangle(frame,
                  (BTN["x"], BTN["y"]),
                  (BTN["x"] + BTN["w"], BTN["y"] + BTN["h"]),
                  (50, 50, 200), -1)
    cv2.rectangle(frame,
                  (BTN["x"], BTN["y"]),
                  (BTN["x"] + BTN["w"], BTN["y"] + BTN["h"]),
                  (255, 255, 255), 2)
    cv2.putText(frame, " STOP",
                (BTN["x"] + 8, BTN["y"] + 28),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

def is_btn_clicked(x, y):
    return (BTN["x"] <= x <= BTN["x"] + BTN["w"] and
            BTN["y"] <= y <= BTN["y"] + BTN["h"])

# Authentication
user = run_auth()
if user is None:
    exit()

# Pre-fill emergency contact from account, or ask manually if guest
if user["user_id"] == "guest" or not user.get("emergency_email"):
    contact_name, contact_email = get_emergency_contact()
else:
    contact_name  = f"{user['first_name']} {user['last_name']}"
    contact_email = user["emergency_email"]
    print(f"Emergency contact loaded from account: {contact_name}  {contact_email}")

start_voice_listener(chat_handler=handle_chat)

cap = cv2.VideoCapture(0)

clicked   = [False]
click_pos = [(-1, -1)]
def on_mouse(event, x, y, flags, param):
    if event == cv2.EVENT_LBUTTONDOWN:
        clicked[0]   = True
        click_pos[0] = (x, y)
cv2.namedWindow("Tiredness Tracker")
cv2.setMouseCallback("Tiredness Tracker", on_mouse)

# ── State variables ───────────────────────────────────────────────
closed_start   = None
alert_level    = 0
prev_level     = 0

BEEP_INTERVAL  = 2.0
last_sound_t   = 0.0

# Waiting mode: eyes opened but STOP not yet pressed
waiting_stop   = False
waiting_level  = 0

# Prevent duplicate CRITICAL voice alert
spoke_critical = False

# Driving time reminder
drive_start_t     = time.time()
DRIVE_REMINDER_S  = 30        # 30 s for demo (swap to 7200 for 2-hr real use)
last_reminder_t   = drive_start_t

with mp_face_mesh.FaceMesh(
    max_num_faces=1,
    refine_landmarks=True,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5
) as face_mesh:

    # Use saved calibration or run new one
    if user.get("needs_calibration") or user["ear_threshold"] is None:
        EAR_THRESHOLD, PITCH_BASELINE = calibrate(face_mesh, cap)
        cv2.destroyWindow("Calibration")
        if user["user_id"] != "guest":
            save_calibration(user["user_id"], EAR_THRESHOLD, PITCH_BASELINE)
            print(f"[Auth] Calibration saved for '{user['user_id']}'.")
    else:
        EAR_THRESHOLD  = user["ear_threshold"]
        PITCH_BASELINE = user["pitch_baseline"]
        print(f"[Auth] Calibration loaded — EAR: {EAR_THRESHOLD:.3f}, Pitch: {PITCH_BASELINE:.2f}")
    NOD_THRESHOLD = PITCH_BASELINE + NOD_PITCH_OFFSET

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

                left_pts   = [get_point(i) for i in LEFT_EYE]
                right_pts  = [get_point(i) for i in RIGHT_EYE]
                avg_EAR    = (calculate_EAR(left_pts) + calculate_EAR(right_pts)) / 2.0
                eye_closed = avg_EAR < EAR_THRESHOLD

                pitch     = calculate_pitch(face_landmarks, w, h)
                head_down = pitch is not None and pitch > NOD_THRESHOLD

                danger    = eye_closed or head_down

                # ── STOP: button click or voice command ───────────
                voice_stop = consume_stop()
                if clicked[0] or voice_stop:
                    btn_hit = voice_stop or is_btn_clicked(*click_pos[0])
                    if btn_hit and (alert_level >= 1 or waiting_stop):
                        closed_start   = None
                        alert_level    = 0
                        prev_level     = 0
                        waiting_stop   = False
                        waiting_level  = 0
                        last_sound_t   = 0.0
                        spoke_critical = False
                    clicked[0] = False

                # ── Waiting mode: eyes open, waiting for STOP ─────
                if waiting_stop:
                    if now - last_sound_t >= BEEP_INTERVAL:
                        if waiting_level == 1:
                            play_beep()
                        else:
                            play_warning()
                        last_sound_t = now

                    color = alert_colors[waiting_level]
                    for pt in left_pts + right_pts:
                        cv2.circle(frame, (int(pt[0]), int(pt[1])), 2, color, -1)
                    pts_l = np.array([(int(p[0]), int(p[1])) for p in left_pts],  np.int32)
                    pts_r = np.array([(int(p[0]), int(p[1])) for p in right_pts], np.int32)
                    cv2.polylines(frame, [pts_l], isClosed=True, color=color, thickness=1)
                    cv2.polylines(frame, [pts_r], isClosed=True, color=color, thickness=1)
                    cv2.putText(frame, f"EAR: {avg_EAR:.2f}", (30, 50),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
                    cv2.putText(frame, alert_labels[waiting_level] + " - STOP to clear",
                                (30, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.75, color, 2)
                    draw_stop_button(frame)

                else:
                    # ── Alert timer logic ─────────────────────────
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
                            # Eyes open before CRITICAL -> enter waiting mode
                            waiting_stop  = True
                            waiting_level = alert_level
                            closed_start  = None
                            alert_level   = 0
                            last_sound_t  = 0.0
                        else:
                            closed_start = None
                            alert_level  = 0

                    # ── Sound / voice / email on level change ─────
                    if alert_level != prev_level:
                        if alert_level == 1:
                            play_beep()
                            last_sound_t = now
                        elif alert_level == 2:
                            play_warning()
                            last_sound_t = now
                        elif alert_level == 3:
                            print("CRITICAL")
                            send_critical_alert(contact_name, contact_email)
                        elif alert_level == 0:
                            last_sound_t   = 0.0
                            spoke_critical = False
                        prev_level = alert_level

                    # CRITICAL voice alert (once only)
                    if alert_level == 3 and not spoke_critical:
                        label = "eyes closed" if eye_closed else "head down"
                        speak(f"Warning! You have been driving with your {label}. Please pull over immediately.")
                        spoke_critical = True

                    # Repeat sound while alert level persists
                    if alert_level == 1 and now - last_sound_t >= BEEP_INTERVAL:
                        play_beep()
                        last_sound_t = now
                    elif alert_level == 2 and now - last_sound_t >= BEEP_INTERVAL:
                        play_warning()
                        last_sound_t = now

                    # ── Draw eye outlines ─────────────────────────
                    color = alert_colors[alert_level]
                    for pt in left_pts + right_pts:
                        cv2.circle(frame, (int(pt[0]), int(pt[1])), 2, color, -1)
                    pts_l = np.array([(int(p[0]), int(p[1])) for p in left_pts],  np.int32)
                    pts_r = np.array([(int(p[0]), int(p[1])) for p in right_pts], np.int32)
                    cv2.polylines(frame, [pts_l], isClosed=True, color=color, thickness=1)
                    cv2.polylines(frame, [pts_r], isClosed=True, color=color, thickness=1)

                    # ── HUD overlay ───────────────────────────────
                    cv2.putText(frame, f"EAR: {avg_EAR:.2f}", (30, 50),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
                    cv2.putText(frame, alert_labels[alert_level], (30, 90),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.9, color, 2)
                    if danger and closed_start:
                        duration = now - closed_start
                        label    = "Eyes closed" if eye_closed else "Head down"
                        cv2.putText(frame, f"{label}: {duration:.1f}s", (30, 130),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

                    if alert_level >= 1:
                        draw_stop_button(frame)
                    # ── Driving time reminder ─────────────────────────────────────
                    if now - last_reminder_t >= DRIVE_REMINDER_S:
                        elapsed_min = int((now - drive_start_t) / 60)
                        if elapsed_min < 1:
                            duration_str = "a little while"
                        else:
                            duration_str = f"{elapsed_min} minute{'s' if elapsed_min != 1 else ''}"
                        speak(f"Hey, you've been driving for {duration_str}. Consider taking a short break to stay safe.")
                        last_reminder_t = now

        cv2.imshow("Tiredness Tracker", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

cap.release()
cv2.destroyAllWindows()