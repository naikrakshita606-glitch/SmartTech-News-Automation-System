"""Rank recent articles and create a concise daily technology briefing."""

from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from pymongo.collection import Collection
from pymongo.errors import PyMongoError

import config


CATEGORY_SCORES = {
    "Agentic AI": 7,
    "Quantum Computing": 7,
    "AI": 6,
    "Cybersecurity": 6,
    "Cloud": 5,
    "Startups": 4,
    "Technology Companies": 4,
    "Programming": 3,
    "Developer Tools": 3,
    "Other Technology": 1,
}

IMPACT_KEYWORDS = (
    "breakthrough",
    "critical",
    "vulnerability",
    "data breach",
    "outage",
    "acquisition",
    "funding",
    "regulation",
    "record",
    "launches",
    "announces",
)

BRIEFING_SECTIONS = {
    "AI": {"AI"},
    "AGENTIC AI": {"Agentic AI"},
    "QUANTUM COMPUTING": {"Quantum Computing"},
    "CLOUD & SOFTWARE": {"Cloud", "Programming", "Developer Tools"},
    "CYBERSECURITY": {"Cybersecurity"},
    "TECHNOLOGY BUSINESS": {"Startups", "Technology Companies"},
    "TECHNOLOGY TRENDS": {"Other Technology"},
}

WHY_IT_MATTERS = {
    "AI": "AI changes can affect how people build software, work with information, and make decisions.",
    "Agentic AI": "Agentic AI can carry out multi-step tasks, changing how software and teams get work done.",
    "Quantum Computing": "Quantum research may eventually help solve specialized problems beyond today's computers.",
    "Cloud": "Cloud changes can affect the cost, reliability, and security of services used around the world.",
    "Cybersecurity": "Security developments can affect the safety of systems, organizations, and personal data.",
    "Programming": "Programming changes can influence how developers build and maintain software.",
    "Developer Tools": "Developer tools can change how quickly and safely software teams deliver products.",
    "Startups": "Startup developments can signal new products, investments, and technology jobs.",
    "Technology Companies": "Large technology companies can influence products, infrastructure, and industry direction.",
    "Other Technology": "This story may signal a technology change worth following.",
}

LEARNING_TOPICS = {
    "AI": "Try a small machine-learning or generative-AI example and inspect its limitations.",
    "Agentic AI": "Learn how tools, goals, and human approval fit into an AI agent workflow.",
    "Quantum Computing": "Review qubits, superposition, and what quantum computers can realistically do.",
    "Cloud": "Deploy a small application and learn about cloud regions, costs, and reliability.",
    "Cybersecurity": "Practice threat modeling and learn how multi-factor authentication reduces risk.",
    "Programming": "Write a small program in the language highlighted by the news.",
    "Developer Tools": "Try one developer tool and compare how it changes a coding task.",
    "Startups": "Study how a technology startup validates a problem and finds customers.",
    "Technology Companies": "Compare the products and business models of two technology companies.",
    "Other Technology": "Choose an unfamiliar term from today's articles and research its basics.",
}

CAREER_SKILLS = {
    "AI": "machine learning, data literacy, and responsible AI",
    "Agentic AI": "AI agent development, tool integration, and evaluation",
    "Quantum Computing": "linear algebra, quantum information, and quantum programming",
    "Cloud": "cloud platforms, distributed systems, and reliability engineering",
    "Cybersecurity": "security analysis, incident response, and secure software development",
    "Programming": "software development and the programming language in the article",
    "Developer Tools": "developer productivity, code review, and build tooling",
    "Startups": "product thinking, business analysis, and early-stage software development",
    "Technology Companies": "software engineering, product management, and technology operations",
    "Other Technology": "research and communication skills for emerging technologies",
}


def score_article(
    article: dict[str, Any],
    now: datetime | None = None,
) -> int:
    """Give an article a transparent score from topic, impact, and freshness."""
    score = CATEGORY_SCORES.get(article.get("category"), 1)
    text = f"{article.get('title', '')} {article.get('description', '')}".lower()

    if any(keyword in text for keyword in IMPACT_KEYWORDS):
        score += 2

    published_at = article.get("published_at")
    if isinstance(published_at, datetime):
        if published_at.tzinfo is None:
            published_at = published_at.replace(tzinfo=timezone.utc)
        else:
            published_at = published_at.astimezone(timezone.utc)

        current_time = now or datetime.now(timezone.utc)
        if current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=timezone.utc)
        age = current_time.astimezone(timezone.utc) - published_at
        if timedelta(0) <= age <= timedelta(hours=6):
            score += 4
        elif timedelta(hours=6) < age <= timedelta(hours=12):
            score += 3
        elif timedelta(hours=12) < age <= timedelta(hours=24):
            score += 1

    return score


