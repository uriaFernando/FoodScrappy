import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scrappy.env import load_dotenv


class EnvTests(unittest.TestCase):
    def test_load_dotenv_sets_missing_values(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            env_path.write_text('GOOGLE_PLACES_API_KEY="abc"\nBRAVE_SEARCH_API_KEY=brave\n', encoding="utf-8")

            with patch.dict(os.environ, {}, clear=True):
                loaded = load_dotenv(env_path)

                self.assertEqual(loaded, ["GOOGLE_PLACES_API_KEY", "BRAVE_SEARCH_API_KEY"])
                self.assertEqual(os.environ["GOOGLE_PLACES_API_KEY"], "abc")
                self.assertEqual(os.environ["BRAVE_SEARCH_API_KEY"], "brave")

    def test_load_dotenv_does_not_override_existing_environment(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            env_path.write_text("GOOGLE_PLACES_API_KEY=file-value\n", encoding="utf-8")

            with patch.dict(os.environ, {"GOOGLE_PLACES_API_KEY": "existing"}, clear=True):
                loaded = load_dotenv(env_path)

                self.assertEqual(loaded, [])
                self.assertEqual(os.environ["GOOGLE_PLACES_API_KEY"], "existing")


if __name__ == "__main__":
    unittest.main()
