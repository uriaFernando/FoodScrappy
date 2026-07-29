import csv
import io
import tempfile
import unittest
from pathlib import Path

from scrappy.csv_io import read_restaurants, write_results
from scrappy.models import EnrichmentResult


class CsvIoTests(unittest.TestCase):
    def test_read_restaurants_rejects_paths_outside_working_directory(self):
        outside_path = Path.cwd().parent / "restaurants.csv"

        with self.assertRaisesRegex(ValueError, "directorio de trabajo"):
            read_restaurants(outside_path)

    def test_write_results_rejects_paths_outside_working_directory(self):
        outside_path = Path.cwd().parent / "results.csv"

        with self.assertRaisesRegex(ValueError, "directorio de trabajo"):
            write_results(outside_path, [])

    def test_read_and_write_accept_paths_inside_working_directory(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            input_path = Path(temp_dir) / "restaurants.csv"
            output_path = Path(temp_dir) / "results.csv"
            input_path.write_text("name,location\nCasa Paco,Gijón\n", encoding="utf-8")

            restaurants = read_restaurants(input_path)
            write_results(
                output_path,
                [
                    EnrichmentResult(
                        input_name=restaurants[0].name,
                        input_location=restaurants[0].location,
                        website="https://example.com",
                    )
                ],
            )

            rows = list(csv.DictReader(io.StringIO(output_path.read_text(encoding="utf-8"))))
            self.assertEqual(rows[0]["input_name"], "Casa Paco")
            self.assertEqual(rows[0]["social_score"], "1")


if __name__ == "__main__":
    unittest.main()
