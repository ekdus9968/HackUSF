# Runs detection in a background thread and the UI in the main thread.
# Detection runs in a daemon thread so it dies automatically when UI closes.
import threading
from detection import run
from ui import AlertEyeApp
 
if __name__ == "__main__":
    # Start detection loop in background thread
    detection_thread = threading.Thread(target=run, daemon=True)
    detection_thread.start()
 
    # Start UI on main thread
    app = AlertEyeApp()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()
 