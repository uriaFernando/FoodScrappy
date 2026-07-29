"""Brave Search fallback for discovering websites, social links, and delivery pages."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

from .matcher import normalize_text
from .models import DELIVERY_FIELDS, SOCIAL_FIELDS
from .social import extract_social_urls, first_socials


BRAVE_SEARCH_ENDPOINT = "https://api.search.brave.com/res/v1/web/search"
AGGREGATOR_HOST_PARTS = (
    "google.",
    "tripadvisor.",
    "thefork.",
    "eltenedor.",
    "just-eat.",
    "ubereats.",
    "glovoapp.",
    "deliveroo.",
    "booking.",
    "restaurantguru.",
    "minube.",
    "yelp.",
    "foursquare.",
    "facebook.",
    "instagram.",
    "tiktok.",
    "twitter.",
    "x.com",
    "linkedin.",
)


class WebSearchError(RuntimeError):
    """Raised when Brave Search cannot be reached or returns an error response."""

    pass


@dataclass(frozen=True)
class SearchResult:
    """Normalized web search result."""

    title: str
    link: str
    snippet: str = ""


@dataclass(frozen=True)
class BraveSearchClient:
    """Client for Brave Web Search API."""

    api_key: str
    timeout_seconds: float = 12.0

    def search(self, query: str, num: int = 5) -> list[SearchResult]:
        """Run a Brave Web Search query and return normalized organic results."""
        params = urllib.parse.urlencode(
            {
                "q": query,
                "count": min(max(num, 1), 10),
                "country": "es",
                "search_lang": "es",
                "safesearch": "moderate",
            }
        )
        request = urllib.request.Request(
            f"{BRAVE_SEARCH_ENDPOINT}?{params}",
            headers={
                "Accept": "application/json",
                "X-Subscription-Token": self.api_key,
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise WebSearchError(f"Brave Search devolvió HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise WebSearchError(f"No se pudo conectar con Brave Search: {exc.reason}") from exc

        if payload.get("error"):
            raise WebSearchError(f"Brave Search devolvió error: {payload['error']}")

        return [
            SearchResult(
                title=item.get("title", ""),
                link=item.get("url", ""),
                snippet=item.get("description", ""),
            )
            for item in (payload.get("web") or {}).get("results", [])
            if item.get("url")
        ]


def build_search_queries(name: str, location: str) -> list[str]:
    """Build the single quota-conscious fallback query for one restaurant."""
    place = "Gijon" if "gij" in normalize_text(location) else location
    return [
        f'"{name}" "{place}" (facebook OR instagram OR tiktok OR "web oficial" OR restaurante OR "uber eats" OR justeat OR glovo)',
    ]


def pick_official_website(results: list[SearchResult], restaurant_name: str) -> str:
    """Choose the most likely official website from search results."""
    scored: list[tuple[int, str]] = []
    normalized_name = normalize_text(restaurant_name)
    name_tokens = [token for token in normalized_name.split() if len(token) > 2]
    for result in results:
        link = _clean_url(result.link)
        if not link or _is_social_or_aggregator(link):
            continue
        haystack = normalize_text(f"{result.title} {result.link} {result.snippet}")
        score = 0
        if any(token in haystack for token in name_tokens):
            score += 2
        if "oficial" in haystack or "official" in haystack:
            score += 1
        if score > 0:
            scored.append((score, link))
    scored.sort(key=lambda item: item[0], reverse=True)
    return scored[0][1] if scored else ""


def extract_socials_from_search_results(results: list[SearchResult]) -> dict[str, str]:
    """Extract social profile URLs from web search results."""
    socials = first_socials(
        extract_social_urls(" ".join(f"{result.link} {result.title} {result.snippet}" for result in results))
    )
    return {field: socials.get(field, "") for field in SOCIAL_FIELDS}


def extract_delivery_from_search_results(results: list[SearchResult]) -> dict[str, str]:
    """Extract supported delivery platform URLs from web search results."""
    found = dict.fromkeys(DELIVERY_FIELDS, "")
    for result in results:
        field = _delivery_field_for_url(result.link)
        if field and not found[field]:
            found[field] = _clean_url(result.link)
    return found


def _clean_url(url: str) -> str:
    """Normalize a search result URL for CSV output."""
    parsed = urllib.parse.urlparse(url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    return urllib.parse.urlunparse((parsed.scheme, parsed.netloc.lower(), parsed.path or "/", "", "", ""))


def _is_social_or_aggregator(url: str) -> bool:
    """Return whether a URL should not be treated as an official website."""
    host = urllib.parse.urlparse(url).netloc.lower()
    host = host[4:] if host.startswith("www.") else host
    return any(re.search(rf"(^|\.){re.escape(part)}", host) for part in AGGREGATOR_HOST_PARTS)


def _delivery_field_for_url(url: str) -> str | None:
    """Map a delivery platform URL to an output field name."""
    host = urllib.parse.urlparse(url.strip()).netloc.lower()
    host = host[4:] if host.startswith("www.") else host
    if "ubereats." in host:
        return "uber_eats"
    if "just-eat." in host or "justeat." in host:
        return "just_eat"
    if "glovoapp." in host or host == "glovo.com" or host.endswith(".glovo.com"):
        return "glovo"
    return None
