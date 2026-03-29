"""
brew install ollama
ollama serve
(open another terminal)
ollama pull llama3.2
"""

"""
chat.py — Conversational AI using Ollama (local, free)
Triggered by wake word "hey car" from voice.py
Run: ollama serve  (keep running in background)
     ollama pull llama3.2
"""

import threading
import requests
import json
from alert import speak

# ── Ollama settings ───────────────────────────────────────────────
OLLAMA_URL   = "http://127.0.0.1:11434/api/chat"
OLLAMA_MODEL = "llama3.2"
# ─────────────────────────────────────────────────────────────────

# Conversation history for multi-turn context
_history = []

SYSTEM_PROMPT = (
    "You are Smart Car, a friendly AI assistant built into a car. "
    "You help the driver stay entertained and informed during long drives. "
    "Keep responses short and conversational — the driver is focused on the road. "
    "Never ask the driver to look at a screen. Speak naturally as if talking to a friend."
)


def _call_ollama(user_text: str) -> str:
    """Send message to local Ollama and return text response"""
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

        # Keep history to last 10 turns to avoid memory bloat
        if len(_history) > 20:
            _history = _history[-20:]

        return reply

    except requests.exceptions.ConnectionError:
        return "Ollama server is not running. Please run 'ollama serve' in a terminal."
    except Exception as e:
        print(f"[Chat] Ollama error: {e}")
        return "Sorry, I couldn't process that. Please try again."


def handle_chat(user_text: str):
    """Called from voice.py after wake word — runs in background thread"""
    def _run():
        print(f"[Chat] User: {user_text}")
        reply = _call_ollama(user_text)
        print(f"[Chat] Smart Car: {reply}")
        speak(reply)
    threading.Thread(target=_run, daemon=True).start()


def reset_conversation():
    """Clear conversation history"""
    global _history
    _history = []
    print("[Chat] Conversation history cleared.")