import smtplib
from email.mime.text import MIMEText

# ── Gmail 설정 ────────────────────────────────────────────────────
# 구글 계정 → 보안 → 2단계 인증 ON → 앱 비밀번호 생성 (16자리)
GMAIL_ADDRESS = "kan.seyoung1018@gmail.com"
GMAIL_APP_PW  = "ltig udtk lsds ilum"
# ─────────────────────────────────────────────────────────────────

def send_critical_alert(contact_name: str, contact_email: str):
    """CRITICAL state: sending email"""
    if not contact_email:
        print("[Alert] no saved email — skip sending")
        return

    try:
        msg = MIMEText(
            f"[Tiredness Tracker warning]\n\n"
            f"emergency contract: {contact_name} ({contact_email})\n\n"
            f"drowsy driving.\n"
            f"please chek."
        )
        msg["Subject"] = "drowsy driving CRITICAL Warning"
        msg["From"]    = GMAIL_ADDRESS
        msg["To"]      = contact_email

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_ADDRESS, GMAIL_APP_PW)
            server.send_message(msg)

        print(f"[Alert] Success → {contact_email}")
    except Exception as e:
        print(f"[Alert] Fail: {e}")