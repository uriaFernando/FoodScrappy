"""CSV input and output helpers for the enrichment pipeline."""

from __future__ import annotations

import csv
from pathlib import Path

from .models import EnrichmentResult, RestaurantInput


OUTPUT_FIELDS = [
    "input_name",
    "input_location",
    "place_id",
    "matched_name",
    "matched_address",
    "google_maps_url",
    "website",
    "instagram",
    "facebook",
    "tiktok",
    "x_twitter",
    "linkedin",
    "uber_eats",
    "just_eat",
    "glovo",
    "confidence",
    "status",
    "notes",
    "social_score",
]


def read_restaurants(path: Path) -> list[RestaurantInput]:
    """Read restaurant inputs from a CSV containing ``name`` and ``location`` columns."""
    with path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        if reader.fieldnames is None:
            raise ValueError("El CSV no tiene cabecera.")

        fields = {field.strip().lower(): field for field in reader.fieldnames if field}
        if "name" not in fields:
            raise ValueError("El CSV debe incluir una columna 'name'.")
        if "location" not in fields:
            raise ValueError("El CSV debe incluir una columna 'location'.")

        rows: list[RestaurantInput] = []
        for row_number, row in enumerate(reader, start=2):
            name = (row.get(fields["name"]) or "").strip()
            location = (row.get(fields["location"]) or "").strip()
            if not name:
                raise ValueError(f"Fila {row_number}: 'name' está vacío.")
            rows.append(RestaurantInput(name=name, location=location))
        return rows


def write_results(path: Path, results: list[EnrichmentResult]) -> None:
    """Write enrichment results to CSV using the public output schema."""
    with path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        for result in results:
            writer.writerow(result.as_row())
