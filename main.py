import customtkinter as ctk
import sys
import traceback

from magister_notifier.app import MagisterLiveApp


if __name__ == "__main__":
    try:
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")
        app = MagisterLiveApp()
        app.mainloop()
    except Exception:
        from tkinter import Tk, messagebox
        root = Tk()
        root.withdraw()
        messagebox.showerror(
            "Magister Live - opstartfout",
            "De applicatie kon niet worden gestart.\n\n" + traceback.format_exc(),
        )
        root.destroy()
