import unittest

from scrappy.models import Place
from scrappy.places import GooglePlacesClient


class TextSearchPaginationClient(GooglePlacesClient):
    def __init__(self):
        super().__init__(api_key="fake")
        self.bodies = []

    def _request_json(self, url, *, method, field_mask, body=None):
        self.bodies.append(body)
        if len(self.bodies) == 1:
            return {
                "places": [{"id": "1", "displayName": {"text": "Casa Paco"}, "formattedAddress": "Gijón"}],
                "nextPageToken": "token-2",
            }
        return {
            "places": [{"id": "2", "displayName": {"text": "Sidrería Norte"}, "formattedAddress": "Gijón"}],
        }


class PlacesClientTests(unittest.TestCase):
    def test_text_search_paginates_next_page_token(self):
        client = TextSearchPaginationClient()

        places = client.search_text_places(
            "restaurantes en Gijon",
            {"rectangle": {"low": {"latitude": 1, "longitude": 1}, "high": {"latitude": 2, "longitude": 2}}},
            sleep_seconds=0,
        )

        self.assertEqual([place.id for place in places], ["1", "2"])
        self.assertEqual(client.bodies[1]["pageToken"], "token-2")

    def test_nearby_search_builds_restaurant_request(self):
        class NearbyClient(GooglePlacesClient):
            def _request_json(self, url, *, method, field_mask, body=None):
                self.body = body
                return {
                    "places": [
                        {"id": "1", "displayName": {"text": "Casa Paco"}, "formattedAddress": "Gijón"}
                    ]
                }

        client = NearbyClient(api_key="fake")

        places = client.search_nearby_restaurants(43.5, -5.6, 700)

        self.assertEqual(places, [Place(id="1", display_name="Casa Paco", formatted_address="Gijón")])
        self.assertEqual(client.body["includedTypes"], ["restaurant"])


if __name__ == "__main__":
    unittest.main()
