import unittest

from scrappy.enricher import RestaurantEnricher
from scrappy.models import EnrichmentResult, Place, RestaurantInput


class FakePlacesClient:
    def __init__(self, detail):
        self.detail = detail

    def search_restaurants(self, name, location):
        return [Place(id="abc", display_name=name, formatted_address=location, types=("restaurant",))]

    def get_place_details(self, place_id):
        return self.detail


class ExplodingPlacesClient:
    def search_restaurants(self, name, location):
        raise ValueError("boom")


class FakeCrawler:
    def crawl(self, start_url):
        raise AssertionError("Crawler should not run without website.")


class EmptyCrawler:
    def crawl(self, start_url):
        class Result:
            socials = {
                "instagram": [],
                "facebook": [],
                "tiktok": [],
                "x_twitter": [],
                "linkedin": [],
            }

            visited_urls = (start_url,)
            errors = ()

        return Result()


class FailingCrawler:
    def crawl(self, start_url):
        raise RuntimeError(f"{start_url}: timeout al leer respuesta.")


class FakeSocialCrawler:
    def crawl(self, start_url):
        class Result:
            socials = {
                "instagram": ["https://instagram.com/casapaco"],
                "facebook": [],
                "tiktok": ["https://tiktok.com/@casapaco"],
                "x_twitter": [],
                "linkedin": [],
            }

            errors = ()

        return Result()


class FakeWebSearchClient:
    def __init__(self, links):
        self.links = links
        self.queries = []

    def search(self, query):
        from scrappy.web_search import SearchResult

        self.queries.append(query)
        return [SearchResult(title="Casa Paco", link=link, snippet="web oficial") for link in self.links]


class ExplodingWebSearchClient:
    def search(self, query):
        raise ValueError("brave boom")


