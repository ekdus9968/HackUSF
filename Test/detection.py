import cv2
import mediapipe as mp
import numpy as np
import time
from calibration import calibrate
from constants import *
from sound import play_beep, play_warning
from emergency import get_emergency_contact
from sms import send_critical_alert

mp_face_mesh = mp.solutions.face_mesh
mp_drawing = mp.solutions.drawing_utils

LEFT_EYE  = [362, 385, 387, 263, 373, 380]
RIGHT_EYE = [33, 160, 158, 133, 153, 144]

# Alert thresholds in seconds
ALERT_1 = 3  # warning
ALERT_2 = 5  # danger
ALERT_3 = 8  # critical

 # Display
alert_colors = {
    0: (0, 255, 0),    # green - ok
    1: (0, 255, 255),  # yellow - warning
    2: (0, 165, 255),  # orange - danger
    3: (0, 0, 255),    # red - critical
}
alert_labels = {
    0: "ALERT: OK",
    1: "ALERT: WARNING (3s)",
    2: "ALERT: DANGER (5s)",
    3: "ALERT: CRITICAL (8s)",
}

def calculate_EAR(eye_landmarks):
    A = np.linalg.norm(np.array(eye_landmarks[1]) - np.array(eye_landmarks[5]))
    B = np.linalg.norm(np.array(eye_landmarks[2]) - np.array(eye_landmarks[4]))
    C = np.linalg.norm(np.array(eye_landmarks[0]) - np.array(eye_landmarks[3]))
    return (A + B) / (2.0 * C)

# ── enter energency contact ──────────────────────────────────────────────
contact_name, contact_email = get_emergency_contact()
if contact_name or contact_email:
    print(f"Emergency contact saved: {contact_name}  {contact_email}")

cap = cv2.VideoCapture(0)

eyes_closed_start = None  # timestamp when eyes first closed
alert_level = 0           # 0 = ok, 1 = warning, 2 = danger, 3 = critical
prev_alert_level = 0      # 

with mp_face_mesh.FaceMesh(
    max_num_faces=1,
    refine_landmarks=True,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5
) as face_mesh:
    EAR_THRESHOLD = calibrate(face_mesh, cap)
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = face_mesh.process(rgb)

        if results.multi_face_landmarks:
            for face_landmarks in results.multi_face_landmarks:

                def get_point(idx):
                    lm = face_landmarks.landmark[idx]
                    return (lm.x * frame.shape[1], lm.y * frame.shape[0])

                left_pts  = [get_point(i) for i in LEFT_EYE]
                right_pts = [get_point(i) for i in RIGHT_EYE]
                avg_EAR   = (calculate_EAR(left_pts) + calculate_EAR(right_pts)) / 2.0
                eye_closed = avg_EAR < EAR_THRESHOLD

                # Draw eye outlines
                color = alert_colors[alert_level]
                for pt in left_pts + right_pts:
                    cv2.circle(frame, (int(pt[0]), int(pt[1])), 2, color, -1)

                pts_left  = np.array([(int(p[0]), int(p[1])) for p in left_pts], np.int32)
                pts_right = np.array([(int(p[0]), int(p[1])) for p in right_pts], np.int32)
                cv2.polylines(frame, [pts_left], isClosed=True, color=color, thickness=1)
                cv2.polylines(frame, [pts_right], isClosed=True, color=color, thickness=1)
                # Timer logic
                if eye_closed:
                    if eyes_closed_start is None:
                        eyes_closed_start = time.time()
                    closed_duration = time.time() - eyes_closed_start

                    if closed_duration >= ALERT_3:
                        alert_level = 3
                    elif closed_duration >= ALERT_2:
                        alert_level = 2
                    elif closed_duration >= ALERT_1:
                        alert_level = 1
                    else:
                        alert_level = 0
                else:
                    # Eyes open — reset
                    eyes_closed_start = None
                    alert_level = 0
                    closed_duration = 0

                # Sound: one time play
                if alert_level != prev_alert_level:
                    if alert_level == 1:
                        play_beep()
                    elif alert_level == 2:
                        play_warning()
                    elif alert_level == 3:
                        print("CRITICAL")
                        send_critical_alert(contact_name, contact_email)
                    prev_alert_level = alert_level

                color = alert_colors[alert_level]
                cv2.putText(frame, f"EAR: {avg_EAR:.2f}", (30, 50),
                            cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)
                cv2.putText(frame, alert_labels[alert_level], (30, 100),
                            cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)
                if eye_closed:
                    cv2.putText(frame, f"Closed: {closed_duration:.1f}s", (30, 150),
                                cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)

        cv2.imshow("Tiredness Tracker", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

cap.release()
cv2.destroyAllWindows()