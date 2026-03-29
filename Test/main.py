import sys
import subprocess
import json
import threading
import mediapipe as mp
import cv2
from config import state
from detection import run
from ui import AlertEyeApp

if __name__ == "__main__":
    # Run auth in a separate subprocess to avoid cv2/Tkinter conflict
    result = subprocess.run(
        [sys.executable, "auth_runner.py"],
        capture_output=True, text=True
    )

    if result.returncode != 0:
        print("Auth failed or cancelled.")
        exit()

    user = json.loads(result.stdout.strip())
    if not user:
        exit()

    state["user"] = user

    # Emergency contact
    if user["user_id"] == "guest" or not user.get("emergency_email"):
        from emergency import get_emergency_contact
        contact_name, contact_email = get_emergency_contact()
    else:
        contact_name  = f"{user['first_name']} {user['last_name']}"
        contact_email = user["emergency_email"]

    state["contact_name"]  = contact_name
    state["contact_email"] = contact_email

    # Calibration
    from calibration import calibrate
    from auth import save_calibration
    cap = cv2.VideoCapture(0, cv2.CAP_AVFOUNDATION)
    with mp.solutions.face_mesh.FaceMesh(
        max_num_faces=1, refine_landmarks=True,
        min_detection_confidence=0.5, min_tracking_confidence=0.5
    ) as face_mesh:
        if user.get("needs_calibration") or user.get("ear_threshold") is None:
            ear_threshold, pitch_baseline = calibrate(face_mesh, cap)
            if user["user_id"] != "guest":
                save_calibration(user["user_id"], ear_threshold, pitch_baseline)
        else:
            ear_threshold  = user["ear_threshold"]
            pitch_baseline = user["pitch_baseline"]
            print(f"[Auth] Loaded calibration — EAR: {ear_threshold:.3f}")

    cap.release()
    cv2.destroyAllWindows()

    state["ear_threshold"]  = ear_threshold
    state["pitch_baseline"] = pitch_baseline

    # Detection thread + UI
    threading.Thread(target=run, daemon=True).start()
    app = AlertEyeApp()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()