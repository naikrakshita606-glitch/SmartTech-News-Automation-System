import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

from pymongo.errors import PyMongoError

import config
from briefing_service import (
    format_briefing,
    generate_daily_briefing,
    score_article,
    select_top_news,
)


class ArticleSelectionTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 18, 6, 0, tzinfo=timezone.utc)

    def test_higher_priority_categories_score_more(self):
        ai_article = {
            "category": "AI",
            "title": "AI research update",
            "published_at": self.now - timedelta(hours=2),
        }
        other_article = {
            "category": "Other Technology",
            "title": "Technology research update",
            "published_at": self.now - timedelta(hours=2),
        }

        self.assertGreater(
            score_article(ai_article, self.now),
            score_article(other_article, self.now),
        )

    def test_impact_keywords_and_freshness_add_points(self):
        article = {
            "category": "Cybersecurity",
            "title": "Critical vulnerability announced",
            "published_at": self.now - timedelta(hours=1),
        }

        self.assertEqual(score_article(article, self.now), 12)

    def test_freshness_bands_match_the_24_hour_briefing_window(self):
        article = {"category": "Cloud", "title": "Cloud report"}

        article["published_at"] = self.now - timedelta(hours=8)
        self.assertEqual(score_article(article, self.now), 8)

        article["published_at"] = self.now - timedelta(hours=18)
        self.assertEqual(score_article(article, self.now), 6)

    def test_selection_sorts_by_score_and_deduplicates_urls(self):
        duplicate_low_score = {
            "url": "https://example.test/duplicate",
            "title": "Old technology story",
            "category": "Other Technology",
            "published_at": self.now - timedelta(days=2),
        }
        duplicate_high_score = {
            "url": "https://example.test/duplicate",
            "title": "Critical AI breakthrough",
            "category": "AI",
            "published_at": self.now - timedelta(hours=1),
        }
        cloud_article = {
            "url": "https://example.test/cloud",
            "title": "Cloud update",
            "category": "Cloud",
            "published_at": self.now - timedelta(hours=1),
        }

        selected = select_top_news(
            [duplicate_low_score, cloud_article, duplicate_high_score],
            now=self.now,
        )

        self.assertEqual(
            [article["url"] for article in selected],
            [
                "https://example.test/duplicate",
                "https://example.test/cloud",
            ],
        )
        self.assertEqual(selected[0]["category"], "AI")

    def test_limit_must_be_positive(self):
        with self.assertRaisesRegex(ValueError, "at least 1"):
            select_top_news([], limit=0)

    def test_format_includes_sections_learning_and_career(self):
        text = format_briefing(
            "2026-10-18",
            [
                {
                    "title": "A new agentic AI tool",
                    "description": "Teams can use the tool.",
                    "source": "Example",
                    "url": "https://example.test/ai",
                    "category": "Agentic AI",
                }
            ],
        )

        self.assertIn("DAILY GLOBAL TECH BRIEFING", text)
        self.assertIn("AGENTIC AI", text)
        self.assertIn("Why it matters:", text)
        self.assertIn("LEARNING OF THE DAY", text)
        self.assertIn("CAREER OPPORTUNITY", text)


class GenerateBriefingTests(unittest.TestCase):
    def test_generates_and_upserts_one_briefing_for_the_date(self):
        generated_at = datetime(2026, 10, 18, 6, 0, tzinfo=timezone.utc)
        article = {
            "title": "Quantum computing progress",
            "description": "A new qubit result.",
            "source": "Example",
            "url": "https://example.test/quantum",
            "category": "Quantum Computing",
            "published_at": generated_at - timedelta(hours=2),
        }
        news_collection = Mock()
        news_collection.find.return_value.sort.return_value = [article]
        briefing_collection = Mock()

        with patch.object(config, "NEWS_SCHEDULE_TIMEZONE", "UTC"):
            briefing = generate_daily_briefing(
                news_collection,
                briefing_collection,
                generated_at,
            )

        self.assertEqual(briefing["briefing_date"], "2026-10-18")
        self.assertEqual(briefing["total_news"], 1)
        self.assertEqual(briefing["categories"], {"Quantum Computing": 1})
        self.assertIn("Quantum computing progress", briefing["text"])
        news_collection.find.assert_called_once_with(
            {"published_at": {"$gte": generated_at - timedelta(days=1)}},
            {"_id": 0},
        )
        briefing_collection.replace_one.assert_called_once_with(
            {"briefing_date": "2026-10-18"},
            briefing,
            upsert=True,
        )

    def test_empty_news_still_creates_a_briefing(self):
        news_collection = Mock()
        news_collection.find.return_value.sort.return_value = []
        briefing_collection = Mock()

        with patch.object(config, "NEWS_SCHEDULE_TIMEZONE", "UTC"):
            briefing = generate_daily_briefing(
                news_collection,
                briefing_collection,
                datetime(2026, 10, 18, 6, 0, tzinfo=timezone.utc),
            )

        self.assertEqual(briefing["total_news"], 0)
        self.assertEqual(briefing["top_news"], [])
        self.assertIn("No matching stories today", briefing["text"])
        briefing_collection.replace_one.assert_called_once()

    def test_database_read_failure_is_reported(self):
        news_collection = Mock()
        news_collection.find.side_effect = PyMongoError("private detail")

        with self.assertRaisesRegex(RuntimeError, "Could not read recent news"):
            generate_daily_briefing(
                news_collection,
                Mock(),
                datetime(2026, 10, 18, 6, 0, tzinfo=timezone.utc),
            )

    def test_database_write_failure_is_reported(self):
        news_collection = Mock()
        news_collection.find.return_value.sort.return_value = []
        briefing_collection = Mock()
        briefing_collection.replace_one.side_effect = PyMongoError("private detail")

        with self.assertRaisesRegex(RuntimeError, "Could not save the daily briefing"):
            generate_daily_briefing(
                news_collection,
                briefing_collection,
                datetime(2026, 10, 18, 6, 0, tzinfo=timezone.utc),
            )


if __name__ == "__main__":
    unittest.main()
