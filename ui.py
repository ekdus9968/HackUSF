# Dependencies:
#   - customtkinter  : modern dark-themed Tkinter wrapper
#   - opencv-python  : webcam frame capture
#   - Pillow         : converts OpenCV frames to Tkinter-compatible images
#   - config.py      : shared state dict read/written by all modules

import customtkinter as ctk
import cv2
from PIL import Image, ImageTk

from config import state

# Theme & color constants
# Cockpit instrument panel aesthetic — dark bg, amber accents, status colors.
# All colors defined here so they're easy to tweak in one place.
 
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")
 
BG     = "#080C12"   # main window background
PANEL  = "#0D1219"   # sidebar / panel background
BORDER = "#1A2332"   # subtle border color
AMBER  = "#F5A623"   # primary accent — EAR value, headings
RED    = "#FF3A3A"   # danger — Stage 2 alert, stop button
GREEN  = "#00E87A"   # safe — monitoring state, good EAR
TEXT   = "#C8D8E8"   # primary text
TEXT2  = "#607080"   # secondary / muted text