import threading
import mediapipe as mp
import cv2
from emergency import get_emergency_contact
from calibration import calibrate
from config import state
from detection import run
from ui import AlertEyeApp

if __name__ == "__main__":
    # Step 1 — emergency contact (Tkinter dialog)
    contact_name, contact_email = get_emergency_contact()
    state["contact_name"]  = contact_name
    state["contact_email"] = contact_email

    # Step 2 — calibration (cv2 window, runs before UI starts)
    cap = cv2.VideoCapture(0)
    with mp.solutions.face_mesh.FaceMesh(
        max_num_faces=1,
        refine_landmarks=True,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5
    ) as face_mesh:
        ear_threshold, pitch_baseline = calibrate(face_mesh, cap)
    cap.release()
    cv2.destroyAllWindows()

    state["ear_threshold"]   = ear_threshold
    state["pitch_baseline"]  = pitch_baseline

    # Step 3 — start detection thread
    detection_thread = threading.Thread(target=run, daemon=True)
    detection_thread.start()

    # Step 4 — start UI
    app = AlertEyeApp()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()