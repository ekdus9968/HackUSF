import numpy as np
import cv2

LEFT_EYE  = [362, 385, 387, 263, 373, 380]
RIGHT_EYE = [33, 160, 158, 133, 153, 144]

# Head pose landmarks (solvePnP)
# 
HEAD_POSE_POINTS = [1, 152, 4, 263, 33, 287, 57]

ALERT_1 = 3
ALERT_2 = 5
ALERT_3 = 8

# bow head: alert thresholds (seconds)
NOD_ALERT_1 = 3
NOD_ALERT_2 = 5
NOD_ALERT_3 = 7

# Head-Down Detection: Detected if the pitch angle drops below the calibration baseline by more than this specified angle (in degrees).
NOD_PITCH_OFFSET = 10.0

alert_colors = {
    0: (0, 255, 0),
    1: (0, 255, 255),
    2: (0, 165, 255),
    3: (0, 0, 255),
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


def calculate_pitch(face_landmarks, frame_w, frame_h):
    """MediaPipe convert head pitch degree by landmark— down + int"""
    # 3D model base 
    model_points = np.array([
        (0.0,    0.0,    0.0),    # end of nose (1)
        (0.0,   -330.0, -65.0),   # chin (152)
        (0.0,   -30.0,  -135.0),  # under nose (4)
        (-225.0, 170.0, -135.0),  # left end eye (263)
        (225.0,  170.0, -135.0),  # right end eye (33)
        (-150.0, -150.0,-125.0),  # left corners of mouth(287)
        (150.0,  -150.0,-125.0),  # right corners of mouth (57)
    ], dtype=np.float64)

    image_points = np.array([
        (face_landmarks.landmark[i].x * frame_w,
         face_landmarks.landmark[i].y * frame_h)
        for i in HEAD_POSE_POINTS
    ], dtype=np.float64)

    focal_length = frame_w
    center = (frame_w / 2, frame_h / 2)
    camera_matrix = np.array([
        [focal_length, 0,            center[0]],
        [0,            focal_length, center[1]],
        [0,            0,            1         ]
    ], dtype=np.float64)
    dist_coeffs = np.zeros((4, 1))

    success, rvec, _ = cv2.solvePnP(
        model_points, image_points, camera_matrix, dist_coeffs,
        flags=cv2.SOLVEPNP_ITERATIVE
    )
    if not success:
        return None

    rmat, _ = cv2.Rodrigues(rvec)
    # pitch: x : down + poisitve int
    pitch = np.degrees(np.arctan2(rmat[2][1], rmat[2][2]))
    return pitch