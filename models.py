"""Shared article categories and simple keyword-based categorization."""

import re


# Categories are checked in this order, so specific topics can take priority.
CATEGORY_KEYWORDS = {
    "Agentic AI": (
        "agentic ai",
        "ai agent",
        "ai agents",
        "autonomous agent",
        "multi-agent",
        "multi agent",
    ),
    "Quantum Computing": (
        "quantum computing",
        "quantum computer",
        "quantum",
        "qubit",
    ),
    "Cloud": (
        "cloud computing",
        "cloud",
        "aws",
        "azure",
        "google cloud",
    ),
    "Cybersecurity": (
        "cybersecurity",
        "cyber security",
        "ransomware",
        "data breach",
        "security vulnerability",
        "zero-day",
        "zero day",
    ),
    "Programming": (
        "programming language",
        "programming",
        "python",
        "javascript",
        "typescript",
        "rust",
        "java",
        "software development",
    ),
    "Developer Tools": (
        "developer tool",
        "developer tools",
        "ide",
        "code editor",
        "compiler",
        "github copilot",
        "command line",
        "cli",
        "sdk",
    ),
    "Startups": (
        "startup",
        "startups",
        "venture capital",
        "funding round",
        "series a",
        "series b",
        "series c",
        "ipo",
    ),
    "AI": (
        "artificial intelligence",
        "generative ai",
        "machine learning",
        "large language model",
        "llm",
        "chatgpt",
        "openai",
        "gemini",
        "ai",
    ),
    "Technology Companies": (
        "apple",
        "google",
        "microsoft",
        "meta",
        "amazon",
        "nvidia",
        "intel",
        "samsung",
        "oracle",
        "tesla",
        "ibm",
    ),
}


def categorize_news(title: str, description: str = "") -> str:
    """Return the first matching category, or Other Technology."""
    text = f"{title} {description}".lower()

    for category, keywords in CATEGORY_KEYWORDS.items():
        for keyword in keywords:
            if re.search(rf"\b{re.escape(keyword)}\b", text):
                return category

    return "Other Technology"
