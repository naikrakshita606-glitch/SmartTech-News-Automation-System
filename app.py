"""Run the local dashboard for fetching news and viewing saved briefings."""

from datetime import datetime, timezone
from threading import Lock
from typing import Any

from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, jsonify, redirect, render_template, request, url_for
from pymongo.errors import PyMongoError

import config
from briefing_service import generate_daily_briefing
from database import connect_to_database
from news_service import NewsServiceError, fetch_news, save_news


app = Flask(__name__)

SCHEDULE_INTERVALS = {
    "1 minute": 60,
    "5 minutes": 5 * 60,
    "1 hour": 60 * 60,
    "1 day": 24 * 60 * 60,
}
_scheduler = BackgroundScheduler(timezone="UTC")
_state_lock = Lock()
_scheduler_active = False
_scheduler_interval = None
_update_state: dict[str, Any] = {
    "run_id": 0,
    "last_run": None,
    "last_error": None,
    "last_saved": None,
}


def _perform_update() -> tuple[str | None, str | None]:
    """Fetch news, save new articles, and generate the latest briefing."""
    client = None
    message = None
    error = None
    saved_count = None
    try:
        client, database = connect_to_database()
        fetched_articles = fetch_news()
        saved_count = save_news(fetched_articles, database.news)
        generate_daily_briefing(
            database.news,
            database.daily_briefings,
        )
        message = (
            f"Fetched {len(fetched_articles)} articles; saved "
            f"{saved_count} new articles. Today's briefing is updated."
        )
    except (NewsServiceError, ConnectionError, RuntimeError, PyMongoError) as exception:
        error = str(exception)
    finally:
        if client is not None:
            client.close()

    with _state_lock:
        _update_state["run_id"] += 1
        _update_state["last_run"] = datetime.now(timezone.utc).isoformat()
        _update_state["last_error"] = error
        _update_state["last_saved"] = saved_count

    return message, error


def _render_dashboard(
    message: str | None = None,
    error: str | None = None,
):
    """Load the latest saved content and render the dashboard."""
    client = None
    articles: list[dict[str, Any]] = []
    briefing = None

    try:
        client, database = connect_to_database()
        articles = list(
            database.news.find({}, {"_id": 0})
            .sort("published_at", -1)
            .limit(20)
        )
        briefing = database.daily_briefings.find_one(
            {},
            {"_id": 0},
            sort=[("generated_at", -1)],
        )
    except (ConnectionError, PyMongoError):
        if not error:
            error = (
                "Could not load saved news. Check that MongoDB is running "
                "and MONGODB_URI in .env is correct."
            )
    finally:
        if client is not None:
            client.close()

    with _state_lock:
        scheduler_active = _scheduler_active
        scheduler_interval = _scheduler_interval
        run_id = _update_state["run_id"]

    return render_template(
        "dashboard.html",
        articles=articles,
        briefing=briefing,
        message=message,
        error=error,
        intervals=SCHEDULE_INTERVALS,
        selected_interval=request.form.get("interval", "1 minute"),
        scheduler_active=scheduler_active,
        scheduler_interval=scheduler_interval,
        run_id=run_id,
        schedule_time=(
            f"{config.NEWS_SCHEDULE_HOUR:02}:"
            f"{config.NEWS_SCHEDULE_MINUTE:02} "
            f"{config.NEWS_SCHEDULE_TIMEZONE}"
        ),
    )


@app.get("/")
def home():
    """Send the root URL to the dashboard."""
    return redirect(url_for("dashboard"))


@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    """Show saved news and control manual or recurring GNews updates."""
    global _scheduler_active, _scheduler_interval
    message = None
    error = None

    if request.method == "POST":
        action = request.form.get("action")
        if action == "fetch_now":
            message, error = _perform_update()
        elif action == "start_schedule":
            interval = request.form.get("interval", "")
            interval_seconds = SCHEDULE_INTERVALS.get(interval)
            if interval_seconds is None:
                error = "Choose one of the available refresh intervals."
            else:
                with _state_lock:
                    if not _scheduler.running:
                        _scheduler.start()
                    _scheduler.add_job(
                        _perform_update,
                        trigger="interval",
                        seconds=interval_seconds,
                        id="news-refresh",
                        replace_existing=True,
                        max_instances=1,
                        coalesce=True,
                    )
                    _scheduler_active = True
                    _scheduler_interval = interval
                message, error = _perform_update()
                if message:
                    message += f" Automatic refresh is set to every {interval}."
        elif action == "stop_schedule":
            with _state_lock:
                if _scheduler.get_job("news-refresh") is not None:
                    _scheduler.remove_job("news-refresh")
                _scheduler_active = False
                _scheduler_interval = None
            message = "Automatic news refresh stopped."

    return _render_dashboard(message=message, error=error)


@app.get("/api/scheduler-status")
def scheduler_status():
    """Return scheduler state for the dashboard's lightweight polling."""
    with _state_lock:
        return jsonify(
            {
                "active": _scheduler_active,
                "interval": _scheduler_interval,
                **_update_state,
            }
        )


if __name__ == "__main__":
    app.run(
        host=config.APP_HOST,
        port=config.APP_PORT,
        debug=False,
        use_reloader=False,
    )
