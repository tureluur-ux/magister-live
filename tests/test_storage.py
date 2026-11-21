import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from magister_notifier.storage import JsonStore


class JsonStoreTests(unittest.TestCase):
    def test_settings_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with patch("magister_notifier.storage.Path.home", return_value=Path(directory)):
                store = JsonStore("test_app")
                store.set("settings", {"school": "Testschool", "sound": True})
                reloaded = JsonStore("test_app")
                self.assertEqual(reloaded.get("settings")["school"], "Testschool")


if __name__ == "__main__":
    unittest.main()
