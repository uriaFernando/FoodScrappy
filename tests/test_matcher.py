import unittest

from scrappy.matcher import choose_best_place, normalize_text, score_place
from scrappy.models import Place, RestaurantInput


class MatcherTests(unittest.TestCase):
    def test_normalize_text_removes_accents_and_punctuation(self):
        self.assertEqual(normalize_text("Café del Mar!"), "cafe del mar")

    def test_prefers_matching_name_and_location(self):
        restaurant = RestaurantInput(name="Casa Paco", location="Madrid")
        candidates = [
            Place(id="1", display_name="Casa Pepe", formatted_address="Barcelona", types=("restaurant",)),
            Place(id="2", display_name="Casa Paco", formatted_address="Calle Mayor, Madrid", types=("restaurant",)),
        ]

        match, confidence = choose_best_place(candidates, restaurant)

        self.assertEqual(match.id, "2")
        self.assertGreater(confidence, 0.8)

    def test_scores_non_restaurant_lower(self):
        restaurant = RestaurantInput(name="Casa Paco", location="Madrid")
        place = Place(id="1", display_name="Casa Paco", formatted_address="Madrid", types=("store",))

        self.assertLess(score_place(place, restaurant), 1.0)


if __name__ == "__main__":
    unittest.main()