def select_top_news(
    articles: list[dict[str, Any]],
    limit: int = 12,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Deduplicate by URL and return the highest-scoring articles."""
    if limit < 1:
        raise ValueError("The article limit must be at least 1.")

    unique_articles = {}
    for article in articles:
        url = article.get("url")
        if not isinstance(url, str) or not url:
            continue
        existing = unique_articles.get(url)
        if existing is None or score_article(article, now) > score_article(existing, now):
            unique_articles[url] = article

    ranked_articles = sorted(
        unique_articles.values(),
        key=lambda article: (
            -score_article(article, now),
            -_published_timestamp(article),
            article["url"],
        ),
    )
    return ranked_articles[:limit]


def _published_timestamp(article: dict[str, Any]) -> float:
    published_at = article.get("published_at")
    if not isinstance(published_at, datetime):
        return 0.0
    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=timezone.utc)
    return published_at.timestamp()


def _summary(article: dict[str, Any]) -> str:
    description = (article.get("description") or "").strip()
    if not description:
        return "No description was provided by the news source."

    sentences = description.replace("? ", "?\n").replace("! ", "!\n")
    sentences = sentences.replace(". ", ".\n").splitlines()
    return " ".join(sentence.strip() for sentence in sentences[:3])


def _primary_category(articles: list[dict[str, Any]]) -> str:
    if not articles:
        return "Other Technology"
    return Counter(article.get("category", "Other Technology") for article in articles).most_common(1)[0][0]


def format_briefing(
    briefing_date: str,
    articles: list[dict[str, Any]],
) -> str:
    """Format ranked articles into a readable terminal briefing."""
    lines = [
        "DAILY GLOBAL TECH BRIEFING",
        f"Date: {briefing_date}",
        f"Articles considered: {len(articles)}",
    ]

    for section, categories in BRIEFING_SECTIONS.items():
        lines.extend(["", section])
        section_articles = [
            article for article in articles
            if article.get("category") in categories
        ]
        if not section_articles:
            lines.append("- No matching stories today.")
            continue

        for article in section_articles[:2]:
            category = article.get("category", "Other Technology")
            lines.extend(
                [
                    f"- {article.get('title', 'Untitled')}",
                    f"  Summary: {_summary(article)}",
                    f"  Why it matters: {WHY_IT_MATTERS.get(category, WHY_IT_MATTERS['Other Technology'])}",
                    f"  Source: {article.get('source', 'Unknown source')} - {article.get('url', '')}",
                ]
            )

    primary_category = _primary_category(articles)
    lines.extend(
        [
            "",
            "LEARNING OF THE DAY",
            f"- {LEARNING_TOPICS.get(primary_category, LEARNING_TOPICS['Other Technology'])}",
            "",
            "CAREER OPPORTUNITY",
            f"- Relevant skills: {CAREER_SKILLS.get(primary_category, CAREER_SKILLS['Other Technology'])}.",
        ]
    )
    return "\n".join(lines)


def generate_daily_briefing(
    news_collection: Collection,
    briefing_collection: Collection,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    """Rank the last 24 hours of news and upsert the day's briefing."""
    if generated_at is None:
        generated_at = datetime.now(timezone.utc)
    elif generated_at.tzinfo is None:
        generated_at = generated_at.replace(tzinfo=timezone.utc)

    generated_at_utc = generated_at.astimezone(timezone.utc)
    briefing_date = generated_at.astimezone(
        ZoneInfo(config.NEWS_SCHEDULE_TIMEZONE)
    ).date().isoformat()
    since = generated_at_utc - timedelta(days=1)

    try:
        recent_articles = list(
            news_collection.find(
                {"published_at": {"$gte": since}},
                {"_id": 0},
            ).sort("published_at", -1)
        )
    except PyMongoError as error:
        raise RuntimeError(
            "Could not read recent news from MongoDB."
        ) from error

    top_news = select_top_news(recent_articles)
    categories = dict(Counter(
        article.get("category", "Other Technology") for article in recent_articles
    ))
    briefing_text = format_briefing(briefing_date, top_news)
    briefing = {
        "briefing_date": briefing_date,
        "generated_at": generated_at_utc,
        "total_news": len(recent_articles),
        "categories": categories,
        "top_news": top_news,
        "text": briefing_text,
        "created_at": generated_at_utc,
    }

    try:
        briefing_collection.replace_one(
            {"briefing_date": briefing_date},
            briefing,
            upsert=True,
        )
    except PyMongoError as error:
        raise RuntimeError(
            "Could not save the daily briefing to MongoDB."
        ) from error

    return briefing
