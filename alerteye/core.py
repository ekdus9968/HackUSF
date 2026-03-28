"""
core.py — Face detection, EAR calculation, and drowsiness state tracking.
Agent 1: Core Engine for AlertEye.
"""

import time
import threading

import cv2
import mediapipe as mp
import numpy as np

import config

# ---------------------------------------------------------------------------
# Module-level state
# ---------------------------------------------------------------------------

_cap: cv2.VideoCapture | None = None
_running = False
_thread: threading.Thread | None = None

_latest_frame: np.ndarray | None = None
_drowsiness_state: dict = {
    "status": "NORMAL",
    "ear_value": 0.0,
    "closed_seconds": 0.0,
    "face_detected": False,
}
_state_lock = threading.Lock()

_eye_closed_since: float | None = None  # timestamp when eyes first closed

# MediaPipe
_mp_face_mesh = mp.solutions.face_mesh
_face_mesh = _mp_face_mesh.FaceMesh(
    refine_landmarks=True,
    max_num_faces=1,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5,
)
_mp_drawing = mp.solutions.drawing_utils
_mp_drawing_styles = mp.solutions.drawing_styles


# ---------------------------------------------------------------------------
# EAR calculation
# ---------------------------------------------------------------------------

def _compute_ear(landmarks, eye_indices: list[int], frame_w: int, frame_h: int) -> float:
    """Compute Eye Aspect Ratio (EAR) for one eye.

    EAR = (||p2-p6|| + ||p3-p5||) / (2 * ||p1-p4||)

    Args:
        landmarks: MediaPipe normalized landmark list.
        eye_indices: 6 landmark indices [p1, p2, p3, p4, p5, p6].
        frame_w: Frame width in pixels.
        frame_h: Frame height in pixels.

    Returns:
        EAR value as float.
    """
    def lm(idx):
        pt = landmarks[idx]
        return np.array([pt.x * frame_w, pt.y * frame_h])

    p1, p2, p3, p4, p5, p6 = [lm(i) for i in eye_indices]

    vertical1 = np.linalg.norm(p2 - p6)
    vertical2 = np.linalg.norm(p3 - p5)
    horizontal = np.linalg.norm(p1 - p4)

    if horizontal < 1e-6:
        return 0.0

    return (vertical1 + vertical2) / (2.0 * horizontal)


# ---------------------------------------------------------------------------
# Overlay drawing
# ---------------------------------------------------------------------------

