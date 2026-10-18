import unittest
from datetime import datetime, timezone
from unittest.mock import Mock, patch

import requests
from pymongo.errors import DuplicateKeyError, PyMongoError

import config
from news_service import NewsServiceError, fetch_news, save_news


class FetchNewsTests(unittest.TestCase):
    def setUp(self):
        self.settings = patch.multiple(
            config,
            NEWS_API_KEY="test-key",
            NEWS_API_URL="https://example.test/news",
            NEWS_REQUEST_TIMEOUT_SECONDS=10,
        )
        self.settings.start()
        self.addCleanup(self.settings.stop)

    def test_fetches_and_normalizes_articles(self):
        response = Mock()
        response.json.return_value = {
            "status": "ok",
            "articles": [
                {
                    "title": "New AI agents help developers",
                    "description": "A new agentic AI tool.",
                    "source": {"name": "Example News"},
                    "author": "Reporter",
                    "publishedAt": "2026-10-18T05:30:00Z",
                    "url": "https://example.test/article",
                },
                {"title": "[Removed]", "url": "https://example.test/removed"},
                {"title": "Missing article URL"},
            ],
        }

        with patch("news_service.requests.get", return_value=response) as get:
            articles = fetch_news()

        get.assert_called_once_with(
            "https://example.test/news",
            headers={"X-Api-Key": "test-key"},
            params={
                "q": "technology OR artificial intelligence OR cybersecurity",
                "language": "en",
                "sortBy": "publishedAt",
                "pageSize": 100,
            },
            timeout=10,
        )
        self.assertEqual(len(articles), 1)
        article = articles[0]
        self.assertEqual(article["category"], "Agentic AI")
        self.assertEqual(article["source"], "Example News")
        self.assertEqual(article["author"], "Reporter")
        self.assertEqual(
            article["published_at"],
            datetime(2026, 10, 18, 5, 30, tzinfo=timezone.utc),
        )
        self.assertIsNotNone(article["collected_at"].tzinfo)

    def test_fetches_from_gnews_api(self):
        response = Mock()
        response.json.return_value = {
            "articles": [
                {
                    "title": "AI chip startup raises funds",
                    "description": "A new funding round for chip design.",
                    "source": {"name": "Example News"},
                    "publishedAt": "2026-10-18T05:30:00Z",
                    "url": "https://example.test/article",
                }
            ]
        }

        with patch.object(config, "NEWS_API_URL", "https://gnews.io/api/v4/search"), patch.object(
            config, "NEWS_API_KEY", "gnews-key"
        ), patch("news_service.requests.get", return_value=response) as get:
            articles = fetch_news()

        get.assert_called_once_with(
            "https://gnews.io/api/v4/search",
            params={
                "q": "technology OR artificial intelligence OR cybersecurity",
                "lang": "en",
                "max": 10,
                "apikey": "gnews-key",
            },
            timeout=10,
        )
        self.assertEqual(len(articles), 1)
        self.assertEqual(articles[0]["title"], "AI chip startup raises funds")
        self.assertEqual(articles[0]["source"], "Example News")

    def test_empty_article_list_is_valid(self):
        response = Mock()
        response.json.return_value = {"status": "ok", "articles": []}

        with patch("news_service.requests.get", return_value=response):
            self.assertEqual(fetch_news(), [])

    def test_missing_key_is_reported_without_requesting(self):
        with patch.object(config, "NEWS_API_KEY", ""), patch(
            "news_service.requests.get"
        ) as get:
            with self.assertRaisesRegex(NewsServiceError, "Set NEWS_API_KEY"):
                fetch_news()
        get.assert_not_called()

    def test_network_error_is_reported_safely(self):
        with patch(
            "news_service.requests.get",
            side_effect=requests.Timeout("private request details"),
        ):
            with self.assertRaisesRegex(NewsServiceError, "could not be reached"):
                fetch_news()

    def test_http_error_reports_status_without_exposing_request_url(self):
        response = Mock()
        response.status_code = 400
        error = requests.HTTPError(
            "Bad request for https://gnews.io/search?apikey=secret-key",
            response=response,
        )

        with patch("news_service.requests.get") as get:
            get.return_value.raise_for_status.side_effect = error
            with self.assertRaisesRegex(NewsServiceError, "HTTP 400") as raised:
                fetch_news()

        self.assertNotIn("secret-key", str(raised.exception))
        self.assertIsNone(raised.exception.__cause__)

    def test_invalid_json_is_reported(self):
        response = Mock()
        response.json.side_effect = ValueError("invalid JSON detail")

        with patch("news_service.requests.get", return_value=response):
            with self.assertRaisesRegex(NewsServiceError, "not valid JSON"):
                fetch_news()

    def test_invalid_provider_status_is_reported(self):
        response = Mock()
        response.json.return_value = {"status": "error"}

        with patch("news_service.requests.get", return_value=response):
            with self.assertRaisesRegex(
                NewsServiceError, "unsuccessful request"
            ):
                fetch_news()

    def test_invalid_article_date_is_reported(self):
        response = Mock()
        response.json.return_value = {
            "status": "ok",
            "articles": [
                {
                    "title": "Technology report",
                    "url": "https://example.test/article",
                    "publishedAt": 123,
                }
            ],
        }

        with patch("news_service.requests.get", return_value=response):
            with self.assertRaisesRegex(NewsServiceError, "invalid publication date"):
                fetch_news()


class SaveNewsTests(unittest.TestCase):
    def test_saves_new_articles_and_skips_duplicate_url(self):
        collection = Mock()
        collection.insert_one.side_effect = [
            Mock(),
            DuplicateKeyError("duplicate URL"),
        ]
        articles = [
            {"url": "https://example.test/one"},
            {"url": "https://example.test/already-saved"},
        ]

        saved_count = save_news(articles, collection)

        self.assertEqual(saved_count, 1)
        self.assertEqual(collection.insert_one.call_count, 2)

    def test_reports_other_database_errors(self):
        collection = Mock()
        collection.insert_one.side_effect = PyMongoError(
            "private database details"
        )

        with self.assertRaisesRegex(RuntimeError, "Check the database connection"):
            save_news([{"url": "https://example.test/one"}], collection)


if __name__ == "__main__":
    unittest.main()
