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

# main application class

class AlertEyeApp(ctk.CTk):
    """
    Main window class. Inherits from ctk.CTk (customtkinter's root window).
    Builds the full UI layout and runs a 33ms update loop for the webcam feed.
    """
 
    def __init__(self):
        super().__init__()
 
        # Window configuration 
        self.title("AlertEye — Driver Monitoring System")
        self.geometry("860x520")       # width x height in pixels
        self.resizable(False, False)   # lock size so layout doesn't break
        self.configure(fg_color=BG)    # set background to cockpit dark color
 
        # Camera initialization 
        # Index 1 for built-in MacBook webcam.
        self.cap = cv2.VideoCapture(1)
 
        # Build UI then start the update loop
        self._build_ui()
        self._update()    # starts the 33ms webcam + state refresh loop
 