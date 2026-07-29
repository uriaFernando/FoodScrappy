"""Social profile URL extraction and normalization utilities."""

from __future__ import annotations

import re
from collections.abc import Iterable
from urllib.parse import parse_qs, unquote, urlparse, urlunparse

from .models import SOCIAL_FIELDS


SOCIAL_HOSTS = {
    "instagram": ("instagram.com",),
    "facebook": ("facebook.com", "fb.com"),
    "tiktok": ("tiktok.com",),
    "x_twitter": ("x.com", "twitter.com"),
    "linkedin": ("linkedin.com",),
}

SOCIAL_URL_RE = re.compile(
    r"https?://(?:www\.)?(?:instagram\.com|facebook\.com|fb\.com|tiktok\.com|x\.com|twitter\.com|linkedin\.com)/[^\s\"'<>]+",
    re.IGNORECASE,
)


def extract_social_urls(text: str) -> dict[str, list[str]]:
    """Extract supported social profile URLs from arbitrary text or HTML."""
    found: dict[str, list[str]] = {field: [] for field in SOCIAL_FIELDS}
    for raw_url in SOCIAL_URL_RE.findall(text):
        field, normalized = normalize_social_url(raw_url)
        if field and normalized and normalized not in found[field]:
            found[field].append(normalized)
    return found


def merge_social_maps(maps: Iterable[dict[str, list[str]]]) -> dict[str, list[str]]:
    """Merge multiple social URL maps while preserving first-seen order."""
    merged: dict[str, list[str]] = {field: [] for field in SOCIAL_FIELDS}
    for social_map in maps:
        for field, urls in social_map.items():
            for url in urls:
                if url not in merged[field]:
                    merged[field].append(url)
    return merged


def normalize_social_url(raw_url: str) -> tuple[str | None, str | None]:
    """Normalize a raw social URL and classify the supported social network."""
    parsed = urlparse(unquote(raw_url.strip()))
    if not parsed.scheme or not parsed.netloc:
        return None, None

    host = parsed.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    path = re.sub(r"/+", "/", parsed.path).rstrip("/")
    path_parts = [part for part in path.split("/") if part]
    if not path_parts:
        return None, None

    field = _field_for_host(host)
    if field is None or _is_non_profile_url(field, path_parts, parsed.query):
        return None, None

    canonical_host = {
        "instagram": "instagram.com",
        "facebook": "facebook.com",
        "tiktok": "tiktok.com",
        "x_twitter": "x.com",
        "linkedin": "linkedin.com",
    }[field]
    normalized_path = "/" + "/".join(path_parts[:2] if field == "linkedin" else path_parts[:1])
    return field, urlunparse(("https", canonical_host, normalized_path, "", "", ""))


def first_socials(socials: dict[str, list[str]]) -> dict[str, str]:
    """Return the first URL for each supported social network."""
    return {field: (socials.get(field) or [""])[0] for field in SOCIAL_FIELDS}


def _field_for_host(host: str) -> str | None:
    """Map a hostname to an output social field."""
    for field, hosts in SOCIAL_HOSTS.items():
        if host in hosts or any(host.endswith(f".{allowed}") for allowed in hosts):
            return field
    return None


def _is_non_profile_url(field: str, path_parts: list[str], query: str) -> bool:
    """Filter share, embed, search, and content URLs that are not profiles."""
    first = path_parts[0].lower()
    if field == "instagram":
        return first in {"p", "reel", "reels", "stories", "explore", "accounts", "developer"}
    if field == "facebook":
        if first in {"sharer", "sharer.php", "plugins", "dialog", "events", "groups", "login"}:
            return True
        return "u" in parse_qs(query) and first in {"l.php"}
    if field == "tiktok":
        return first in {"tag", "music", "discover", "embed"} or not first.startswith("@")
    if field == "x_twitter":
        return first in {"intent", "share", "hashtag", "search", "i", "home"}
    if field == "linkedin":
        return first not in {"company", "school", "in", "showcase"}
    return False
