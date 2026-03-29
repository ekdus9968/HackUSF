import customtkinter as ctk

root = ctk.CTk()

label = ctk.CTkLabel(
    root,
    text="NOCTURA",
    font=ctk.CTkFont(family="MuseoModerno", size=30, weight="bold")
)
label.pack(pady=50)

root.mainloop()