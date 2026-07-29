import json
import unittest
from unittest.mock import patch

from scrappy.web_search import (
    BraveSearchClient,
    SearchResult,
    extract_delivery_from_search_results,
    extract_socials_from_search_results,
    pick_official_website,
)


class FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(
            {
                "web": {
                    "results": [
                        {
                            "title": "Casa Paco",
                            "url": "https://casapaco.test/",
                            "description": "Restaurante oficial",
                        }
                    ]
                }
            }
        ).encode("utf-8")


class WebSearchTests(unittest.TestCase):
    def test_brave_search_client_parses_web_results(self):
        client = BraveSearchClient(api_key="key")

        with patch("urllib.request.urlopen", return_value=FakeResponse()):
            results = client.search("Casa Paco Gijon")

        self.assertEqual(results[0].link, "https://casapaco.test/")

    def test_pick_official_website_avoids_aggregators_and_socials(self):
        results = [
            SearchResult("Casa Paco TripAdvisor", "https://www.tripadvisor.es/casa-paco", ""),
            SearchResult("Casa Paco Facebook", "https://facebook.com/casapaco", ""),
            SearchResult("Casa Paco Oficial", "https://casapaco.test/", "web oficial"),
        ]

        self.assertEqual(pick_official_website(results, "Casa Paco"), "https://casapaco.test/")

    def test_extract_socials_from_search_results(self):
        results = [SearchResult("Casa Paco Facebook", "https://www.facebook.com/casapaco?ref=search", "")]

        socials = extract_socials_from_search_results(results)

        self.assertEqual(socials["facebook"], "https://facebook.com/casapaco")

    def test_extract_delivery_from_search_results(self):
        results = [
            SearchResult("Casa Paco Uber Eats", "https://www.ubereats.com/es/store/casa-paco/abc", ""),
            SearchResult("Casa Paco Just Eat", "https://www.just-eat.es/restaurants-casa-paco-gijon/menu", ""),
            SearchResult("Casa Paco Glovo", "https://glovoapp.com/es/es/gijon/casa-paco/", ""),
        ]

        delivery = extract_delivery_from_search_results(results)

        self.assertEqual(delivery["uber_eats"], "https://www.ubereats.com/es/store/casa-paco/abc")
        self.assertEqual(delivery["just_eat"], "https://www.just-eat.es/restaurants-casa-paco-gijon/menu")
        self.assertEqual(delivery["glovo"], "https://glovoapp.com/es/es/gijon/casa-paco/")


if __name__ == "__main__":
    unittest.main()
