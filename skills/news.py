"""
news.py — News headline and search skills for MARS.

All functions return a ``str`` response that MARS speaks aloud.
Requires the ``NEWS_API_KEY`` environment variable (https://newsapi.org).

Functions
---------
get_top_news  : Fetch top headlines by category.
search_news   : Search articles for a specific topic.
"""

from __future__ import annotations

import os
import urllib.parse

import requests

from utils.logger import get_logger

log = get_logger(__name__)

_NEWS_BASE = "https://newsapi.org/v2"
_TIMEOUT = 10

_VALID_CATEGORIES = {
    "general", "business", "entertainment",
    "health", "science", "sports", "technology",
}


def _get_api_key() -> str | None:
    """Return the News API key from the environment."""
    return os.environ.get("NEWS_API_KEY")


# ---------------------------------------------------------------------------
# get_top_news
# ---------------------------------------------------------------------------


def get_top_news(category: str = "general", count: int = 5) -> str:
    """Return a spoken summary of the top news headlines.

    Parameters
    ----------
    category:
        One of: ``general``, ``business``, ``entertainment``, ``health``,
        ``science``, ``sports``, ``technology``.
    count:
        Number of headlines to return (1–10).

    Returns
    -------
    str
        Spoken news summary, or an error/warning message.
    """
    api_key = _get_api_key()
    if not api_key:
        return (
            "News is unavailable. Please set the NEWS_API_KEY environment variable."
        )

    category = category.lower()
    if category not in _VALID_CATEGORIES:
        category = "general"
    count = max(1, min(10, count))

    url = (
        f"{_NEWS_BASE}/top-headlines"
        f"?category={category}&pageSize={count}&language=en&apiKey={api_key}"
    )
    try:
        response = requests.get(url, timeout=_TIMEOUT)
        if response.status_code == 401:
            return "News API key is invalid. Please check your NEWS_API_KEY."
        response.raise_for_status()
        data = response.json()

        articles: list[dict] = data.get("articles", [])
        if not articles:
            return f"I found no {category} headlines at the moment."

        intro = f"Here are the top {len(articles)} {category} headlines. "
        headlines: list[str] = []
        for i, article in enumerate(articles[:count], start=1):
            title: str = article.get("title") or ""
            source: str = (article.get("source") or {}).get("name") or ""
            if title:
                entry = f"{i}. {title}"
                if source:
                    entry += f", from {source}"
                headlines.append(entry)

        if not headlines:
            return f"No readable headlines found for category '{category}'."

        result = intro + ". ".join(headlines) + "."
        log.info("get_top_news(category=%r, count=%d): %d articles", category, count, len(headlines))
        return result
    except requests.RequestException as exc:
        log.error("get_top_news failed: %s", exc)
        return f"I was unable to fetch the news: {exc}"


# ---------------------------------------------------------------------------
# search_news
# ---------------------------------------------------------------------------


def search_news(query: str) -> str:
    """Search recent news articles for *query* and return a spoken summary.

    Parameters
    ----------
    query:
        Topic or keyword to search for.

    Returns
    -------
    str
        Spoken summary of the top matching articles, or an error message.
    """
    if not query.strip():
        return "Please provide a topic to search for in the news."

    api_key = _get_api_key()
    if not api_key:
        return (
            "News search is unavailable. Please set the NEWS_API_KEY environment variable."
        )

    encoded_query = urllib.parse.quote(query)
    url = (
        f"{_NEWS_BASE}/everything"
        f"?q={encoded_query}&pageSize=5&language=en"
        f"&sortBy=publishedAt&apiKey={api_key}"
    )
    try:
        response = requests.get(url, timeout=_TIMEOUT)
        if response.status_code == 401:
            return "News API key is invalid. Please check your NEWS_API_KEY."
        response.raise_for_status()
        data = response.json()

        articles: list[dict] = data.get("articles", [])
        if not articles:
            return f"I found no news articles about '{query}'."

        intro = f"Here are the latest news articles about '{query}'. "
        items: list[str] = []
        for i, article in enumerate(articles, start=1):
            title: str = article.get("title") or ""
            source: str = (article.get("source") or {}).get("name") or ""
            description: str = article.get("description") or ""
            if title:
                entry = f"{i}. {title}"
                if source:
                    entry += f", from {source}"
                if description:
                    # Keep description brief
                    short_desc = description[:120].rsplit(" ", 1)[0]
                    entry += f". {short_desc}"
                items.append(entry)

        if not items:
            return f"No readable articles found for '{query}'."

        result = intro + " | ".join(items)
        log.info("search_news(%r): %d articles", query, len(items))
        return result
    except requests.RequestException as exc:
        log.error("search_news failed: %s", exc)
        return f"I was unable to search the news: {exc}"
