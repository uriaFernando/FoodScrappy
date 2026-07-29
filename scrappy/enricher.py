"""Restaurant enrichment orchestration across Places, crawling, and web search."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .crawler import WebsiteCrawler
from .matcher import choose_best_place
from .models import DELIVERY_FIELDS, EnrichmentResult, RestaurantInput, SOCIAL_FIELDS
from .places import GooglePlacesClient, PlacesApiError
from .social import first_socials
from .web_search import (
    BraveSearchClient,
    SearchResult,
    WebSearchError,
    build_search_queries,
    extract_delivery_from_search_results,
    extract_socials_from_search_results,
    pick_official_website,
)


@dataclass
class RestaurantEnricher:
    """Enrich one restaurant input with website, social, and delivery links."""

    places_client: GooglePlacesClient
    crawler: WebsiteCrawler
    web_search_client: BraveSearchClient | None = None
    web_search_limit: int = 600
    min_confidence: float = 0.45
    log: Callable[[str], None] | None = None
    web_searches_used: int = 0
    web_search_cache: dict[str, list[SearchResult]] | None = None

    def enrich(self, restaurant: RestaurantInput) -> EnrichmentResult:
        """Enrich a restaurant and always return a result row, even on errors."""
        result = EnrichmentResult(input_name=restaurant.name, input_location=restaurant.location)
        try:
            self._log("buscando candidatos en Google Places...")
            candidates = self.places_client.search_restaurants(restaurant.name, restaurant.location)
            self._log(f"Google Places devolvió {len(candidates)} candidatos.")
            match, confidence = choose_best_place(candidates, restaurant)
            result.confidence = f"{confidence:.2f}"
            if match is None or confidence < self.min_confidence:
                self._log(f"sin match fiable (confidence={confidence:.2f}).")
                result.status = "no_match"
                result.notes = "No se encontró un candidato suficientemente fiable en Google Places."
                return result

            self._log(f"match: {match.display_name} ({confidence:.2f}); pidiendo detalles...")
            place = self.places_client.get_place_details(match.id)
            result.place_id = place.id
            result.matched_name = place.display_name
            result.matched_address = place.formatted_address
            result.google_maps_url = place.google_maps_uri
            result.website = place.website_uri

            if place.website_uri:
                self._crawl_website_into_result(result, place.website_uri)
            else:
                self._log("Places no devolvió web oficial.")
                result.status = "no_website"
                result.notes = "Google Places no devolvió web oficial."

            if self._needs_web_search(result):
                self._apply_web_search_fallback(result)

            if result.status == "not_started":
                result.status = "ok"
            return result
        except PlacesApiError as exc:
            result.status = "places_error"
            result.notes = str(exc)
            self._log(f"error de Places: {exc}")
            return result
        except Exception as exc:
            result.status = "unexpected_error"
            result.notes = f"{type(exc).__name__}: {exc}"
            self._log(f"error inesperado: {type(exc).__name__}: {exc}")
            return result

    def _log(self, message: str) -> None:
        """Emit an optional enrichment-scoped log message."""
        if self.log is not None:
            self.log(f"[enrich]   {message}")

    def _crawl_website_into_result(self, result: EnrichmentResult, website_url: str) -> None:
        """Crawl a website and merge any discovered social links into a result."""
        self._log(f"rastreando web oficial: {website_url}")
        try:
            crawl = self.crawler.crawl(website_url)
        except Exception as exc:
            self._append_note(result, str(exc))
            self._log(f"crawler falló: {exc}")
            return
        visited_urls = getattr(crawl, "visited_urls", ())
        self._log(f"crawler visitó {len(visited_urls)} páginas.")
        socials = first_socials(crawl.socials)
        for field, value in socials.items():
            if value and not getattr(result, field):
                setattr(result, field, value)
        result.status = "ok"
        self._log(f"redes encontradas: {sum(1 for value in socials.values() if value)}.")
        if crawl.errors:
            self._append_note(result, " | ".join(crawl.errors[:3]))

    def _needs_web_search(self, result: EnrichmentResult) -> bool:
        """Return whether Brave fallback can add missing fields."""
        if self.web_search_client is None:
            if not result.website or any(not getattr(result, field) for field in SOCIAL_FIELDS):
                self._append_note(result, "Búsqueda web no configurada.")
            return False
        return (
            not result.website
            or any(not getattr(result, field) for field in SOCIAL_FIELDS)
            or any(not getattr(result, field) for field in DELIVERY_FIELDS)
        )

    def _apply_web_search_fallback(self, result: EnrichmentResult) -> None:
        """Use Brave Search once per restaurant to fill missing web-related fields."""
        assert self.web_search_client is not None
        name = result.matched_name or result.input_name
        location = result.matched_address or result.input_location
        self._log("buscando web/redes con Brave Search...")
        try:
            search_results = self._get_web_search_results(result, name, location)
            if search_results is None:
                return

            self._apply_website_from_search(result, search_results, name)
            self._apply_links_from_search(
                result,
                extract_socials_from_search_results(search_results),
                "redes",
                "Redes encontradas por búsqueda web.",
            )
            self._apply_links_from_search(
                result,
                extract_delivery_from_search_results(search_results),
                "plataformas de delivery",
                "Plataformas de delivery encontradas por búsqueda web.",
            )
        except Exception as exc:
            self._append_note(result, f"{type(exc).__name__}: {exc}")
            self._log(f"búsqueda web falló: {type(exc).__name__}: {exc}")

    def _get_web_search_results(
        self,
        result: EnrichmentResult,
        name: str,
        location: str,
    ) -> list[SearchResult] | None:
        """Return cached or newly fetched Brave results while enforcing the search limit."""
        assert self.web_search_client is not None
        if self.web_search_cache is None:
            self.web_search_cache = {}

        cache_key = self._web_search_cache_key(name, location)
        if cache_key in self.web_search_cache:
            self._log("Brave Search: usando resultados cacheados.")
            return self.web_search_cache[cache_key]
        if self.web_searches_used >= self.web_search_limit:
            self._append_note(result, "Límite de búsqueda web alcanzado.")
            self._log(f"Búsquedas Brave usadas: {self.web_searches_used}/{self.web_search_limit}.")
            return None

        query = build_search_queries(name, location)[0]
        self._log(f"Brave Search: {query}")
        search_results = self.web_search_client.search(query)
        self.web_search_cache[cache_key] = search_results
        self.web_searches_used += 1
        self._log(f"Búsquedas Brave usadas: {self.web_searches_used}/{self.web_search_limit}.")
        return search_results

    def _apply_website_from_search(
        self,
        result: EnrichmentResult,
        search_results: list[SearchResult],
        name: str,
    ) -> None:
        """Fill and crawl the official website if search found one and the result has none."""
        if result.website:
            return
        website = pick_official_website(search_results, name)
        if not website:
            return
        result.website = website
        result.status = "ok"
        self._append_note(result, "Web encontrada por búsqueda web.")
        self._crawl_website_into_result(result, website)

    def _apply_links_from_search(
        self,
        result: EnrichmentResult,
        links_by_field: dict[str, str],
        log_label: str,
        note: str,
    ) -> None:
        """Merge missing field links from search results into the output row."""
        found_count = 0
        for field, value in links_by_field.items():
            if value and not getattr(result, field):
                setattr(result, field, value)
                found_count += 1
        self._log(f"búsqueda web añadió {found_count} {log_label}.")
        if found_count:
            result.status = "ok"
            self._append_note(result, note)

    def _append_note(self, result: EnrichmentResult, note: str) -> None:
        """Append a note to a result without losing existing context."""
        if not note:
            return
        result.notes = f"{result.notes} | {note}" if result.notes else note

    def _web_search_cache_key(self, name: str, location: str) -> str:
        """Build the per-run cache key for fallback search results."""
        return f"{name}|{location}".strip().lower()
