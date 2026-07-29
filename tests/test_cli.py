import csv
import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from scrappy.cli import main


class ExplodingEnricher:
    def __init__(self, *args, **kwargs):
        pass

    def enrich(self, restaurant):
        raise RuntimeError("restaurant failed")


class CliTests(unittest.TestCase):
    def test_enrich_continues_and_writes_row_when_restaurant_crashes(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            input_path = Path(temp_dir) / "restaurants.csv"
            output_path = Path(temp_dir) / "out.csv"
            input_path.write_text("name,location\nCasa Paco,Gijón\n", encoding="utf-8")

            with (
                patch("scrappy.cli.load_dotenv", return_value=[]),
                patch.dict("os.environ", {"GOOGLE_PLACES_API_KEY": "fake"}, clear=True),
                patch("scrappy.cli.RestaurantEnricher", ExplodingEnricher),
                redirect_stdout(io.StringIO()),
            ):
                exit_code = main(["enrich", str(input_path), "--out", str(output_path)])

            self.assertEqual(exit_code, 0)
            rows = list(csv.DictReader(io.StringIO(output_path.read_text(encoding="utf-8"))))
            self.assertEqual(rows[0]["status"], "unexpected_error")
            self.assertIn("restaurant failed", rows[0]["notes"])


if __name__ == "__main__":
    unittest.main()
