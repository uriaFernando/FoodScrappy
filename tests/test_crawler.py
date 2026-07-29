import unittest

from scrappy.crawler import WebsiteCrawler


class FakeCrawler(WebsiteCrawler):
    def __init__(self, pages):
        super().__init__(max_pages=5)
        self.pages = pages

    def _fetch(self, url):
        if url not in self.pages:
            raise RuntimeError(f"{url}: missing fixture.")
        return self.pages[url]


class CrawlerTests(unittest.TestCase):
    def test_crawls_home_and_useful_same_domain_pages(self):
        pages = {
            "https://restaurant.test/": """
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <a href="/contacto">Contacto</a>
                <a href="https://instagram.com/restaurante">Instagram</a>
            """,
            "https://restaurant.test/contacto": """
                <a href="https://facebook.com/restaurante">Facebook</a>
            """,
        }
        crawler = FakeCrawler(pages)

        result = crawler.crawl("https://restaurant.test/")

        self.assertEqual(result.socials["instagram"], ["https://instagram.com/restaurante"])
        self.assertEqual(result.socials["facebook"], ["https://facebook.com/restaurante"])
        self.assertEqual(len(result.visited_urls), 2)

    def test_ignores_non_url_metadata_and_control_character_hrefs(self):
        pages = {
            "https://restaurant.test/": """
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <a href="/contacto con espacios">Rota</a>
                <a href="mailto:hola@restaurant.test">Email</a>
                <a href="/contacto">Contacto</a>
            """,
            "https://restaurant.test/contacto": """
                <a href="https://instagram.com/restaurante">Instagram</a>
            """,
        }
        crawler = FakeCrawler(pages)

        result = crawler.crawl("https://restaurant.test/")

        self.assertEqual(result.socials["instagram"], ["https://instagram.com/restaurante"])
        self.assertEqual(result.errors, ())

    def test_fetch_timeout_becomes_recoverable_crawl_error(self):
        class TimeoutCrawler(WebsiteCrawler):
            def _fetch(self, url):
                raise RuntimeError(f"{url}: timeout al leer respuesta.")

        result = TimeoutCrawler(max_pages=1).crawl("https://restaurant.test/")

        self.assertEqual(result.visited_urls, ())
        self.assertIn("timeout", result.errors[0])


if __name__ == "__main__":
    unittest.main()
