import threading
import requests
import json
from alert import speak

OLLAMA_URL   = "http://127.0.0.1:11434/api/chat"
OLLAMA_MODEL = "llama3.2"

_history = []

SYSTEM_PROMPT = (
    "You are Smart Car, a friendly AI assistant built into a car. "
    "You help the driver stay entertained and informed during long drives. "
    "Keep responses short and conversational — the driver is focused on the road. "
    "Never ask the driver to look at a screen. Speak naturally as if talking to a friend."
)

def _call_ollama(user_text: str) -> str:
    global _history
    _history.append({"role": "user", "content": user_text})
    payload = {
        "model":    OLLAMA_MODEL,
        "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + _history,
        "stream":   False,
    }
    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=30)
        response.raise_for_status()
        reply = response.json()["message"]["content"].strip()
        _history.append({"role": "assistant", "content": reply})
        if len(_history) > 20:
            _history = _history[-20:]
        return reply
    except requests.exceptions.ConnectionError:
        return "Ollama server is not running. Please run ollama serve in a terminal."
    except Exception as e:
        print(f"[Chat] Ollama error: {e}")
        return "Sorry, I couldn't process that. Please try again."

def handle_chat(user_text: str):
    def _run():
        print(f"[Chat] User: {user_text}")
        reply = _call_ollama(user_text)
        print(f"[Chat] Smart Car: {reply}")
        speak(reply)
    threading.Thread(target=_run, daemon=True).start()

def reset_conversation():
    global _history
    _history = []
    print("[Chat] Conversation history cleared.")