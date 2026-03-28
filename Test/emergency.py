import cv2
import numpy as np

def get_emergency_contact():
    """Emergency contact setup screen — ENTER to confirm, ESC to skip"""
    name  = ""
    email = ""
    field = 0   # 0 = name field, 1 = email field

    W, H = 640, 400

    while True:
        canvas = np.zeros((H, W, 3), dtype=np.uint8)

        # Title
        cv2.putText(canvas, "Emergency Contact Setup",
                    (80, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
        cv2.line(canvas, (60, 65), (580, 65), (100, 100, 100), 1)

        # Name field
        name_color = (0, 255, 255) if field == 0 else (180, 180, 180)
        cv2.putText(canvas, "Name:", (60, 130),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 200, 200), 1)
        cv2.rectangle(canvas, (60, 145), (580, 185), name_color, 2)
        cv2.putText(canvas, name + ("|" if field == 0 else ""),
                    (72, 175), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

        # Email field
        email_color = (0, 255, 255) if field == 1 else (180, 180, 180)
        cv2.putText(canvas, "Email:", (60, 230),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 200, 200), 1)
        cv2.rectangle(canvas, (60, 245), (580, 285), email_color, 2)
        cv2.putText(canvas, email + ("|" if field == 1 else ""),
                    (72, 275), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

        # Instructions
        cv2.putText(canvas, "ENTER: next / confirm    ESC: skip",
                    (100, 350), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (120, 120, 120), 1)

        cv2.imshow("Setup", canvas)
        key = cv2.waitKey(20) & 0xFF

        if key == 27:           # ESC — skip
            break
        elif key == 13:         # ENTER — next field or confirm
            if field == 0 and name:
                field = 1
            elif field == 1:
                break
        elif key == 8:          # BACKSPACE
            if field == 0:
                name = name[:-1]
            else:
                email = email[:-1]
        elif 32 <= key <= 126:  # printable character
            if field == 0:
                name += chr(key)
            else:
                email += chr(key)

    cv2.destroyWindow("Setup")
    return name.strip(), email.strip()