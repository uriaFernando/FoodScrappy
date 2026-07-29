"""Restaurant-to-Place matching utilities."""

from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher

from .models import Place, RestaurantInput


def normalize_text(value: str) -> str:
    """Normalize text for fuzzy matching and deduplication."""
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", re.sub(r"[^a-zA-Z0-9 ]+", " ", ascii_value)).strip().lower()


def score_place(candidate: Place, restaurant: RestaurantInput) -> float:
    """Score how well a Google Places candidate matches a restaurant input."""
    wanted_name = normalize_text(restaurant.name)
    candidate_name = normalize_text(candidate.display_name)
    wanted_location = normalize_text(restaurant.location)
    candidate_address = normalize_text(candidate.formatted_address)

    name_score = SequenceMatcher(None, wanted_name, candidate_name).ratio() if candidate_name else 0.0
    location_score = 0.0
    if wanted_location:
        location_score = 1.0 if wanted_location in candidate_address else SequenceMatcher(
            None, wanted_location, candidate_address
        ).ratio()
    type_score = 1.0 if candidate.primary_type == "restaurant" or "restaurant" in candidate.types else 0.0
    return round((name_score * 0.7) + (location_score * 0.2) + (type_score * 0.1), 4)


def choose_best_place(candidates: list[Place], restaurant: RestaurantInput) -> tuple[Place | None, float]:
    """Return the highest-scoring candidate and its confidence score."""
    if not candidates:
        return None, 0.0
    scored = [(candidate, score_place(candidate, restaurant)) for candidate in candidates]
    scored.sort(key=lambda item: item[1], reverse=True)
    return scored[0]
