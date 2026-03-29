import threading
import time
import os
from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs
from elevenlabs import stream

load_dotenv()
client = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))

def speak(text):
    def _speak():
        audio = client.text_to_speech.convert(
            text=text,
            voice_id="JBFqnCBsd6RMkjVDRZzb",
            model_id="eleven_turbo_v2_5",
        )
        stream(audio)
    threading.Thread(target=_speak, daemon=True).start()

if __name__ == "__main__":
    speak("Warning! You have been driving with your eyes closed. Please pull over.")
    import time
    time.sleep(5)