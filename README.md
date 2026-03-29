# HackUSF
# Noctua — Driver Drowsiness Detection System

Real-time driver awareness system using computer vision, voice interaction, and AI-powered conversation.  
Built for HackUSF 2026.

---

## Overview

Noctua monitors driver alertness in real-time using a webcam. It detects eye closure and head pose, escalates through alert stages, notifies emergency contacts, and provides post-drive fatigue reports. Users can interact hands-free via voice commands and converse with an onboard AI assistant.

---

## Features

| Category | Feature |
|---|---|
| Detection | Eye closure (EAR), head pose (pitch), blink rate, PERCLOS, brow furrow |
| Alerts | 3-stage system — audio beep → warning sound → email + ElevenLabs voice |
| Voice | "stop" to dismiss alerts, "hey smart car" to chat with Ollama |
| AI Chat | Ollama (llama3.2) local LLM — works offline |
| Auth | Sign in / Create account / Guest mode (SQLite) |
| Calibration | Personalized per user — EAR threshold + head pitch baseline |
| Driver Profile | Weekly drive frequency, vision, glasses, sleep, caffeine, environment |
| Reports | Per-session matplotlib report + cumulative history (grade A–F) |
| Fatigue Signals | Blink rate, PERCLOS, brow furrow — terminal output |
| Email Alert | Gmail SMTP — sends on CRITICAL with contact info |
| UI | CustomTkinter dashboard with EAR ring, PERCLOS arc, alert log |
| Weather | WeatherAPI used for weather conditions on greeting |
| Traffic | TomTom for traffic conditions announced on greeting |

---

## Project Structure

```
noctua/
│
├── ui.py               # Main app window (CustomTkinter) — run this
├── detection.py        # Core detection loop (eye + head pose + alerts)
├── calibration.py      # EAR + pitch calibration (3-step)
├── constants.py        # Landmark indices, thresholds, EAR/pitch functions
│
├── auth.py             # SQLite auth — sign in, create account, driver profile
├── session.py          # Per-session data collection (5s snapshots)
├── report.py           # Matplotlib reports — single session + history
├── fatigue.py          # Blink rate, PERCLOS, brow furrow detector
│
├── voice.py            # Speech recognition — "stop" + wake word
├── chat.py             # Ollama LLM conversation
├── alert.py            # ElevenLabs TTS (blocking + async)
├── sound.py            # macOS afplay — beep.wav, warning.wav
├── sms.py              # Gmail SMTP emergency email
├── emergency.py        # Emergency contact input (OpenCV fallback)
├── weather_greeting.py # Weather + traffic context integration
│
├── config.py           # API keys, environment variables, configuration
├── constants.py        # Shared constants (thresholds, tuning params)
│
├── beep.wav            # Stage 1 alert sound
├── warning.wav         # Stage 2 alert sound
├── completion.wav      # Voice interaction completion sound
│
├── icons8-alert-100.png
├── icons8-closed-eye-100.png
├── icons8-eye-100.png
├── icons8-up-arrow-100.png
│
├── Noctua Logo with BG.png     # Branding asset
├── Noctua symbol no BG.png     # Transparent logo
├── Welcome To Noctua.mp4       # Welcome screen video
│
├── users.db            # SQLite database (auto-created)
├── .env                # Environment variables (API keys, secrets)
│
├── MuseoModerno/       # Custom font assets
├── Inter/              # Custom font assets
│
├── font_test.py        # Font rendering test
├── main.py             # Alternative entry point 
│
├── .gitignore
└── README.md
```
---

## Requirements

### Python packages

```bash
pip install opencv-python mediapipe numpy customtkinter pillow \
            SpeechRecognition pyaudio elevenlabs requests matplotlib
```

### Ollama (local LLM)

```bash
brew install ollama
ollama pull llama3.2
brew services start ollama   # auto-start on boot
```

### macOS Tk 8.6 (required for CustomTkinter)

```bash
brew install tcl-tk@8

CPPFLAGS="-I/opt/homebrew/opt/tcl-tk@8/include/tcl-tk" \
LDFLAGS="-L/opt/homebrew/opt/tcl-tk@8/lib" \
PYTHON_CONFIGURE_OPTS="--with-tcltk-includes=-I/opt/homebrew/opt/tcl-tk@8/include/tcl-tk \
  --with-tcltk-libs='-L/opt/homebrew/opt/tcl-tk@8/lib -ltcl8.6 -ltk8.6'" \
pyenv install 3.10.18 --force
```

