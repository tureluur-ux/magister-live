import customtkinter as ctk

from magister_notifier.app import MagisterNotifierApp


if __name__ == "__main__":
    ctk.set_appearance_mode("Dark")
    ctk.set_default_color_theme("blue")
    app = MagisterNotifierApp()
    app.mainloop()
