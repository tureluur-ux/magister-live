import sys


def set_windows_startup(enabled: bool) -> None:
    if sys.platform != "win32":
        return
    import winreg

    key = winreg.OpenKey(
        winreg.HKEY_CURRENT_USER,
        r"Software\Microsoft\Windows\CurrentVersion\Run",
        0,
        winreg.KEY_SET_VALUE,
    )
    name = "MagisterLive"
    try:
        if enabled:
            exe = sys.executable
            script = __import__("os").path.abspath(__import__("sys").argv[0])
            command = f'"{exe}" "{script}"' if not getattr(sys, "frozen", False) else f'"{exe}"'
            winreg.SetValueEx(key, name, 0, winreg.REG_SZ, command)
        else:
            try:
                winreg.DeleteValue(key, name)
            except FileNotFoundError:
                pass
    finally:
        winreg.CloseKey(key)
