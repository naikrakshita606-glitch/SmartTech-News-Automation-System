import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app import app


class DashboardTests(unittest.TestCase):
    def setUp(self):
        app.config.update(TESTING=True)
        self.client = app.test_client()

    def _database_connection(self):
        client = Mock()
        news_cursor = Mock()
        news_cursor.sort.return_value = news_cursor
        news_cursor.limit.return_value = []
        database = SimpleNamespace(
            news=SimpleNamespace(find=Mock(return_value=news_cursor)),
            daily_briefings=SimpleNamespace(find_one=Mock(return_value=None)),
        )
        return client, database

    def test_dashboard_displays_empty_state(self):
        database_connection = self._database_connection()
        with patch("app.connect_to_database", return_value=database_connection):
            response = self.client.get("/dashboard")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"SmartTech News", response.data)
        self.assertIn(b"Start automatic refresh", response.data)
        self.assertIn(b"Every 1 minute", response.data)
        self.assertIn(b"Every 5 minutes", response.data)
        self.assertIn(b"Every 1 hour", response.data)
        self.assertIn(b"Every 1 day", response.data)
        self.assertIn(b"No saved articles yet", response.data)
        database_connection[0].close.assert_called_once()

    def test_dashboard_post_fetches_saves_and_generates_briefing(self):
        database_connection = self._database_connection()
        fetched_articles = [{"title": "Latest technology news"}]

        with (
            patch(
                "app.connect_to_database",
                side_effect=[database_connection, self._database_connection()],
            ),
            patch("app.fetch_news", return_value=fetched_articles),
            patch("app.save_news", return_value=1) as save_news,
            patch("app.generate_daily_briefing") as generate_briefing,
        ):
            response = self.client.post(
                "/dashboard",
                data={"action": "fetch_now"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Fetched 1 articles; saved 1 new articles", response.data)
        save_news.assert_called_once_with(
            fetched_articles,
            database_connection[1].news,
        )
        generate_briefing.assert_called_once_with(
            database_connection[1].news,
            database_connection[1].daily_briefings,
        )
        database_connection[0].close.assert_called_once()

    def test_dashboard_starts_selected_interval_and_runs_immediately(self):
        database_connection = self._database_connection()
        with (
            patch(
                "app.connect_to_database",
                return_value=database_connection,
            ),
            patch("app._scheduler.start") as start_scheduler,
            patch("app._scheduler.add_job") as add_job,
            patch(
                "app._perform_update",
                return_value=("Fetched 0 articles; saved 0 new articles.", None),
            ) as perform_update,
        ):
            response = self.client.post(
                "/dashboard",
                data={"action": "start_schedule", "interval": "5 minutes"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Automatic refresh is set to every 5 minutes", response.data)
        start_scheduler.assert_called_once()
        add_job.assert_called_once_with(
            perform_update,
            trigger="interval",
            seconds=300,
            id="news-refresh",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        perform_update.assert_called_once()
        database_connection[0].close.assert_called_once()

        with (
            patch("app._scheduler.get_job", return_value=Mock()),
            patch("app._scheduler.remove_job") as remove_job,
            patch("app.connect_to_database", return_value=self._database_connection()),
        ):
            stop_response = self.client.post(
                "/dashboard",
                data={"action": "stop_schedule"},
            )
        self.assertEqual(stop_response.status_code, 200)
        remove_job.assert_called_once_with("news-refresh")

    def test_dashboard_reports_database_connection_errors(self):
        with patch(
            "app.connect_to_database",
            side_effect=ConnectionError("database details"),
        ):
            response = self.client.get("/dashboard")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Could not load saved news", response.data)
        self.assertNotIn(b"database details", response.data)


if __name__ == "__main__":
    unittest.main()
