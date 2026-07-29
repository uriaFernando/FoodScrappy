"""Small same-domain website crawler used to discover social profile links."""

from __future__ import annotations

import html.parser
import socket
import urllib.error
import urllib.parse
import urllib.request
from collections import deque
from dataclasses import dataclass, field

from .social import extract_social_urls, merge_social_maps


CRAWL_HINTS = ("contact", "contacto", "about", "sobre", "reserv", "menu", "carta", "legal")


@dataclass(frozen=True)
class CrawlResult:
    """Result of crawling a restaurant website."""

    socials: dict[str, list[str]]
    visited_urls: tuple[str, ...]
    errors: tuple[str, ...] = ()


@dataclass
class WebsiteCrawler:
    """Fetch a limited number of same-domain pages from a restaurant website."""

    max_pages: int = 5
    timeout_seconds: float = 12.0
    user_agent: str = "FoodScrappy/0.1 (+https://example.invalid)"

    def crawl(self, start_url: str) -> CrawlResult:
        """Crawl ``start_url`` and return discovered social profiles and recoverable errors."""
        start = _ensure_scheme(start_url)
        start_host = _canonical_host(urllib.parse.urlparse(start).netloc)
        queue: deque[str] = deque([start])
        seen: set[str] = set()
        visited: list[str] = []
        errors: list[str] = []
        social_maps: list[dict[str, list[str]]] = []

        while queue and len(visited) < self.max_pages:
            url = queue.popleft()
            normalized_url = _strip_fragment(url)
            if normalized_url in seen:
                continue
            seen.add(normalized_url)

            page = self._crawl_page(normalized_url, start_host, seen, is_home_page=not visited)
            if page.error:
                errors.append(page.error)
                continue

            visited.append(normalized_url)
            social_maps.append(page.socials)
            queue.extend(page.links)

        return CrawlResult(
            socials=merge_social_maps(social_maps),
            visited_urls=tuple(visited),
            errors=tuple(errors),
        )

    def _fetch(self, url: str) -> str:
        """Download a single HTML page and return decoded text."""
        request = urllib.request.Request(url, headers={"User-Agent": self.user_agent})
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                content_type = response.headers.get("Content-Type", "")
                if "text/html" not in content_type and "application/xhtml+xml" not in content_type:
                    raise RuntimeError(f"{url}: contenido no HTML ({content_type or 'sin content-type'}).")
                charset = response.headers.get_content_charset() or "utf-8"
                return response.read(1_500_000).decode(charset, errors="replace")
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"{url}: HTTP {exc.code}.") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"{url}: error de red: {exc.reason}.") from exc
        except TimeoutError as exc:
            raise RuntimeError(f"{url}: timeout al leer respuesta.") from exc
        except socket.timeout as exc:
            raise RuntimeError(f"{url}: timeout de red.") from exc

    def _crawl_page(self, url: str, start_host: str, seen: set[str], *, is_home_page: bool) -> "PageCrawl":
        """Fetch one page and return its socials, outgoing crawl links, or error."""
        try:
            html = self._fetch(url)
        except RuntimeError as exc:
            return PageCrawl(error=str(exc))

        parser = LinkParser()
        parser.feed(html)
        return PageCrawl(
            socials=extract_social_urls(html),
            links=_crawlable_links(
                parser.links,
                base_url=url,
                start_host=start_host,
                seen=seen,
                is_home_page=is_home_page,
            ),
        )


@dataclass(frozen=True)
class PageCrawl:
    """Intermediate result for one fetched website page."""

    socials: dict[str, list[str]] = field(default_factory=dict)
    links: tuple[str, ...] = ()
    error: str = ""


class LinkParser(html.parser.HTMLParser):
    """Extract navigable links from HTML anchor and link tags."""

    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Collect ``href`` attributes from tags that can point to crawlable pages."""
        if tag.lower() not in {"a", "link"}:
            return
        for name, value in attrs:
            if value and name.lower() == "href":
                self.links.append(value)


def _ensure_scheme(url: str) -> str:
    """Add an HTTPS scheme when a URL-like value omits one."""
    parsed = urllib.parse.urlparse(url)
    return url if parsed.scheme else f"https://{url}"


def _strip_fragment(url: str) -> str:
    """Remove URL fragments and normalize empty paths."""
    parsed = urllib.parse.urlparse(url)
    return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, parsed.path or "/", "", parsed.query, ""))


def _canonical_host(host: str) -> str:
    """Normalize host names for same-domain comparisons."""
    lowered = host.lower()
    return lowered[4:] if lowered.startswith("www.") else lowered


def _looks_useful_page(url: str) -> bool:
    """Return whether a URL path looks useful for social-link discovery."""
    lowered = url.lower()
    return any(hint in lowered for hint in CRAWL_HINTS)


def _is_fetchable_href(href: str) -> bool:
    """Return whether an href value is safe and useful to fetch."""
    stripped = href.strip()
    if not stripped or any(character.isspace() for character in stripped):
        return False
    lowered = stripped.lower()
    return not lowered.startswith(("mailto:", "tel:", "javascript:", "data:", "#"))


def _crawlable_links(
    hrefs: list[str],
    *,
    base_url: str,
    start_host: str,
    seen: set[str],
    is_home_page: bool,
) -> tuple[str, ...]:
    """Normalize and filter page links that should be queued for crawling."""
    return tuple(
        absolute
        for href in hrefs
        if (absolute := _normalize_crawl_href(href, base_url, start_host, seen))
        and (_looks_useful_page(absolute) or is_home_page)
    )


def _normalize_crawl_href(href: str, base_url: str, start_host: str, seen: set[str]) -> str:
    """Return a normalized same-domain crawl URL, or an empty string if it should be skipped."""
    if not _is_fetchable_href(href):
        return ""

    absolute = _strip_fragment(urllib.parse.urljoin(base_url, href))
    parsed = urllib.parse.urlparse(absolute)
    if parsed.scheme not in {"http", "https"}:
        return ""
    if _canonical_host(parsed.netloc) != start_host:
        return ""
    if absolute in seen:
        return ""
    return absolute
