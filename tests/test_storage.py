import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from unittest.mock import Mock

from magister_notifier.storage import JsonStore
from magister_notifier.magister_client import MagisterClient
from magister_notifier.models import ScheduleItem, schedule_item_from_dict


class JsonStoreTests(unittest.TestCase):
    def test_school_url_is_normalized(self) -> None:
        self.assertEqual(
            MagisterClient.normalize_school("schaersvoorde.magister.net"),
            ("schaersvoorde.magister.net", "schaersvoorde"),
        )
        self.assertEqual(
            MagisterClient.normalize_school("schaersvoorde"),
            ("schaersvoorde", "schaersvoorde"),
        )
        with self.assertRaises(ValueError):
            MagisterClient.normalize_school("school.example.org")

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

    def test_login_uses_schaersvoorde_tenant(self) -> None:
        with patch("MagisterPy.MagisterSession") as session_type:
            session_type.return_value.login.return_value = True
            client = MagisterClient(
                "schaersvoorde",
                "student-user",
                "test-password",
            )
            self.assertTrue(client.login())
            session_type.return_value.login.assert_called_once_with(
                school_name="schaersvoorde",
                username="student-user",
                password="test-password",
            )

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

    def test_migrates_legacy_magister_schedule_cache(self) -> None:
        item = schedule_item_from_dict({
            "Id": 42,
            "Start": "2026-11-25T08:30:00",
            "Einde": "2026-11-25T09:20:00",
            "Omschrijving": "Les",
            "Lokatie": "Lokaal 12",
            "Vakken": [{"Naam": "Informatica"}],
            "Docenten": [{"Naam": "Docent"}],
            "OpdrachtId": 123,
        })
        self.assertEqual(item.id, "42")
        self.assertEqual(item.date, "2026-11-25")
        self.assertEqual(item.subject, "Informatica")
        self.assertEqual(item.location, "Lokaal 12")
        self.assertTrue(item.has_homework)


if __name__ == "__main__":
    unittest.main()
