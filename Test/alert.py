import threading
import time
from elevenlabs.client import ElevenLabs
from elevenlabs import stream

client = ElevenLabs(api_key="sk_1c15f9436483d5e3b710e8d18ec90f60077f5415636769fa")

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
    time.sleep(5)