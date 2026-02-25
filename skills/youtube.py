"""
youtube.py — YouTube search and download skill for MARS.

All functions return a ``str`` response that MARS speaks aloud.

Required packages (optional, installed on demand)
-----------------
yt-dlp : ``pip install yt-dlp``  (required for download_video)

Functions
---------
play_youtube    : Search YouTube and open the top result in the default browser.
download_video  : Download a YouTube video using yt-dlp.
"""

from __future__ import annotations

import subprocess
import urllib.parse
import webbrowser

from utils.logger import get_logger

log = get_logger(__name__)

_YT_SEARCH_URL = "https://www.youtube.com/results?search_query={query}"
_YT_WATCH_URL = "https://www.youtube.com/watch?v={video_id}"


# ---------------------------------------------------------------------------
# play_youtube
# ---------------------------------------------------------------------------


def play_youtube(query: str) -> str:
    """Search YouTube and open the top result in the default web browser.

    Uses the YouTube Data API if ``YOUTUBE_API_KEY`` is set in the
    environment; otherwise falls back to opening a YouTube search page
    directly in the browser.

    Parameters
    ----------
    query:
        Search term to find on YouTube.

    Returns
    -------
    str
        Spoken confirmation or error message.
    """
    query = query.strip()
    if not query:
        return "Please provide a search term for YouTube."

    import os

    api_key = os.environ.get("YOUTUBE_API_KEY", "")

    if api_key:
        # Try to use the YouTube Data API to get the actual top video ID
        try:
            import urllib.request
            import json

            encoded = urllib.parse.quote(query)
            api_url = (
                f"https://www.googleapis.com/youtube/v3/search"
                f"?part=snippet&maxResults=1&q={encoded}&type=video&key={api_key}"
            )
            with urllib.request.urlopen(api_url, timeout=10) as resp:
                data = json.loads(resp.read().decode())

            items = data.get("items", [])
            if items:
                video_id = items[0]["id"]["videoId"]
                video_title = items[0]["snippet"]["title"]
                watch_url = _YT_WATCH_URL.format(video_id=video_id)
                webbrowser.open(watch_url)
                log.info("play_youtube: opening video '%s' (%s)", video_title, video_id)
                return f"Opening YouTube video: {video_title}."
        except Exception as exc:  # noqa: BLE001
            log.warning("play_youtube API lookup failed, falling back to search: %s", exc)

    # Fallback: open a YouTube search results page
    encoded = urllib.parse.quote_plus(query)
    search_url = _YT_SEARCH_URL.format(query=encoded)
    try:
        webbrowser.open(search_url)
        log.info("play_youtube: opened search for %r", query)
        return f"Opening YouTube search for '{query}'."
    except Exception as exc:  # noqa: BLE001
        log.error("play_youtube failed: %s", exc)
        return f"I couldn't open YouTube: {exc}"


# ---------------------------------------------------------------------------
# download_video
# ---------------------------------------------------------------------------


def download_video(url: str, output_dir: str = "~/Downloads") -> str:
    """Download a YouTube video using yt-dlp.

    Parameters
    ----------
    url:
        Full YouTube video URL (e.g. ``"https://www.youtube.com/watch?v=..."``).
    output_dir:
        Directory to save the downloaded video.  Supports ``~`` expansion.
        Defaults to ``~/Downloads``.

    Returns
    -------
    str
        Spoken confirmation or error message.
    """
    import os
    from pathlib import Path

    url = url.strip()
    if not url:
        return "Please provide a YouTube video URL to download."

    # Expand ~ and resolve the output directory
    output_path = Path(os.path.expanduser(output_dir))
    try:
        output_path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return f"I couldn't create the output directory '{output_dir}': {exc}"

    # Check yt-dlp availability
    try:
        check = subprocess.run(
            ["yt-dlp", "--version"],
            capture_output=True,
            text=True,
        )
        if check.returncode != 0:
            raise FileNotFoundError
    except FileNotFoundError:
        # Try installing yt-dlp automatically
        log.info("download_video: yt-dlp not found, attempting pip install")
        install = subprocess.run(
            ["pip", "install", "yt-dlp", "--quiet"],
            capture_output=True,
            text=True,
        )
        if install.returncode != 0:
            return (
                "yt-dlp is not installed and automatic installation failed. "
                "Please run: pip install yt-dlp"
            )

    output_template = str(output_path / "%(title)s.%(ext)s")

    try:
        result = subprocess.run(
            [
                "yt-dlp",
                "--no-playlist",
                "--output", output_template,
                "--no-warnings",
                url,
            ],
            capture_output=True,
            text=True,
            timeout=300,
        )

        if result.returncode == 0:
            log.info("download_video: downloaded '%s' to '%s'", url, output_dir)
            return f"Video downloaded successfully to {output_dir}."
        else:
            error_msg = result.stderr.strip() or result.stdout.strip()
            log.error("download_video failed (rc=%d): %s", result.returncode, error_msg)
            # Extract a short error summary
            short_err = error_msg.splitlines()[-1] if error_msg else "Unknown error"
            return f"I couldn't download the video: {short_err}"
    except subprocess.TimeoutExpired:
        return "The download timed out. The video may be too large or the connection too slow."
    except Exception as exc:  # noqa: BLE001
        log.error("download_video failed: %s", exc)
        return f"I couldn't download the video: {exc}"
