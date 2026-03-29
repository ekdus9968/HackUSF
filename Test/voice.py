import threading
import speech_recognition as sr

mic = sr.Microphone(device_index=0, sample_rate=16000, chunk_size=1024)

# Shared flag read by the main detection loop
stop_triggered = [False]


# Accept multiple variations for robustness
WAKE_WORDS = ["hey smart car", "hey car", "smart car", "hey smartcar"]

_chat_handler = None

def _listen_loop():
    r   = sr.Recognizer()
    mic = sr.Microphone()

    with mic as source:
        r.adjust_for_ambient_noise(source, duration=1)
    print("[Voice] Listener started — say 'stop' to dismiss alerts, 'hey smart car' to chat.")

    while True:
        try:
            with mic as source:
                audio = r.listen(source, timeout=3, phrase_time_limit=5)
            text = r.recognize_google(audio, language="en-US").lower()
            print(f"[Voice] Heard: '{text}'")

            if "stop" in text:
                stop_triggered[0] = True
            elif any(w in text for w in WAKE_WORDS):
                matched = next(w for w in WAKE_WORDS if w in text)
                query = text.split(matched, 1)[-1].strip()
                if query:
                    if _chat_handler:
                        _chat_handler(query)
                else:
                    _listen_for_query(r, mic)

        except sr.WaitTimeoutError:
            pass
        except sr.UnknownValueError:
            pass
        except Exception as e:
            print(f"[Voice] Error: {e}")

def _listen_for_query(r, mic):
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
    global _chat_handler
    _chat_handler = chat_handler
    t = threading.Thread(target=_listen_loop, daemon=True)
    t.start()

def consume_stop():
    if stop_triggered[0]:
        stop_triggered[0] = False
        return True
    return False