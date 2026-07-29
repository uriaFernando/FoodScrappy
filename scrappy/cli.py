"""Command-line interface for restaurant enrichment workflows."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from .crawler import WebsiteCrawler
from .csv_io import read_restaurants, write_results
from .env import load_dotenv
from .enricher import RestaurantEnricher
from .models import EnrichmentResult
from .places import GooglePlacesClient
from .web_search import BraveSearchClient


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level argument parser used by ``python -m scrappy``."""
    parser = argparse.ArgumentParser(prog="python -m scrappy")
    subparsers = parser.add_subparsers(dest="command", required=True)

    enrich = subparsers.add_parser("enrich", help="Enriquece restaurantes con web y redes sociales.")
    enrich.add_argument("input_csv", type=Path, help="CSV con columnas name y location.")
    enrich.add_argument("--out", required=True, type=Path, help="Ruta del CSV de salida.")
    enrich.add_argument("--api-key", default=None, help="Google Places API key. Si se omite, usa el entorno.")
    enrich.add_argument("--language", default="es", help="Código de idioma para Google Places.")
    enrich.add_argument("--region", default=None, help="Código regional opcional para Google Places, por ejemplo ES.")
    enrich.add_argument("--max-pages", type=int, default=5, help="Máximo de páginas a rastrear por web.")
    enrich.add_argument("--min-confidence", type=float, default=0.45, help="Score mínimo para aceptar un match.")
    enrich.add_argument("--brave-search-key", default=None, help="Brave Search API key para búsqueda web.")
    enrich.add_argument("--web-search-limit", type=int, default=600, help="Máximo de búsquedas web por ejecución.")
    enrich.add_argument(
        "--no-web-search-fallback",
        action="store_true",
        help="Desactiva el fallback de búsqueda web aunque existan credenciales.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the CLI and return a process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "enrich":
        return _run_enrich(args)
    parser.error(f"Comando desconocido: {args.command}")
    return 2


def _run_enrich(args: argparse.Namespace) -> int:
    """Execute the CSV enrichment command."""
    loaded_env = load_dotenv()
    if loaded_env:
        _log(f"[enrich] Variables cargadas desde .env: {', '.join(loaded_env)}")

    api_key = args.api_key or os.getenv("GOOGLE_PLACES_API_KEY") or os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key:
        raise SystemExit(
            "Falta API key. Define GOOGLE_PLACES_API_KEY o usa --api-key con una clave de Google Places."
        )

    _log(f"[enrich] Leyendo restaurantes desde {args.input_csv}")
    restaurants = read_restaurants(args.input_csv)
    _log(f"[enrich] Cargados {len(restaurants)} restaurantes.")
    search_api_key = args.brave_search_key or os.getenv("BRAVE_SEARCH_API_KEY")
    web_search_client = None
    if args.no_web_search_fallback:
        _log("[enrich] Fallback de búsqueda web desactivado por CLI.")
    elif search_api_key:
        web_search_client = BraveSearchClient(api_key=search_api_key)
        _log("[enrich] Fallback de búsqueda web activado con Brave Search.")
    else:
        _log("[enrich] Fallback de búsqueda web no configurado.")

    enricher = RestaurantEnricher(
        places_client=GooglePlacesClient(
            api_key=api_key,
            language_code=args.language,
            region_code=args.region,
        ),
        crawler=WebsiteCrawler(max_pages=args.max_pages),
        web_search_client=web_search_client,
        web_search_limit=args.web_search_limit,
        min_confidence=args.min_confidence,
        log=_log,
    )
    results = []
    for index, restaurant in enumerate(restaurants, start=1):
        _log(f"[enrich] {index}/{len(restaurants)}: {restaurant.name} ({restaurant.location})...")
        try:
            result = enricher.enrich(restaurant)
        except Exception as exc:
            result = EnrichmentResult(
                input_name=restaurant.name,
                input_location=restaurant.location,
                status="unexpected_error",
                notes=f"{type(exc).__name__}: {exc}",
            )
            _log(f"[enrich] ERROR inesperado en {restaurant.name}: {type(exc).__name__}: {exc}")
        results.append(result)
        _log(
            f"[enrich] {index}/{len(restaurants)} terminado: "
            f"status={result.status}, score={result.calculate_social_score()}, website={'si' if result.website else 'no'}."
        )
        if result.notes:
            _log(f"[enrich] Nota: {result.notes}")

    _log(f"[enrich] Escribiendo CSV: {args.out}")
    write_results(args.out, results)
    print(f"Procesados {len(results)} restaurantes. Resultado: {args.out}")
    return 0


def _log(message: str) -> None:
    """Print a progress message immediately to the terminal."""
    print(message, flush=True)
