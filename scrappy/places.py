"""Google Places API client used for discovery and enrichment."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from .models import Place


class PlacesApiError(RuntimeError):
    """Raised when Google Places cannot be reached or returns an error response."""

    pass


@dataclass(frozen=True)
class GooglePlacesClient:
    """Small Google Places Web Service client backed by the standard library."""

    api_key: str
    language_code: str = "es"
    region_code: str | None = None
    timeout_seconds: float = 15.0

    def search_nearby_restaurants(
        self,
        latitude: float,
        longitude: float,
        radius_meters: float,
        max_results: int = 20,
        rank_preference: str = "POPULARITY",
    ) -> list[Place]:
        """Search restaurants near a latitude/longitude point."""
        body: dict[str, Any] = {
            "includedTypes": ["restaurant"],
            "maxResultCount": min(max(max_results, 1), 20),
            "rankPreference": rank_preference,
            "languageCode": self.language_code,
            "locationRestriction": {
                "circle": {
                    "center": {"latitude": latitude, "longitude": longitude},
                    "radius": radius_meters,
                }
            },
        }
        if self.region_code:
            body["regionCode"] = self.region_code

        payload = self._request_json(
            "https://places.googleapis.com/v1/places:searchNearby",
            method="POST",
            field_mask="places.id,places.displayName,places.formattedAddress,places.types,places.primaryType",
            body=body,
        )
        return [_place_from_json(item) for item in payload.get("places", [])]

    def search_text_places(
        self,
        query: str,
        location_restriction: dict[str, Any],
        page_size: int = 20,
        max_pages: int = 3,
        sleep_seconds: float = 0.0,
    ) -> list[Place]:
        """Run paginated Google Places Text Search queries."""
        places: list[Place] = []
        page_token: str | None = None
        for page_index in range(max_pages):
            body: dict[str, Any] = {
                "textQuery": query,
                "includedType": "restaurant",
                "strictTypeFiltering": False,
                "pageSize": min(max(page_size, 1), 20),
                "languageCode": self.language_code,
                "locationRestriction": location_restriction,
            }
            if self.region_code:
                body["regionCode"] = self.region_code
            if page_token:
                body["pageToken"] = page_token
                if sleep_seconds > 0:
                    time.sleep(sleep_seconds)

            payload = self._request_json(
                "https://places.googleapis.com/v1/places:searchText",
                method="POST",
                field_mask="places.id,places.displayName,places.formattedAddress,places.types,places.primaryType,nextPageToken",
                body=body,
            )
            places.extend(_place_from_json(item) for item in payload.get("places", []))
            page_token = payload.get("nextPageToken")
            if not page_token or page_index == max_pages - 1:
                break
        return places

    def search_restaurants(self, name: str, location: str, max_results: int = 5) -> list[Place]:
        """Find candidate Google Places records for a restaurant name and location."""
        body: dict[str, Any] = {
            "textQuery": f"{name} {location}".strip(),
            "includedType": "restaurant",
            "strictTypeFiltering": False,
            "languageCode": self.language_code,
        }
        if self.region_code:
            body["regionCode"] = self.region_code

        payload = self._request_json(
            "https://places.googleapis.com/v1/places:searchText",
            method="POST",
            field_mask="places.id,places.displayName,places.formattedAddress,places.googleMapsUri,places.types,places.primaryType",
            body=body,
        )
        return [_place_from_json(item) for item in payload.get("places", [])[:max_results]]

    def get_place_details(self, place_id: str) -> Place:
        """Fetch details for a Google Place ID."""
        payload = self._request_json(
            f"https://places.googleapis.com/v1/places/{place_id}",
            method="GET",
            field_mask="id,displayName,formattedAddress,googleMapsUri,websiteUri,types,primaryType",
        )
        return _place_from_json(payload)

    def _request_json(
        self,
        url: str,
        *,
        method: str,
        field_mask: str,
        body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Send an authenticated Places request and parse the JSON response."""
        data = json.dumps(body).encode("utf-8") if body is not None else None
        request = urllib.request.Request(
            url,
            data=data,
            method=method,
            headers={
                "Content-Type": "application/json",
                "X-Goog-Api-Key": self.api_key,
                "X-Goog-FieldMask": field_mask,
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise PlacesApiError(f"Google Places devolvió HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise PlacesApiError(f"No se pudo conectar con Google Places: {exc.reason}") from exc


def _place_from_json(payload: dict[str, Any]) -> Place:
    """Convert a Google Places API payload into a ``Place`` model."""
    display_name = payload.get("displayName") or {}
    return Place(
        id=payload.get("id", ""),
        display_name=display_name.get("text", ""),
        formatted_address=payload.get("formattedAddress", ""),
        google_maps_uri=payload.get("googleMapsUri", ""),
        website_uri=payload.get("websiteUri", ""),
        types=tuple(payload.get("types") or ()),
        primary_type=payload.get("primaryType", ""),
    )
