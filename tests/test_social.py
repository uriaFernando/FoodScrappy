import unittest

from scrappy.social import extract_social_urls, normalize_social_url


class SocialUrlTests(unittest.TestCase):
    def test_normalizes_profile_url_and_drops_tracking(self):
        field, url = normalize_social_url("https://www.instagram.com/Example.Restaurant/?utm_source=site")

        self.assertEqual(field, "instagram")
        self.assertEqual(url, "https://instagram.com/Example.Restaurant")

    def test_ignores_share_urls(self):
        field, url = normalize_social_url("https://www.facebook.com/sharer.php?u=https://restaurant.test")

        self.assertIsNone(field)
        self.assertIsNone(url)

    def test_extracts_multiple_socials_from_html(self):
        html = """
        <a href="https://instagram.com/foo/">IG</a>
        <meta property="sameAs" content="https://www.linkedin.com/company/foo-restaurant?trk=x">
        <script>{"sameAs":["https://www.tiktok.com/@foo"]}</script>
        """

        socials = extract_social_urls(html)

        self.assertEqual(socials["instagram"], ["https://instagram.com/foo"])
        self.assertEqual(socials["linkedin"], ["https://linkedin.com/company/foo-restaurant"])
        self.assertEqual(socials["tiktok"], ["https://tiktok.com/@foo"])


if __name__ == "__main__":
    unittest.main()
