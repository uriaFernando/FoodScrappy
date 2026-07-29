"""Shared data models and output schema helpers."""

from __future__ import annotations

from dataclasses import dataclass, field


SOCIAL_FIELDS = ("instagram", "facebook", "tiktok", "x_twitter", "linkedin")
DELIVERY_FIELDS = ("uber_eats", "just_eat", "glovo")


@dataclass(frozen=True)
class RestaurantInput:
    """A restaurant row provided by the user input CSV."""

    name: str
    location: str


@dataclass(frozen=True)
class Place:
    """Minimal Google Places representation used by the scraper."""

    id: str
    display_name: str = ""
    formatted_address: str = ""
    google_maps_uri: str = ""
    website_uri: str = ""
    types: tuple[str, ...] = field(default_factory=tuple)
    primary_type: str = ""


@dataclass
class EnrichmentResult:
    """Complete output row produced for a single restaurant."""

    input_name: str
    input_location: str
    place_id: str = ""
    matched_name: str = ""
    matched_address: str = ""
    google_maps_url: str = ""
    website: str = ""
    instagram: str = ""
    facebook: str = ""
    tiktok: str = ""
    x_twitter: str = ""
    linkedin: str = ""
    uber_eats: str = ""
    just_eat: str = ""
    glovo: str = ""
    confidence: str = "0.00"
    status: str = "not_started"
    notes: str = ""
    social_score: str = "0"

    def as_row(self) -> dict[str, str]:
        """Return the result as a CSV-ready dictionary."""
        self.social_score = str(self.calculate_social_score())
        return {
            "input_name": self.input_name,
            "input_location": self.input_location,
            "place_id": self.place_id,
            "matched_name": self.matched_name,
            "matched_address": self.matched_address,
            "google_maps_url": self.google_maps_url,
            "website": self.website,
            "instagram": self.instagram,
            "facebook": self.facebook,
            "tiktok": self.tiktok,
            "x_twitter": self.x_twitter,
            "linkedin": self.linkedin,
            "uber_eats": self.uber_eats,
            "just_eat": self.just_eat,
            "glovo": self.glovo,
            "confidence": self.confidence,
            "status": self.status,
            "notes": self.notes,
            "social_score": self.social_score,
        }

    def calculate_social_score(self) -> int:
        """Count all discovered website, social, and delivery links."""
        return sum(
            1
            for value in (
                self.website,
                self.instagram,
                self.facebook,
                self.tiktok,
                self.x_twitter,
                self.linkedin,
                self.uber_eats,
                self.just_eat,
                self.glovo,
            )
            if value
        )
