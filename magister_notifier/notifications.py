import sys
import winsound


class NotificationService:
    def __init__(self, sound_enabled: bool = True) -> None:
        self.sound_enabled = sound_enabled

    def set_sound(self, enabled: bool) -> None:
        self.sound_enabled = enabled

    def show(self, title: str, message: str) -> None:
        if sys.platform == "win32":
            try:
                from plyer import notification
                notification.notify(
                    title=title,
                    message=message,
                    app_name="Magister Live",
                    timeout=10,
                )
            except Exception:
                try:
                    from win10toast import ToastNotifier
                    ToastNotifier().show_toast(title, message, duration=10, threaded=True)
                except Exception:
                    pass
        if self.sound_enabled and sys.platform == "win32":
            try:
                winsound.MessageBeep(winsound.MB_ICONASTERISK)
            except Exception:
                pass
