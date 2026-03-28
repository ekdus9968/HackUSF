# AlertEye — Project Memory

## Product
Real-time driver drowsiness detection desktop app.
Uses webcam + AI to detect eye closure, head pose, and yawning.
Triggers staged audio alarms and sends emergency SMS.

## Target User
Drivers (long-distance, night driving)
Platform: Mac M1 + Windows — installable .app / .exe

---

## Tech Stack
| Layer          | Library                    |
|----------------|----------------------------|
| Face detection | MediaPipe Face Mesh        |
| Camera         | OpenCV                     |
| Detection      | EAR + MAR + Head Pose      |
| UI             | Tkinter                    |
| Sound          | pygame                     |
| SMS            | Twilio API                 |
| Data           | CSV + JSON                 |
| Build          | PyInstaller                |
| Language       | Python 3.x                 |

---

## File Structure
```
alerteye/
├── CLAUDE.md
├── config.py          ← single source of truth (DONE)
├── core.py            ← face detection + EAR (Agent 1)
├── ui.py              ← Tkinter UI (Agent 2)
├── alert.py           ← sound + SMS (Agent 3)
├── detector.py        ← head pose + yawn (Phase 2)
├── calibration.py     ← personal EAR baseline (Phase 3)
├── session.py         ← session data + CSV (Phase 4)
├── main.py            ← entry point, connects all
├── assets/
│   ├── beep.wav
│   └── alarm.wav
├── data/
│   ├── user_profile.json
│   └── sessions.csv
└── alerts.log
```

---

## Config (config.py) — Already Done
All agents must import from config.py.
Never hardcode values in any other file.

Key values:
- EAR_THRESHOLD = 0.25 (overridden by calibration)
- STAGE1_SECONDS = 3
- STAGE2_SECONDS = 5
- SMS_SECONDS = 8
- SMS_COOLDOWN = 60
- LEFT_EYE_IDX / RIGHT_EYE_IDX — MediaPipe indices
- STATUS_COLORS — NORMAL/STAGE1/STAGE2/SMS
- WINDOW_WIDTH = 860, WINDOW_HEIGHT = 520

---

## Alert Logic
```
Eyes normal            → NORMAL  🟢
Eyes closed 3s+        → STAGE1  🟡  short beep
Eyes closed 5s+        → STAGE2  🔴  loud alarm loop
Eyes closed 8s+        → SMS     📱  Twilio auto-send
Head nodding down      → STAGE1  🟡  (even if eyes open)
Head tilting sideways  → STAGE1  🟡
Yawn detected          → log + increment yawn counter
User presses Stop      → NORMAL  🟢  all sounds stop
```

---

## Combined Drowsiness Score
EAR score + Head angle score + Yawn count = final risk level
All three feed into a single status: NORMAL / STAGE1 / STAGE2 / SMS

---

## Agent Contracts

### core.py must expose:
```python
def start_detection() -> None
def stop_detection() -> None
def get_frame_with_overlay() -> np.ndarray
def get_drowsiness_state() -> dict
# {
#   "status": "NORMAL"|"STAGE1"|"STAGE2"|"SMS",
#   "ear_value": float,
#   "closed_seconds": float,
#   "face_detected": bool
# }
```

### alert.py must expose:
```python
def trigger_alert(stage: str) -> None
def stop_alarm() -> None
def send_emergency_sms(contact: str, seconds: float) -> None
```

### ui.py must expose:
```python
def launch_app() -> None
```

### detector.py must expose:
```python
def get_head_pose(landmarks) -> dict
# { "pitch": float, "nodding": bool, "tilting": bool }
def get_yawn_state(landmarks) -> dict
# { "mar_value": float, "is_yawning": bool }
```

### calibration.py must expose:
```python
def run_calibration(duration_seconds=5) -> float
# returns personal EAR baseline
def load_profile() -> dict
def save_profile(ear_baseline: float) -> None
```

### session.py must expose:
```python
def start_session() -> None
def end_session() -> dict
# returns session summary dict
def log_event(status: str, ear: float, seconds: float) -> None
def export_csv() -> str
# returns filepath of exported CSV
def get_personal_pattern() -> dict
# {
#   "avg_drowsy_after_minutes": float,
#   "riskiest_hour": int,
#   "total_sessions": int
# }
```

---

## UI Layout
```
┌─────────────────────────────────────┐
│              AlertEye               │
├──────────────────┬──────────────────┤
│                  │ Status: NORMAL 🟢│
│  Live webcam     │ EAR:  0.32       │
│  feed with       │ Head: straight   │
│  landmarks       │ Yawns: 0         │
│                  │ Alerts: 0        │
│                  │ Drive: 00:12:34  │
├──────────────────┴──────────────────┤
│ Sensitivity:  [ Low ──●── High ]    │
│ Emergency:    [ +821012345678     ] │
├─────────────────────────────────────┤
│ [▶ Start]  [⚙ Calibrate]  [🔕 Stop]│
└─────────────────────────────────────┘
```

---

## Development Phases
- [x] config.py        DONE
- [ ] Phase 1: core.py + ui.py + alert.py + main.py
- [ ] Phase 2: detector.py (head pose + yawn)
- [ ] Phase 3: calibration.py
- [ ] Phase 4: session.py (CSV + pattern analysis)

---

## Rules for All Agents
1. Import all settings from config.py — never hardcode
2. Add docstrings to every function
3. Handle all exceptions gracefully — never hard crash
4. After writing, run the file to verify no errors
5. Fix all errors automatically without asking
6. Do not ask questions — make reasonable decisions
7. When done: print "AGENT [N] DONE" and list exposed functions