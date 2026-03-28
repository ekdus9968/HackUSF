import subprocess
import threading

def play_sound(path):
    """Play a sound file using macOS afplay (non-blocking)"""
    def _play():
        try:
            subprocess.Popen(["afplay", path])
        except Exception as e:
            print(f"[Sound Error] {path}: {e}")
    threading.Thread(target=_play, daemon=True).start()

def play_beep():
    play_sound("warning.wav")

def play_warning():
    play_sound("beep.wav")