class EnricherTests(unittest.TestCase):
    def test_no_website_status(self):
        enricher = RestaurantEnricher(
            places_client=FakePlacesClient(
                Place(
                    id="abc",
                    display_name="Casa Paco",
                    formatted_address="Madrid",
                    google_maps_uri="https://maps.google.com/?cid=1",
                    website_uri="",
                    types=("restaurant",),
                )
            ),
            crawler=FakeCrawler(),
        )

        result = enricher.enrich(RestaurantInput(name="Casa Paco", location="Madrid"))

        self.assertEqual(result.status, "no_website")
        self.assertEqual(result.instagram, "")
        self.assertEqual(result.calculate_social_score(), 0)
        self.assertIn("Búsqueda web no configurada", result.notes)

    def test_social_score_counts_website_and_found_social_profiles(self):
        enricher = RestaurantEnricher(
            places_client=FakePlacesClient(
                Place(
                    id="abc",
                    display_name="Casa Paco",
                    formatted_address="Madrid",
                    google_maps_uri="https://maps.google.com/?cid=1",
                    website_uri="https://casapaco.test",
                    types=("restaurant",),
                )
            ),
            crawler=FakeSocialCrawler(),
        )

        result = enricher.enrich(RestaurantInput(name="Casa Paco", location="Madrid"))

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.calculate_social_score(), 3)
        self.assertEqual(result.as_row()["social_score"], "3")

    def test_social_score_counts_delivery_platforms(self):
        enrichment = EnrichmentResult(
            input_name="Casa Paco",
            input_location="Madrid",
            website="https://casapaco.test",
            uber_eats="https://ubereats.com/store/casa-paco",
            just_eat="https://just-eat.es/restaurants-casa-paco",
            glovo="https://glovoapp.com/es/gijon/casa-paco",
        )

        self.assertEqual(enrichment.calculate_social_score(), 4)

    def test_web_search_fallback_finds_facebook_when_places_has_no_website(self):
        enricher = RestaurantEnricher(
            places_client=FakePlacesClient(
                Place(
                    id="abc",
                    display_name="Casa Paco",
                    formatted_address="Gijón",
                    google_maps_uri="https://maps.google.com/?cid=1",
                    website_uri="",
                    types=("restaurant",),
                )
            ),
            crawler=EmptyCrawler(),
            web_search_client=FakeWebSearchClient(["https://www.facebook.com/casapaco"]),
        )

        result = enricher.enrich(RestaurantInput(name="Casa Paco", location="Gijón"))

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.facebook, "https://facebook.com/casapaco")
        self.assertEqual(result.calculate_social_score(), 1)

    def test_web_search_fallback_finds_delivery_platforms(self):
        enricher = RestaurantEnricher(
            places_client=FakePlacesClient(
                Place(
                    id="abc",
                    display_name="Casa Paco",
                    formatted_address="Gijón",
                    google_maps_uri="https://maps.google.com/?cid=1",
                    website_uri="",
                    types=("restaurant",),
                )
            ),
            crawler=EmptyCrawler(),
            web_search_client=FakeWebSearchClient(
                [
                    "https://www.ubereats.com/es/store/casa-paco/abc",
                    "https://www.just-eat.es/restaurants-casa-paco-gijon/menu",
                    "https://glovoapp.com/es/es/gijon/casa-paco/",
                ]
            ),
        )

        result = enricher.enrich(RestaurantInput(name="Casa Paco", location="Gijón"))

        self.assertEqual(result.uber_eats, "https://www.ubereats.com/es/store/casa-paco/abc")
        self.assertEqual(result.just_eat, "https://www.just-eat.es/restaurants-casa-paco-gijon/menu")
        self.assertEqual(result.glovo, "https://glovoapp.com/es/es/gijon/casa-paco/")
        self.assertEqual(result.calculate_social_score(), 3)

    def test_web_search_fallback_runs_when_website_has_missing_socials(self):
        enricher = RestaurantEnricher(
            places_client=FakePlacesClient(
                Place(
                    id="abc",
                    display_name="Casa Paco",
                    formatted_address="Gijón",
                    google_maps_uri="https://maps.google.com/?cid=1",
                    website_uri="https://casapaco.test",
                    types=("restaurant",),
                )
            ),
            crawler=EmptyCrawler(),
            web_search_client=FakeWebSearchClient(["https://instagram.com/casapaco"]),
        )

        result = enricher.enrich(RestaurantInput(name="Casa Paco", location="Gijón"))

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.instagram, "https://instagram.com/casapaco")
        self.assertEqual(result.calculate_social_score(), 2)

    def test_crawler_failure_from_fallback_website_does_not_crash_enrichment(self):
        enricher = RestaurantEnricher(
            places_client=FakePlacesClient(
                Place(
                    id="abc",
                    display_name="Casa Paco",
                    formatted_address="Gijón",
                    google_maps_uri="https://maps.google.com/?cid=1",
                    website_uri="",
                    types=("restaurant",),
                )
            ),
            crawler=FailingCrawler(),
            web_search_client=FakeWebSearchClient(["https://casapaco.test/"]),
        )

        result = enricher.enrich(RestaurantInput(name="Casa Paco", location="Gijón"))

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.website, "https://casapaco.test/")
        self.assertIn("timeout", result.notes)

    def test_web_search_fallback_uses_one_search_per_restaurant(self):
        web_search_client = FakeWebSearchClient(["https://www.facebook.com/casapaco"])
        enricher = RestaurantEnricher(
            places_client=FakePlacesClient(
                Place(
                    id="abc",
                    display_name="Casa Paco",
                    formatted_address="Gijón",
                    google_maps_uri="https://maps.google.com/?cid=1",
                    website_uri="",
                    types=("restaurant",),
                )
            ),
            crawler=EmptyCrawler(),
            web_search_client=web_search_client,
        )

        enricher.enrich(RestaurantInput(name="Casa Paco", location="Gijón"))

        self.assertEqual(len(web_search_client.queries), 1)
        self.assertIn("facebook OR instagram OR tiktok", web_search_client.queries[0])

    def test_web_search_cache_avoids_duplicate_requests(self):
        web_search_client = FakeWebSearchClient(["https://www.facebook.com/casapaco"])
        enricher = RestaurantEnricher(
            places_client=FakePlacesClient(
                Place(
                    id="abc",
                    display_name="Casa Paco",
                    formatted_address="Gijón",
                    google_maps_uri="https://maps.google.com/?cid=1",
                    website_uri="",
                    types=("restaurant",),
                )
            ),
            crawler=EmptyCrawler(),
            web_search_client=web_search_client,
        )

        enricher.enrich(RestaurantInput(name="Casa Paco", location="Gijón"))
        enricher.enrich(RestaurantInput(name="Casa Paco", location="Gijón"))

        self.assertEqual(len(web_search_client.queries), 1)
        self.assertEqual(enricher.web_searches_used, 1)

    def test_web_search_limit_adds_note_without_searching(self):
        web_search_client = FakeWebSearchClient(["https://www.facebook.com/casapaco"])
        enricher = RestaurantEnricher(
            places_client=FakePlacesClient(
                Place(
                    id="abc",
                    display_name="Casa Paco",
                    formatted_address="Gijón",
                    google_maps_uri="https://maps.google.com/?cid=1",
                    website_uri="",
                    types=("restaurant",),
                )
            ),
            crawler=EmptyCrawler(),
            web_search_client=web_search_client,
            web_search_limit=0,
        )

        result = enricher.enrich(RestaurantInput(name="Casa Paco", location="Gijón"))

        self.assertEqual(web_search_client.queries, [])
        self.assertIn("Límite de búsqueda web alcanzado", result.notes)

    def test_unexpected_places_error_is_caught_in_result(self):
        enricher = RestaurantEnricher(
            places_client=ExplodingPlacesClient(),
            crawler=EmptyCrawler(),
        )

        result = enricher.enrich(RestaurantInput(name="Casa Paco", location="Gijón"))

        self.assertEqual(result.status, "unexpected_error")
        self.assertIn("ValueError", result.notes)

    def test_unexpected_web_search_error_is_caught_without_crashing(self):
        enricher = RestaurantEnricher(
            places_client=FakePlacesClient(
                Place(
                    id="abc",
                    display_name="Casa Paco",
                    formatted_address="Gijón",
                    google_maps_uri="https://maps.google.com/?cid=1",
                    website_uri="",
                    types=("restaurant",),
                )
            ),
            crawler=EmptyCrawler(),
            web_search_client=ExplodingWebSearchClient(),
        )

        result = enricher.enrich(RestaurantInput(name="Casa Paco", location="Gijón"))

        self.assertEqual(result.status, "no_website")
        self.assertIn("ValueError", result.notes)


if __name__ == "__main__":
    unittest.main()
