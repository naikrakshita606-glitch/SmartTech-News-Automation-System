"""Fetch technology articles from NewsAPI.org and save them in MongoDB."""

from datetime import datetime, timezone
from typing import Any

import requests
from pymongo.collection import Collection
from pymongo.errors import DuplicateKeyError, PyMongoError

import config
from models import categorize_news


class NewsServiceError(Exception):
    """Raised when the news provider returns an unusable response."""


def _parse_published_at(value: str | None) -> datetime | None:
    """Convert NewsAPI's ISO date string to a Python datetime."""
    if not value:
        return None

    try:
        published_at = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise NewsServiceError(
            "The news provider returned an invalid publication date."
        ) from error

    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=timezone.utc)

    return published_at


def _normalize_article(article: dict[str, Any]) -> dict[str, Any] | None:
    """Map one NewsAPI article to the fields used by this project."""
    title = article.get("title")
    url = article.get("url")

    # NewsAPI may return removed or incomplete articles without usable links.
    if not isinstance(title, str) or not title.strip():
        return None
    if not isinstance(url, str) or not url.strip():
        return None
    if title.strip() == "[Removed]":
        return None

    description = article.get("description")
    if description is not None and not isinstance(description, str):
        raise NewsServiceError("The news provider returned an invalid description.")
    description = description or ""

    source_data = article.get("source") or {}
    if not isinstance(source_data, dict):
        raise NewsServiceError("The news provider returned an invalid source.")
    source = source_data.get("name") or "Unknown source"
    if not isinstance(source, str):
        raise NewsServiceError("The news provider returned an invalid source name.")

    author = article.get("author")
    if author is not None and not isinstance(author, str):
        author = None

    published_value = article.get("publishedAt")
    if published_value is not None and not isinstance(published_value, str):
        raise NewsServiceError(
            "The news provider returned an invalid publication date."
        )

    return {
        "title": title.strip(),
        "description": description.strip(),
        "source": source,
        "author": author,
        "url": url.strip(),
        "category": categorize_news(title, description),
        "published_at": _parse_published_at(published_value),
        "collected_at": datetime.now(timezone.utc),
    }


def _build_request_kwargs() -> dict[str, Any]:
    """Build the provider-specific request parameters and headers."""
    if "gnews.io" in config.NEWS_API_URL.lower():
        params: dict[str, Any] = {
            "q": "technology OR artificial intelligence OR cybersecurity",
            "lang": "en",
            "max": 10,
            "apikey": config.NEWS_API_KEY,
        }
        return {
            "params": params,
            "timeout": config.NEWS_REQUEST_TIMEOUT_SECONDS,
        }

    params = {
        "q": "technology OR artificial intelligence OR cybersecurity",
        "language": "en",
        "sortBy": "publishedAt",
        "pageSize": 100,
    }
    return {
        "headers": {"X-Api-Key": config.NEWS_API_KEY},
        "params": params,
        "timeout": config.NEWS_REQUEST_TIMEOUT_SECONDS,
    }


def fetch_news() -> list[dict[str, Any]]:
    """Request and normalize recent English-language technology news."""
    if not config.NEWS_API_KEY:
        raise NewsServiceError(
            "Set NEWS_API_KEY in your local .env file before fetching news."
        )
    if not config.NEWS_API_URL:
        raise NewsServiceError("Set NEWS_API_URL before fetching news.")

    request_kwargs = _build_request_kwargs()

    try:
        response = requests.get(config.NEWS_API_URL, **request_kwargs)
        response.raise_for_status()
    except requests.RequestException as error:
        status_code = getattr(error.response, "status_code", None)
        if status_code is not None:
            raise NewsServiceError(
                f"The news provider rejected the request (HTTP {status_code}). "
                "Check the API key, account limits, and request settings."
            ) from None
        raise NewsServiceError(
            "The news provider could not be reached. Check your network "
            "connection and try again."
        ) from None

    try:
        payload = response.json()
    except ValueError as error:
        raise NewsServiceError(
            "The news provider returned a response that was not valid JSON."
        ) from error

    if not isinstance(payload, dict):
        raise NewsServiceError("The news provider returned an invalid response.")

    status = payload.get("status")
    if status is not None and status != "ok":
        raise NewsServiceError(
            "The news provider reported an unsuccessful request. Check the API "
            "key, account limits, and request settings."
        )

    articles = payload.get("articles")
    if not isinstance(articles, list):
        raise NewsServiceError(
            "The news provider response did not contain an article list."
        )

    normalized_articles = []
    for article in articles:
        if not isinstance(article, dict):
            raise NewsServiceError(
                "The news provider returned an article in an invalid format."
            )
        normalized = _normalize_article(article)
        if normalized is not None:
            normalized_articles.append(normalized)

    return normalized_articles


def save_news(
    articles: list[dict[str, Any]],
    news_collection: Collection,
) -> int:
    """Save new articles and return how many were inserted."""
    saved_count = 0

    for article in articles:
        try:
            news_collection.insert_one(article)
            saved_count += 1
        except DuplicateKeyError:
            # The unique URL index safely rejects an article already collected.
            continue
        except PyMongoError as error:
            raise RuntimeError(
                "Could not save an article to MongoDB. Check the database connection."
            ) from error

    return saved_count
