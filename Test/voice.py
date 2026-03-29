import threading
import speech_recognition as sr

# main loop 
stop_triggered = [False]

def _listen_loop():
    r   = sr.Recognizer()
    mic = sr.Microphone(device_index=0, sample_rate=16000, chunk_size=1024)

    # noisy 
    with mic as source:
        r.adjust_for_ambient_noise(source, duration=1)

    print("[Voice] Voice Recognition Started — Say 'stop' to dismiss the notification.")

    while True:
        try:
            with mic as source:
                audio = r.listen(source, timeout=3, phrase_time_limit=3)
            text = r.recognize_google(audio, language="en-US").lower()
            print(f"[Voice] recognize: '{text}'")
            if "stop" in text:
                stop_triggered[0] = True
        except sr.WaitTimeoutError:
            pass
        except sr.UnknownValueError:
            pass
        except Exception as e:
            print(f"[Voice] Error: {e}")


def start_voice_listener():
    """Start speech recognition in a background thread."""
    t = threading.Thread(target=_listen_loop, daemon=True)
    t.start()


def consume_stop():
    """Read and reset the stop flag — called every frame within the detection loop."""
    if stop_triggered[0]:
        stop_triggered[0] = False
        return True
    return False