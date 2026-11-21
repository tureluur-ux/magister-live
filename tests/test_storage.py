import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from unittest.mock import Mock

from magister_notifier.storage import JsonStore
from magister_notifier.magister_client import MagisterClient
from magister_notifier.models import ScheduleItem
from magister_notifier.auth import MagisterBrowserAuth, BrowserLoginError


class JsonStoreTests(unittest.TestCase):
    def test_school_url_is_normalized(self) -> None:
        self.assertEqual(
            MagisterBrowserAuth.normalize_school_url("schaersvoorde.magister.net"),
            "https://schaersvoorde.magister.net",
        )
        self.assertEqual(
            MagisterBrowserAuth.normalize_school_url("https://schaersvoorde.magister.net/"),
            "https://schaersvoorde.magister.net",
        )
        with self.assertRaises(BrowserLoginError):
            MagisterBrowserAuth.normalize_school_url("school")
    def test_settings_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with patch("magister_notifier.storage.Path.home", return_value=Path(directory)):
                store = JsonStore("test_app")
                store.set("settings", {"school": "Testschool", "sound": True})
                reloaded = JsonStore("test_app")
                self.assertEqual(reloaded.get("settings")["school"], "Testschool")

    def test_school_search_returns_unique_names(self) -> None:
        response = Mock()
        response.raise_for_status = Mock()
        response.json.return_value = [
            {"displayName": "School A"},
            {"displayName": "School B"},
            {"displayName": "School A"},
        ]
        with patch("magister_notifier.magister_client.requests.get", return_value=response):
            schools = MagisterClient.search_schools("School")
        self.assertEqual(schools, ["School A", "School B"])

    def test_schedule_item_round_trip(self) -> None:
        item = ScheduleItem(
            id="1",
            date="2026-11-21",
            start="2026-11-21T08:30:00",
            end="2026-11-21T09:20:00",
            subject="Informatica",
            location="Lokaal 12",
            has_homework=True,
        )
        restored = ScheduleItem(**item.__dict__)
        self.assertEqual(restored.subject, "Informatica")
        self.assertTrue(restored.has_homework)


if __name__ == "__main__":
    unittest.main()
