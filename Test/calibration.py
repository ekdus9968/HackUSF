import cv2
import numpy as np
from constants import LEFT_EYE, RIGHT_EYE, calculate_EAR, calculate_pitch


def calibrate(face_mesh, cap):
    print("Calibration: Keep eyes OPEN. Press SPACE when ready...")
    open_ears = []
    closed_ears = []

    # Collect open EAR
    collecting = False
    while True:
        ret, frame = cap.read()
        if not ret or frame is None:
            continue
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = face_mesh.process(rgb)

        cv2.putText(frame, "OPEN eyes, press SPACE to start", (30, 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,255,0), 2)

        if collecting and results.multi_face_landmarks:
            for face_landmarks in results.multi_face_landmarks:
                def get_point(idx):
                    lm = face_landmarks.landmark[idx]
                    return (lm.x * frame.shape[1], lm.y * frame.shape[0])
                left_pts  = [get_point(i) for i in LEFT_EYE]
                right_pts = [get_point(i) for i in RIGHT_EYE]
                ear = (calculate_EAR(left_pts) + calculate_EAR(right_pts)) / 2.0
                open_ears.append(ear)
            cv2.putText(frame, f"Collecting... {len(open_ears)}/60", (30, 100),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,255,0), 2)

        cv2.imshow("Calibration", frame)
        key = cv2.waitKey(1) & 0xFF
        if key == ord(' ') and not collecting:
            collecting = True
        if len(open_ears) >= 60:
            break

    # Collect closed EAR
    collecting = False
    print("Now CLOSE your eyes. Press SPACE when ready...")
    while True:
        ret, frame = cap.read()
        if not ret or frame is None:
            continue
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = face_mesh.process(rgb)

        cv2.putText(frame, "CLOSE eyes, press SPACE to start", (30, 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,0,255), 2)

        if collecting and results.multi_face_landmarks:
            for face_landmarks in results.multi_face_landmarks:
                def get_point(idx):
                    lm = face_landmarks.landmark[idx]
                    return (lm.x * frame.shape[1], lm.y * frame.shape[0])
                left_pts  = [get_point(i) for i in LEFT_EYE]
                right_pts = [get_point(i) for i in RIGHT_EYE]
                ear = (calculate_EAR(left_pts) + calculate_EAR(right_pts)) / 2.0
                closed_ears.append(ear)
            cv2.putText(frame, f"Collecting... {len(closed_ears)}/60", (30, 100),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,0,255), 2)

        cv2.imshow("Calibration", frame)
        key = cv2.waitKey(1) & 0xFF
        if key == ord(' ') and not collecting:
            collecting = True
        if len(closed_ears) >= 60:
            break

    open_avg   = np.mean(open_ears)
    closed_avg = np.mean(closed_ears)
    threshold  = (open_avg + closed_avg) / 2.0
    print(f"Calibrated — Open: {open_avg:.2f}, Closed: {closed_avg:.2f}, Threshold: {threshold:.2f}")

    # ── Head Pose 캘리브레이션 ─────────────────────────────────────
    collecting = False
    pitch_samples = []
    print("Head pose calibration: Look STRAIGHT ahead. Press SPACE when ready...")
    while True:
        ret, frame = cap.read()
        if not ret or frame is None:
            continue
        h, w = frame.shape[:2]
        rgb     = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = face_mesh.process(rgb)

        cv2.putText(frame, "Look STRAIGHT, press SPACE to start", (30, 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 200, 0), 2)

        if collecting and results.multi_face_landmarks:
            for face_landmarks in results.multi_face_landmarks:
                pitch = calculate_pitch(face_landmarks, w, h)
                if pitch is not None:
                    pitch_samples.append(pitch)
            cv2.putText(frame, f"Collecting... {len(pitch_samples)}/60", (30, 100),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 200, 0), 2)

        cv2.imshow("Calibration", frame)
        key = cv2.waitKey(1) & 0xFF
        if key == ord(' ') and not collecting:
            collecting = True
        if len(pitch_samples) >= 60:
            break

    pitch_baseline = float(np.mean(pitch_samples))
    print(f"Head pose baseline pitch: {pitch_baseline:.2f}°")

    return threshold, pitch_baseline