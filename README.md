# FoodScrappy

[![Tests and Sonar](https://github.com/uriaFernando/FoodScrappy/actions/workflows/tests.yml/badge.svg?branch=main)](https://github.com/uriaFernando/FoodScrappy/actions/workflows/tests.yml)
[![Quality Gate Status](https://sonarcloud.io/api/project_badges/measure?project=uriaFernando_FoodScrappy&metric=alert_status)](https://sonarcloud.io/summary/new_code?id=uriaFernando_FoodScrappy)

Restaurant enrichment CLI that finds official websites, social profiles, and delivery platform links from restaurant CSV inputs using Google Places and Brave Search.

## Configuration

Copy `.env.example` to `.env` and fill in your real keys. `.env` is ignored by git.

```text
GOOGLE_PLACES_API_KEY=...
BRAVE_SEARCH_API_KEY=...
```

`BRAVE_SEARCH_API_KEY` is optional. Without it, the CLI still runs, but web-search fallback fields may remain empty.

## Usage

Prepare an input CSV with `name` and `location` columns:

```csv
name,location
Casa Paco,Gijón
```

Run enrichment:

```powershell
python -m scrappy enrich restaurants.csv --out enriched_restaurants.csv --region ES
```

The installable project is named `FoodScrappy`; the Python package and CLI module remain `scrappy` for stable imports and commands.

Useful options:

```powershell
python -m scrappy enrich restaurants.csv --out enriched_restaurants.csv --region ES --web-search-limit 600
python -m scrappy enrich restaurants.csv --out enriched_restaurants.csv --region ES --no-web-search-fallback
```

## Output

The output CSV contains:

```text
input_name,input_location,place_id,matched_name,matched_address,google_maps_url,website,instagram,facebook,tiktok,x_twitter,linkedin,uber_eats,just_eat,glovo,confidence,status,notes,social_score
```

`social_score` adds 1 point for each discovered website, social profile, or delivery platform link.

Common statuses:

- `ok`: restaurant matched and enrichment completed.
- `no_match`: no reliable Google Places match was found.
- `no_website`: Google Places did not return an official website.
- `places_error`: Google Places returned an API or network error.
- `unexpected_error`: an unexpected per-restaurant error was caught and logged.

## Tests

```powershell
python -m unittest discover
```

CI runs unit tests, generates `coverage.xml`, uploads it as an artifact, and sends static analysis plus coverage to SonarCloud.
