import json
from pathlib import Path
from typing import Any


class JsonStore:
    """Stores application configuration and synchronization state in JSON."""

    def __init__(self, name: str = "magister_notifier") -> None:
        base = Path.home() / "AppData" / "Local" if __import__("os").name == "nt" else Path.home() / ".local" / "share"
        self.directory = base / name
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / "data.json"
        self._data = self._load()

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {
                "settings": {"school": "", "username": "", "startup": False, "sound": True},
                "grades": [],
                "homework": [],
                "schedule": [],
                "notifications": [],
            }
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value
        self.save()

    def save(self) -> None:
        temp = self.path.with_suffix(".tmp")
        temp.write_text(json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(self.path)
