"""
alert.py — Sound and SMS alert system for AlertEye.

Exposes:
    trigger_alert(stage: str) -> None
    stop_alarm() -> None
    send_emergency_sms(contact: str, seconds: float) -> None
"""

import os
import time
import logging
import struct
import wave
from datetime import datetime

import pygame

import config

# ---------------------------------------------------------------------------
# Logging setup — append to alerts.log beside this file
# ---------------------------------------------------------------------------

_LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "alerts.log")

logging.basicConfig(
    filename=_LOG_PATH,
    level=logging.INFO,
    format="%(asctime)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
_log = logging.getLogger("alerteye")

# ---------------------------------------------------------------------------
# Pygame mixer — initialise once on import
# ---------------------------------------------------------------------------

try:
    pygame.mixer.pre_init(frequency=44100, size=-16, channels=1, buffer=512)
    pygame.mixer.init()
    _MIXER_OK = True
except Exception as exc:
    print(f"[alert] pygame mixer init failed: {exc}. Sound disabled.")
    _MIXER_OK = False

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

_last_sms_time: float = 0.0   # epoch seconds of most-recent SMS
_alarm_channel: "pygame.mixer.Channel | None" = None

# ---------------------------------------------------------------------------
# Sound helpers
# ---------------------------------------------------------------------------


def _ensure_assets_dir() -> None:
    """Create assets/ directory if it does not exist."""
    assets = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
    os.makedirs(assets, exist_ok=True)


def _write_wav(path: str, frequency: float, duration: float, amplitude: int = 16000) -> None:
    """Generate a simple sine-wave WAV file programmatically."""
    import math

    sample_rate = 44100
    n_samples = int(sample_rate * duration)
    samples = []
    for i in range(n_samples):
        value = int(amplitude * math.sin(2 * math.pi * frequency * i / sample_rate))
        samples.append(value)

    with wave.open(path, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)
        wf.writeframes(struct.pack(f"<{n_samples}h", *samples))


def _ensure_sound_file(path: str, frequency: float, duration: float) -> bool:
    """Return True if *path* exists (or was just generated successfully)."""
    if os.path.exists(path):
        return True
    try:
        _ensure_assets_dir()
        _write_wav(path, frequency, duration)
        print(f"[alert] Generated missing sound file: {path}")
        return True
    except Exception as exc:
        print(f"[alert] Could not generate {path}: {exc}")
        return False


def _load_sound(path: str, frequency: float, duration: float) -> "pygame.mixer.Sound | None":
    """Load a pygame Sound, generating the file if necessary."""
    if not _MIXER_OK:
        return None
    if not _ensure_sound_file(path, frequency, duration):
        return None
    try:
        return pygame.mixer.Sound(path)
    except Exception as exc:
        print(f"[alert] Could not load sound {path}: {exc}")
        return None


# Lazy-loaded sound objects
_sound_stage1: "pygame.mixer.Sound | None" = None
_sound_stage2: "pygame.mixer.Sound | None" = None


def _get_sound_stage1() -> "pygame.mixer.Sound | None":
    global _sound_stage1
    if _sound_stage1 is None:
        _sound_stage1 = _load_sound(config.SOUND_STAGE1, frequency=880.0, duration=0.4)
    return _sound_stage1


def _get_sound_stage2() -> "pygame.mixer.Sound | None":
    global _sound_stage2
    if _sound_stage2 is None:
        _sound_stage2 = _load_sound(config.SOUND_STAGE2, frequency=440.0, duration=1.0)
    return _sound_stage2


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def trigger_alert(stage: str) -> None:
    """Play the appropriate alert sound for *stage*.

    Args:
        stage: One of "STAGE1", "STAGE2", or "SMS".
               STAGE1 → single short beep.
               STAGE2 / SMS → loud alarm loops continuously.
    """
    global _alarm_channel

    _log.info("ALERT triggered — stage=%s", stage)

    if not _MIXER_OK:
        print(f"[alert] Sound disabled. Alert stage: {stage}")
        return

    if stage == "STAGE1":
        snd = _get_sound_stage1()
        if snd:
            try:
                stop_alarm()  # stop any ongoing alarm first
                snd.play()
            except Exception as exc:
                print(f"[alert] STAGE1 sound play error: {exc}")

    elif stage in ("STAGE2", "SMS"):
        snd = _get_sound_stage2()
        if snd:
            try:
                # Only start loop if not already looping
                if _alarm_channel is None or not _alarm_channel.get_busy():
                    _alarm_channel = snd.play(loops=-1)  # -1 = loop forever
            except Exception as exc:
                print(f"[alert] STAGE2 sound play error: {exc}")

    else:
        print(f"[alert] Unknown stage: {stage!r}")


def stop_alarm() -> None:
    """Immediately silence ALL sounds and reset alarm state."""
    global _alarm_channel

    if not _MIXER_OK:
        return

    try:
        pygame.mixer.stop()
    except Exception as exc:
        print(f"[alert] Error stopping sounds: {exc}")

    _alarm_channel = None
    _log.info("ALARM stopped")


def send_emergency_sms(contact: str, seconds: float) -> None:
    """Send (or mock) an emergency SMS to *contact*.

    Respects SMS_COOLDOWN — silently skips if called too soon after a
    previous send.

    Args:
        contact: Destination phone number in E.164 format (e.g. "+821012345678").
        seconds: How many seconds the driver has been detected as drowsy.
    """
    global _last_sms_time

    if not contact:
        print("[alert] No emergency contact set — SMS skipped.")
        _log.warning("SMS skipped — no contact configured")
        return

    now = time.time()
    if now - _last_sms_time < config.SMS_COOLDOWN:
        remaining = config.SMS_COOLDOWN - (now - _last_sms_time)
        print(f"[alert] SMS cooldown active — {remaining:.0f}s remaining.")
        return

    message = (
        f"AlertEye WARNING: Driver drowsy for {seconds:.0f}s. "
        "Please check on them immediately."
    )

    # Mock mode when Twilio credentials are absent
    if not config.TWILIO_SID or not config.TWILIO_TOKEN or not config.TWILIO_FROM:
        print(f"[SMS MOCK] To: {contact} — drowsy for {seconds:.1f}s")
        _log.info("SMS MOCK → %s | %.1fs drowsy", contact, seconds)
        _last_sms_time = now
        return

    # Real Twilio send
    try:
        from twilio.rest import Client  # type: ignore

        client = Client(config.TWILIO_SID, config.TWILIO_TOKEN)
        client.messages.create(
            body=message,
            from_=config.TWILIO_FROM,
            to=contact,
        )
        print(f"[alert] SMS sent to {contact}")
        _log.info("SMS sent → %s | %.1fs drowsy", contact, seconds)
        _last_sms_time = now

    except ImportError:
        print("[alert] twilio package not installed. Falling back to mock SMS.")
        print(f"[SMS MOCK] To: {contact} — drowsy for {seconds:.1f}s")
        _log.warning("SMS MOCK (twilio not installed) → %s | %.1fs drowsy", contact, seconds)
        _last_sms_time = now

    except Exception as exc:
        print(f"[alert] SMS send failed: {exc}")
        _log.error("SMS FAILED → %s | error: %s", contact, exc)


# ---------------------------------------------------------------------------
# Standalone smoke-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=== alert.py standalone test ===")

    print("1) trigger_alert('STAGE1') — should play short beep")
    trigger_alert("STAGE1")
    time.sleep(1)

    print("2) trigger_alert('STAGE2') — should loop alarm")
    trigger_alert("STAGE2")
    time.sleep(2)

    print("3) stop_alarm()")
    stop_alarm()
    time.sleep(0.5)

    print("4) send_emergency_sms (mock — no credentials)")
    send_emergency_sms("+821012345678", 9.5)

    print("5) send_emergency_sms again — should hit cooldown")
    send_emergency_sms("+821012345678", 11.0)

    print("\nAGENT 3 DONE")
    print("Exposed functions:")
    print("  trigger_alert(stage: str) -> None")
    print("  stop_alarm() -> None")
    print("  send_emergency_sms(contact: str, seconds: float) -> None")
