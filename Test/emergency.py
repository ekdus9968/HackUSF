# =============================================================================
# emergency.py — Noctua emergency contact setup
# Cockpit aesthetic, matches auth.py and calibration.py
# =============================================================================

import sys
import customtkinter as ctk

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

BG     = "#080C12"
PANEL  = "#0D1219"
BORDER = "#1A2332"
AMBER  = "#F5A623"
GREEN  = "#00E87A"
RED    = "#FF3A3A"
TEXT   = "#C8D8E8"
TEXT2  = "#607080"
CARD   = "#0F1520"


def get_emergency_contact():
    """
    Shows emergency contact setup screen.
    Returns (name, email) — either filled or empty strings if skipped.
    """
    result = {"name": "", "email": ""}

    win = ctk.CTk()
    win.title("Noctua")
    win.configure(fg_color=BG)
    win.resizable(True, True)
    win.after(100, lambda: win.state("zoomed"))

    # ── Title bar ─────────────────────────────────────────────────────────────
    bar = ctk.CTkFrame(win, fg_color=PANEL, height=40, corner_radius=0,
                       border_width=1, border_color=BORDER)
    bar.pack(fill="x", side="top")
    bar.pack_propagate(False)

    ctk.CTkLabel(bar, text="Noctua",
                 font=ctk.CTkFont(family="Courier", size=13, weight="bold"),
                 text_color=AMBER).pack(side="left", padx=16)

    ctk.CTkLabel(bar, text="EMERGENCY CONTACT SETUP",
                 font=ctk.CTkFont(family="Courier", size=11),
                 text_color=TEXT2).pack(side="left", padx=8)

    ctk.CTkLabel(bar, text="STEP 3 OF 4",
                 font=ctk.CTkFont(family="Courier", size=10),
                 text_color=TEXT2).pack(side="right", padx=16)

    # ── Centered card ─────────────────────────────────────────────────────────
    outer = ctk.CTkFrame(win, fg_color=BG)
    outer.pack(fill="both", expand=True)

    card = ctk.CTkFrame(outer, fg_color=CARD, corner_radius=16,
                        border_width=1, border_color=BORDER,
                        width=520, height=520)
    card.place(relx=0.5, rely=0.5, anchor="center")
    card.pack_propagate(False)

    inner = ctk.CTkFrame(card, fg_color="transparent")
    inner.place(relx=0.5, rely=0.5, anchor="center")

    # Icon
    ctk.CTkLabel(inner, text="🚨",
                 font=ctk.CTkFont(size=52)).pack(pady=(0, 8))

    # Title
    ctk.CTkLabel(inner, text="EMERGENCY CONTACT",
                 font=ctk.CTkFont(family="Courier", size=22, weight="bold"),
                 text_color=AMBER).pack(pady=(0, 4))

    # Subtitle
    ctk.CTkLabel(inner,
                 text="If a critical alert fires, we'll notify this person.",
                 font=ctk.CTkFont(family="Courier", size=10),
                 text_color=TEXT2).pack(pady=(0, 28))

    # Name field
    ctk.CTkLabel(inner, text="CONTACT NAME",
                 font=ctk.CTkFont(family="Courier", size=9),
                 text_color=TEXT2).pack(anchor="w")

    name_entry = ctk.CTkEntry(
        inner,
        placeholder_text="e.g. Jane Smith",
        font=ctk.CTkFont(family="Courier", size=13),
        fg_color=PANEL, border_color=BORDER, border_width=1,
        text_color=TEXT, placeholder_text_color=TEXT2,
        width=380, height=42, corner_radius=6
    )
    name_entry.pack(pady=(4, 16))

    # Email field
    ctk.CTkLabel(inner, text="CONTACT EMAIL",
                 font=ctk.CTkFont(family="Courier", size=9),
                 text_color=TEXT2).pack(anchor="w")

    email_entry = ctk.CTkEntry(
        inner,
        placeholder_text="e.g. jane@gmail.com",
        font=ctk.CTkFont(family="Courier", size=13),
        fg_color=PANEL, border_color=BORDER, border_width=1,
        text_color=TEXT, placeholder_text_color=TEXT2,
        width=380, height=42, corner_radius=6
    )
    email_entry.pack(pady=(4, 8))

    # Error label
    err_lbl = ctk.CTkLabel(inner, text="",
                           font=ctk.CTkFont(family="Courier", size=10),
                           text_color=RED)
    err_lbl.pack(pady=(0, 16))

    # Buttons
    def confirm():
        name  = name_entry.get().strip()
        email = email_entry.get().strip()
        if not name and not email:
            err_lbl.configure(text="Please enter at least a name or email.")
            return
        result["name"]  = name
        result["email"] = email
        win.after(10, win.destroy)

    def skip():
        win.after(10, win.destroy)

    ctk.CTkButton(
        inner, text="SAVE CONTACT",
        command=confirm,
        font=ctk.CTkFont(family="Courier", size=12, weight="bold"),
        fg_color=AMBER, hover_color="#E8920D",
        text_color="#000000",
        width=380, height=42, corner_radius=6
    ).pack(pady=(0, 10))

    ctk.CTkButton(
        inner, text="Skip for now",
        command=skip,
        font=ctk.CTkFont(family="Courier", size=11),
        fg_color="transparent", hover_color=PANEL,
        text_color=TEXT2,
        border_width=1, border_color=BORDER,
        width=380, height=38, corner_radius=6
    ).pack()

    ctk.CTkLabel(inner,
                 text="You can update this later in settings.",
                 font=ctk.CTkFont(family="Courier", size=9),
                 text_color=BORDER).pack(pady=(16, 0))

    win.bind("<Return>", lambda e: confirm())
    name_entry.focus()
    win.mainloop()

    return result["name"], result["email"]