def _draw_overlay(frame: np.ndarray, face_results, ear: float, status: str) -> np.ndarray:
    """Draw face mesh tessellation and EAR/status overlay on the frame.

    Args:
        frame: BGR frame from OpenCV.
        face_results: MediaPipe FaceMesh process result.
        ear: Current EAR value.
        status: Current drowsiness status string.

    Returns:
        Frame with overlay drawn (same array, modified in-place, also returned).
    """
    if face_results.multi_face_landmarks:
        for face_landmarks in face_results.multi_face_landmarks:
            _mp_drawing.draw_landmarks(
                image=frame,
                landmark_list=face_landmarks,
                connections=_mp_face_mesh.FACEMESH_TESSELATION,
                landmark_drawing_spec=None,
                connection_drawing_spec=_mp_drawing_styles.get_default_face_mesh_tesselation_style(),
            )
            _mp_drawing.draw_landmarks(
                image=frame,
                landmark_list=face_landmarks,
                connections=_mp_face_mesh.FACEMESH_CONTOURS,
                landmark_drawing_spec=None,
                connection_drawing_spec=_mp_drawing_styles.get_default_face_mesh_contours_style(),
            )

    # Status color mapping (BGR)
    status_bgr = {
        "NORMAL": (113, 204,  46),
        "STAGE1": ( 18, 156, 243),
        "STAGE2": ( 60,  76, 231),
        "SMS":    (173,  68, 142),
    }
    color = status_bgr.get(status, (255, 255, 255))

    cv2.putText(frame, f"EAR: {ear:.3f}", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
    cv2.putText(frame, f"Status: {status}", (10, 65),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)

    return frame


# ---------------------------------------------------------------------------
# Detection loop (runs in background thread)
# ---------------------------------------------------------------------------

def _detection_loop() -> None:
    """Main detection loop: reads webcam frames, computes EAR, updates state."""
    global _cap, _running, _latest_frame, _eye_closed_since

    _cap = cv2.VideoCapture(config.CAMERA_INDEX)
    _cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.FRAME_WIDTH)
    _cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.FRAME_HEIGHT)

    if not _cap.isOpened():
        print("[core] ERROR: Cannot open camera.")
        _running = False
        return

    # 2-second warmup required before the camera starts delivering frames.
    time.sleep(2)

    while _running:
        # Retry up to 10 times with 0.1s delay if frame read fails.
        ret, frame = False, None
        for _ in range(10):
            ret, frame = _cap.read()
            if ret and frame is not None:
                break
            time.sleep(0.1)
        if not ret or frame is None:
            continue

        frame = cv2.resize(frame, (config.FRAME_WIDTH, config.FRAME_HEIGHT))
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = _face_mesh.process(rgb)

        h, w = frame.shape[:2]
        face_detected = bool(results.multi_face_landmarks)
        ear = 0.0
        status = "NORMAL"
        closed_seconds = 0.0

        if face_detected:
            lms = results.multi_face_landmarks[0].landmark
            left_ear  = _compute_ear(lms, config.LEFT_EYE_IDX,  w, h)
            right_ear = _compute_ear(lms, config.RIGHT_EYE_IDX, w, h)
            ear = (left_ear + right_ear) / 2.0

            now = time.time()
            threshold = config.EAR_THRESHOLD

            if ear < threshold:
                if _eye_closed_since is None:
                    _eye_closed_since = now
                closed_seconds = now - _eye_closed_since
            else:
                _eye_closed_since = None
                closed_seconds = 0.0

            if closed_seconds >= config.SMS_SECONDS:
                status = "SMS"
            elif closed_seconds >= config.STAGE2_SECONDS:
                status = "STAGE2"
            elif closed_seconds >= config.STAGE1_SECONDS:
                status = "STAGE1"
            else:
                status = "NORMAL"
        else:
            _eye_closed_since = None

        overlaid = _draw_overlay(frame.copy(), results, ear, status)

        with _state_lock:
            _latest_frame = overlaid
            _drowsiness_state["status"]         = status
            _drowsiness_state["ear_value"]       = round(ear, 4)
            _drowsiness_state["closed_seconds"]  = round(closed_seconds, 2)
            _drowsiness_state["face_detected"]   = face_detected

    if _cap:
        _cap.release()
        _cap = None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def start_detection() -> None:
    """Start the background webcam capture and drowsiness detection thread."""
    global _running, _thread, _eye_closed_since

    if _running:
        return

    _eye_closed_since = None
    _running = True
    _thread = threading.Thread(target=_detection_loop, daemon=True)
    _thread.start()


def stop_detection() -> None:
    """Stop the detection thread and release the webcam."""
    global _running, _thread

    _running = False
    if _thread and _thread.is_alive():
        _thread.join(timeout=3.0)
    _thread = None

    with _state_lock:
        _drowsiness_state["status"]        = "NORMAL"
        _drowsiness_state["ear_value"]      = 0.0
        _drowsiness_state["closed_seconds"] = 0.0
        _drowsiness_state["face_detected"]  = False


def get_frame_with_overlay() -> np.ndarray:
    """Return the most recent webcam frame with face mesh and status overlay.

    Returns:
        A BGR numpy array (H x W x 3). Returns a blank frame if none available.
    """
    with _state_lock:
        if _latest_frame is not None:
            return _latest_frame.copy()
    return np.zeros((config.FRAME_HEIGHT, config.FRAME_WIDTH, 3), dtype=np.uint8)


def get_drowsiness_state() -> dict:
    """Return the current drowsiness detection state.

    Returns:
        dict with keys:
            status (str)         — "NORMAL" | "STAGE1" | "STAGE2" | "SMS"
            ear_value (float)    — current averaged EAR score
            closed_seconds (float) — continuous eye-closure duration in seconds
            face_detected (bool) — whether a face is visible in the frame
    """
    with _state_lock:
        return dict(_drowsiness_state)


# ---------------------------------------------------------------------------
# Standalone test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Starting detection — press 'q' to quit.")
    start_detection()
    time.sleep(1)

    try:
        while True:
            frame = get_frame_with_overlay()
            state = get_drowsiness_state()
            cv2.imshow("AlertEye — core.py test", frame)
            print(f"\r{state}", end="", flush=True)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    except KeyboardInterrupt:
        pass
    finally:
        stop_detection()
        cv2.destroyAllWindows()
        print("\nAGENT 1 DONE")
        print("Exposed functions:")
        print("  start_detection() -> None")
        print("  stop_detection() -> None")
        print("  get_frame_with_overlay() -> np.ndarray")
        print("  get_drowsiness_state() -> dict")
