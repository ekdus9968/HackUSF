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

mp_face_mesh = mp.solutions.face_mesh

LEFT_EYE  = [362, 385, 387, 263, 373, 380]
RIGHT_EYE = [33, 160, 158, 133, 153, 144]

alert_colors = {
    0: (0, 255, 0),
    1: (0, 255, 255),
    2: (0, 165, 255),
    3: (0, 0, 255),
}
alert_labels = {
    0: "ALERT: OK",
    1: "ALERT: WARNING",
    2: "ALERT: DANGER",
    3: "ALERT: CRITICAL",
}

def calculate_EAR(eye_landmarks):
    A = np.linalg.norm(np.array(eye_landmarks[1]) - np.array(eye_landmarks[5]))
    B = np.linalg.norm(np.array(eye_landmarks[2]) - np.array(eye_landmarks[4]))
    C = np.linalg.norm(np.array(eye_landmarks[0]) - np.array(eye_landmarks[3]))
    return (A + B) / (2.0 * C)

# ── STOP 버튼 ─────────────────────────────────────────────────────
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

# ── 비상 연락처 ───────────────────────────────────────────────────
contact_name, contact_email = get_emergency_contact()
if contact_name or contact_email:
    print(f"Emergency contact saved: {contact_name}  {contact_email}")

start_voice_listener()

cap = cv2.VideoCapture(0)

clicked   = [False]
click_pos = [(-1, -1)]
def on_mouse(event, x, y, flags, param):
    if event == cv2.EVENT_LBUTTONDOWN:
        clicked[0]   = True
        click_pos[0] = (x, y)
cv2.namedWindow("Tiredness Tracker")
cv2.setMouseCallback("Tiredness Tracker", on_mouse)

# ── 상태 변수 ─────────────────────────────────────────────────────
closed_start   = None    # 눈 감김/고개 숙임 시작 시각
alert_level    = 0
prev_level     = 0

BEEP_INTERVAL  = 2.0
last_sound_t   = 0.0

# "눈 뜬 채로 대기" 모드 — STOP 누를 때까지 소리 반복
waiting_stop   = False   # True 이면 눈 떴지만 아직 STOP 안 누른 상태
waiting_level  = 0       # 대기 중인 alert level (1 or 2)

with mp_face_mesh.FaceMesh(
    max_num_faces=1,
    refine_landmarks=True,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5
) as face_mesh:

    EAR_THRESHOLD, PITCH_BASELINE = calibrate(face_mesh, cap)
    cv2.destroyWindow("Calibration")
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

                danger    = eye_closed or head_down  # 위험 상태 여부

                # ── STOP 버튼 클릭 or 음성 "stop" ────────────────
                voice_stop = consume_stop()
                if clicked[0] or voice_stop:
                    btn_hit = voice_stop or is_btn_clicked(*click_pos[0])
                    if btn_hit and (alert_level >= 1 or waiting_stop):
                        # 소리/타이머 전부 리셋 → 정상 복귀
                        closed_start  = None
                        alert_level   = 0
                        prev_level    = 0
                        waiting_stop  = False
                        waiting_level = 0
                        last_sound_t  = 0.0
                    clicked[0] = False

                # ── "눈 뜬 채로 대기" 모드 처리 ──────────────────
                if waiting_stop:
                    if now - last_sound_t >= BEEP_INTERVAL:
                        if waiting_level == 1:
                            play_beep()
                        else:
                            play_warning()
                        last_sound_t = now
                    # 이 모드에서는 타이머 진행 없음 — STOP 기다림
                    # HUD / 버튼 그리고 다음 프레임으로
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
                    # ── 일반 타이머 로직 ──────────────────────────
                    if danger:
                        if closed_start is None:
                            closed_start = now
                        duration = now - closed_start

                        if   duration >= ALERT_3: alert_level = 3
                        elif duration >= ALERT_2: alert_level = 2
                        elif duration >= ALERT_1: alert_level = 1
                        else:                     alert_level = 0
                    else:
                        # 눈 뜸 / 고개 듦
                        if alert_level in (1, 2):
                            # ALERT_1 or 2 중 회복 → 대기 모드 진입
                            waiting_stop  = True
                            waiting_level = alert_level
                            closed_start  = None
                            alert_level   = 0
                            last_sound_t  = 0.0
                        else:
                            closed_start = None
                            alert_level  = 0

                    # ── 레벨 전환 시 소리/이벤트 ──────────────────
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
                            last_sound_t = 0.0
                        prev_level = alert_level

                    # ALERT_1/2 유지 중 반복 재생
                    if alert_level == 1 and now - last_sound_t >= BEEP_INTERVAL:
                        play_beep()
                        last_sound_t = now
                    elif alert_level == 2 and now - last_sound_t >= BEEP_INTERVAL:
                        play_warning()
                        last_sound_t = now

                    # ── 눈 윤곽선 ─────────────────────────────────
                    color = alert_colors[alert_level]
                    for pt in left_pts + right_pts:
                        cv2.circle(frame, (int(pt[0]), int(pt[1])), 2, color, -1)
                    pts_l = np.array([(int(p[0]), int(p[1])) for p in left_pts],  np.int32)
                    pts_r = np.array([(int(p[0]), int(p[1])) for p in right_pts], np.int32)
                    cv2.polylines(frame, [pts_l], isClosed=True, color=color, thickness=1)
                    cv2.polylines(frame, [pts_r], isClosed=True, color=color, thickness=1)

                    # ── HUD ───────────────────────────────────────
                    color = alert_colors[alert_level]
                    cv2.putText(frame, f"EAR: {avg_EAR:.2f}", (30, 50),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
                    cv2.putText(frame, alert_labels[alert_level], (30, 90),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.9, color, 2)
                    if danger and closed_start:
                        duration = now - closed_start
                        label = "Eyes closed" if eye_closed else "Head down"
                        cv2.putText(frame, f"{label}: {duration:.1f}s", (30, 130),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

                    if alert_level >= 1:
                        draw_stop_button(frame)

        cv2.imshow("Tiredness Tracker", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

cap.release()
cv2.destroyAllWindows()