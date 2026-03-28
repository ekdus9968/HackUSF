import threading
import speech_recognition as sr

# Shared flag read by the main detection loop
stop_triggered = [False]

# Wake word for conversation mode
# Accept multiple variations for robustness
WAKE_WORDS = ["hey smart car", "hey car", "smart car", "hey smartcar"]

# Listening mode state
_chat_handler = None   # set by start_voice_listener()


def _listen_loop():
    r   = sr.Recognizer()
    mic = sr.Microphone()

    # Calibrate for ambient noise
    with mic as source:
        r.adjust_for_ambient_noise(source, duration=1)

    print("[Voice] Listener started — say 'stop' to dismiss alerts, 'hey smart car' to chat.")

    while True:
        try:
            with mic as source:
                audio = r.listen(source, timeout=3, phrase_time_limit=5)
            text = r.recognize_google(audio, language="en-US").lower()
            print(f"[Voice] Heard: '{text}'")

            # ── STOP alert ────────────────────────────────────────
            if "stop" in text:
                stop_triggered[0] = True

            # ── Wake word → chat mode ─────────────────────────────
            elif any(w in text for w in WAKE_WORDS):
                matched = next(w for w in WAKE_WORDS if w in text)
                query = text.split(matched, 1)[-1].strip()
                if query:
                    # Question was said together with wake word
                    if _chat_handler:
                        _chat_handler(query)
                else:
                    # Wake word only — listen for the follow-up question
                    _listen_for_query(r, mic)

        except sr.WaitTimeoutError:
            pass
        except sr.UnknownValueError:
            pass
        except Exception as e:
            print(f"[Voice] Error: {e}")


def _listen_for_query(r, mic):
    """Listen for a follow-up question after the wake word is detected"""
    from alert import speak
    speak("Yes?")
    print("[Voice] Wake word detected — listening for question...")
    try:
        with mic as source:
            audio = r.listen(source, timeout=5, phrase_time_limit=8)
        query = r.recognize_google(audio, language="en-US")
        print(f"[Voice] Question: '{query}'")
        if _chat_handler and query:
            _chat_handler(query)
    except sr.WaitTimeoutError:
        print("[Voice] No question heard after wake word.")
    except sr.UnknownValueError:
        print("[Voice] Could not understand the question.")
    except Exception as e:
        print(f"[Voice] Error listening for query: {e}")


def start_voice_listener(chat_handler=None):
    """Start voice recognition in a background daemon thread"""
    global _chat_handler
    _chat_handler = chat_handler
    t = threading.Thread(target=_listen_loop, daemon=True)
    t.start()


def consume_stop():
    """Read and reset the stop flag — call every frame from the detection loop"""
    if stop_triggered[0]:
        stop_triggered[0] = False
        return True
    return False