---

## Setup

### 1. Gmail app password (for email alerts)

1. Go to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
2. Create an app password (16 chars)
3. Open `sms.py` and fill in:

```python
GMAIL_ADDRESS = "your@gmail.com"
GMAIL_APP_PW  = "xxxx xxxx xxxx xxxx"
```

### 2. ElevenLabs API key (for voice alerts)

Open `alert.py` and replace the API key:

```python
client = ElevenLabs(api_key="your_key_here")
```

### 3. Sound files

Place `beep.wav` and `warning.wav` in the project root.

### 4. Welcome video (optional)

Place `welcome.mp4` in the project root. If missing, a static logo screen is shown.

---

## Running

```bash
python main.py
```

---

## Alert Flow

```
Eyes closed / Head down
        │
    3 seconds ──► STAGE 1   beep.wav (repeats every 2s) + STOP button
        │
    Eyes open + no STOP ──► sound repeats until STOP pressed
        │
    5 seconds ──► STAGE 2   warning.wav (repeats) + STOP button
        │
    8 seconds ──► CRITICAL  Email sent + ElevenLabs voice warning
```

**Dismissing alerts:**
- Click `STOP ALARM` button on screen
- Say `"stop"` (voice command)

---

## Voice Commands

| Command | Action |
|---|---|
| `"stop"` / `"halt"` / `"cancel"` | Dismiss active alert |
| `"hey smart car"` | Wake AI assistant |
| `"hey car, [question]"` | Ask question directly |

---

## Database Schema

```sql
users (
    user_id              TEXT PRIMARY KEY,
    first_name           TEXT,
    last_name            TEXT,
    pw_hash              TEXT,       -- SHA-256
    personal_email       TEXT,
    emergency_email      TEXT,
    ear_threshold        REAL,       -- saved after calibration
    pitch_baseline       REAL,       -- saved after calibration
    -- Driver profile
    drive_frequency      TEXT,       -- daily / 2-3x/week / weekends / rarely
    vision_left          TEXT,       -- e.g. 20/20
    vision_right         TEXT,
    wears_glasses        TEXT,       -- no / glasses / contacts
    drive_time_of_day    TEXT,       -- morning / afternoon / evening / night / mixed
    avg_drive_duration   TEXT,       -- under30 / 30to120 / over120
    drive_environment    TEXT,       -- urban / highway / mixed
    avg_sleep_hours      TEXT,       -- under5 / 5to6 / 7to8 / over8
    caffeine_intake      TEXT        -- none / light / moderate / heavy
)

sessions (
    session_id           INTEGER PRIMARY KEY,
    user_id              TEXT,
    date                 TEXT,
    start_time           TEXT,
    end_time             TEXT,
    total_minutes        REAL,
    avg_fatigue          REAL,       -- 0–100
    worst_period_min     REAL,       -- minute into drive
    best_period_min      REAL,
    alert_1_count        INTEGER,
    alert_2_count        INTEGER,
    critical_count       INTEGER,
    perclos_avg          REAL,
    blink_rate_avg       REAL,
    timeline_json        TEXT        -- 5s snapshots: t, ear, pitch, blink, perclos, alert, score
)
```

---

## Report Grades

| Grade | Condition |
|---|---|
| A | Avg fatigue < 15 |
| B | Avg fatigue < 30 |
| C | Avg fatigue < 50 |
| D | Avg fatigue < 70 |
| F | Avg fatigue ≥ 70 or any CRITICAL event |

---

## Tech Stack

| Component | Technology |
|---|---|
| Computer vision | MediaPipe Face Mesh (468 landmarks) |
| UI | CustomTkinter |
| Database | SQLite (built-in) |
| Voice recognition | Google Speech Recognition (SpeechRecognition) |
| AI assistant | Ollama — llama3.2 (local) |
| TTS | ElevenLabs Turbo v2.5 |
| Graphs | Matplotlib |
| Audio playback | macOS `afplay` |
| Email | Gmail SMTP (smtplib) |
| Daily Report | Tomtom Weatherapi |

