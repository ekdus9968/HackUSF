import numpy as np

LEFT_EYE  = [362, 385, 387, 263, 373, 380]
RIGHT_EYE = [33, 160, 158, 133, 153, 144]

ALERT_1 = 3
ALERT_2 = 5
ALERT_3 = 8

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