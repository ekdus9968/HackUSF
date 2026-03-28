import customtkinter as ctk

def get_emergency_contact():
    """Simple Tkinter dialog for emergency contact setup"""
    result = {"name": "", "email": ""}

    dialog = ctk.CTk()
    dialog.title("Emergency Contact Setup")
    dialog.geometry("400x280")
    dialog.configure(fg_color="#0D1219")
    dialog.resizable(False, False)

    ctk.CTkLabel(dialog, text="Emergency Contact Setup",
                 font=ctk.CTkFont(size=16, weight="bold"),
                 text_color="#F5A623").pack(pady=20)

    ctk.CTkLabel(dialog, text="Name:", text_color="#C8D8E8").pack(anchor="w", padx=40)
    name_entry = ctk.CTkEntry(dialog, width=320, placeholder_text="Contact name")
    name_entry.pack(padx=40, pady=(4, 12))

    ctk.CTkLabel(dialog, text="Email:", text_color="#C8D8E8").pack(anchor="w", padx=40)
    email_entry = ctk.CTkEntry(dialog, width=320, placeholder_text="Contact email")
    email_entry.pack(padx=40, pady=(4, 12))

    def confirm():
        result["name"]  = name_entry.get().strip()
        result["email"] = email_entry.get().strip()
        dialog.destroy()

    def skip():
        dialog.destroy()

    btn_row = ctk.CTkFrame(dialog, fg_color="transparent")
    btn_row.pack(pady=12)
    ctk.CTkButton(btn_row, text="Confirm", command=confirm,
                  fg_color="#F5A623", text_color="#000").pack(side="left", padx=8)
    ctk.CTkButton(btn_row, text="Skip", command=skip,
                  fg_color="#1A2332", text_color="#C8D8E8").pack(side="left", padx=8)

    dialog.mainloop()
    return result["name"], result["email"]