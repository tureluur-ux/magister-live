from dataclasses import dataclass
from typing import Any

from .storage import JsonStore


@dataclass
class AppConfig:
    school: str = ""
    username: str = ""
    startup: bool = False
    sound: bool = True

    @classmethod
    def load(cls, store: JsonStore) -> "AppConfig":
        values = store.get("settings", {})
        return cls(
            school=str(values.get("school", "")),
            username=str(values.get("username", "")),
            startup=bool(values.get("startup", False)),
            sound=bool(values.get("sound", True)),
        )

    def save(self, store: JsonStore) -> None:
        store.set("settings", {
            "school": self.school,
            "username": self.username,
            "startup": self.startup,
            "sound": self.sound,
        })
