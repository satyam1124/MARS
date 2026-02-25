"""
web_search.py — Web search and browsing skills for MARS.

All functions return a ``str`` response that MARS speaks aloud.

Functions
---------
search_web          : Search DuckDuckGo and return a spoken summary.
open_url            : Open a URL in the default browser.
search_wikipedia    : Retrieve a Wikipedia article summary.
get_webpage_summary : Fetch and summarise the text content of any URL.
"""

from __future__ import annotations

import subprocess
import urllib.parse

import requests
from bs4 import BeautifulSoup

from utils.logger import get_logger

log = get_logger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    )
}
_TIMEOUT = 10  # seconds


# ---------------------------------------------------------------------------
# search_web
# ---------------------------------------------------------------------------


def search_web(query: str) -> str:
    """Search DuckDuckGo for *query* and return a spoken summary of the results.

    Uses DuckDuckGo's HTML interface (no API key required).  Returns up to
    three result snippets.

    Parameters
    ----------
    query:
        The search query string.

    Returns
    -------
    str
        Spoken summary of the top results, or an error message.
    """
    if not query.strip():
        return "Please provide a search query."

    encoded = urllib.parse.quote_plus(query)
    url = f"https://html.duckduckgo.com/html/?q={encoded}"
    try:
        response = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        results: list[str] = []
        for result in soup.select(".result__snippet"):
            text = result.get_text(separator=" ", strip=True)
            if text:
                results.append(text)
            if len(results) >= 3:
                break

        if not results:
            return f"I found no results for '{query}'."

        intro = f"Here are the top results for '{query}'. "
        body = " | ".join(results)
        spoken = intro + body
        log.info("search_web(%r): %d results", query, len(results))
        return spoken
    except requests.RequestException as exc:
        log.error("search_web failed: %s", exc)
        return f"I was unable to search the web right now: {exc}"


# ---------------------------------------------------------------------------
# open_url
# ---------------------------------------------------------------------------


def open_url(url: str) -> str:
    """Open *url* in the system's default web browser.

    Parameters
    ----------
    url:
        The URL to open.  A scheme is prepended automatically if missing.

    Returns
    -------
    str
        Spoken confirmation or error message.
    """
    if not url.strip():
        return "Please provide a URL to open."

    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    try:
        subprocess.Popen(["open", url])
        log.info("open_url: %s", url)
        return f"Opening {url} in your browser."
    except Exception as exc:
        log.error("open_url(%r) failed: %s", url, exc)
        return f"I couldn't open that URL: {exc}"


# ---------------------------------------------------------------------------
# search_wikipedia
# ---------------------------------------------------------------------------


def search_wikipedia(topic: str) -> str:
    """Retrieve a summary of *topic* from Wikipedia.

    Uses the Wikipedia REST API (no key required).  Returns the first two
    sentences of the extract for brevity.

    Parameters
    ----------
    topic:
        The subject to look up.

    Returns
    -------
    str
        Spoken Wikipedia summary or an informative error message.
    """
    if not topic.strip():
        return "Please tell me what topic to look up on Wikipedia."

    encoded = urllib.parse.quote(topic.replace(" ", "_"))
    url = (
        f"https://en.wikipedia.org/api/rest_v1/page/summary/{encoded}"
    )
    try:
        response = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
        if response.status_code == 404:
            return f"I couldn't find a Wikipedia article for '{topic}'."
        response.raise_for_status()
        data = response.json()

        extract: str = data.get("extract", "")
        if not extract:
            return f"Wikipedia has no summary available for '{topic}'."

        # Keep it concise: at most two sentences
        sentences = extract.split(". ")
        summary = ". ".join(sentences[:2]).strip()
        if not summary.endswith("."):
            summary += "."

        log.info("search_wikipedia(%r): %d chars", topic, len(summary))
        return f"According to Wikipedia: {summary}"
    except requests.RequestException as exc:
        log.error("search_wikipedia failed: %s", exc)
        return f"I was unable to reach Wikipedia right now: {exc}"


# ---------------------------------------------------------------------------
# get_webpage_summary
# ---------------------------------------------------------------------------


def get_webpage_summary(url: str) -> str:
    """Fetch *url* and return a spoken summary of its visible text content.

    Strips navigation, scripts, and style elements, then returns the first
    ~500 characters of meaningful body text.

    Parameters
    ----------
    url:
        Web page URL to summarise.

    Returns
    -------
    str
        Spoken summary or error message.
    """
    if not url.strip():
        return "Please provide a URL to summarise."

    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    try:
        response = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        # Remove noisy tags
        for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
            tag.decompose()

        # Prefer <article> or <main>, fall back to <body>
        container = soup.find("article") or soup.find("main") or soup.body
        if container is None:
            return "I couldn't extract any readable content from that page."

        text = container.get_text(separator=" ", strip=True)
        # Collapse whitespace
        import re
        text = re.sub(r"\s+", " ", text).strip()

        if not text:
            return "The page appears to have no readable text content."

        snippet = text[:500]
        if len(text) > 500:
            snippet = snippet.rsplit(" ", 1)[0] + "…"

        log.info("get_webpage_summary(%r): %d chars extracted", url, len(text))
        return f"Here is a summary of that page: {snippet}"
    except requests.RequestException as exc:
        log.error("get_webpage_summary failed: %s", exc)
        return f"I was unable to fetch that page: {exc}"
