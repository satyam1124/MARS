"""
music_player.py — Spotify and Apple Music playback skill for MARS.

All functions return a ``str`` response that MARS speaks aloud.

Required environment variables
-------------------------------
SPOTIFY_CLIENT_ID     : Spotify application client ID.
SPOTIFY_CLIENT_SECRET : Spotify application client secret.
SPOTIFY_REDIRECT_URI  : OAuth redirect URI (e.g. ``http://localhost:8888/callback``).

Required packages
-----------------
spotipy : ``pip install spotipy``

Functions
---------
play_spotify       : Search Spotify and play a track, album, or artist.
pause_music        : Pause Spotify playback.
resume_music       : Resume Spotify playback.
next_track         : Skip to the next Spotify track.
previous_track     : Go to the previous Spotify track.
get_current_track  : Get the currently playing Spotify track.
play_apple_music   : Open Apple Music and play a search query via AppleScript.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from utils.logger import get_logger

log = get_logger(__name__)

_SPOTIFY_CACHE_PATH = Path(__file__).resolve().parents[1] / "config" / ".spotify_cache"
_SPOTIFY_SCOPE = (
    "user-read-playback-state "
    "user-modify-playback-state "
    "user-read-currently-playing "
    "streaming"
)


def _get_spotify():
    """Return an authenticated :class:`spotipy.Spotify` client.

    Raises
    ------
    RuntimeError
        If spotipy is not installed or credentials are missing.
    """
    try:
        import spotipy  # type: ignore[import]
        from spotipy.oauth2 import SpotifyOAuth  # type: ignore[import]
    except ImportError as exc:
        raise RuntimeError(
            f"spotipy is not installed: {exc}. Run: pip install spotipy"
        ) from exc

    client_id = os.environ.get("SPOTIFY_CLIENT_ID", "")
    client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET", "")
    redirect_uri = os.environ.get("SPOTIFY_REDIRECT_URI", "http://localhost:8888/callback")

    if not client_id or not client_secret:
        raise RuntimeError(
            "Spotify credentials not set. Please set SPOTIFY_CLIENT_ID and "
            "SPOTIFY_CLIENT_SECRET environment variables."
        )

    auth_manager = SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        scope=_SPOTIFY_SCOPE,
        cache_path=str(_SPOTIFY_CACHE_PATH),
        open_browser=True,
    )
    return spotipy.Spotify(auth_manager=auth_manager)


# ---------------------------------------------------------------------------
# play_spotify
# ---------------------------------------------------------------------------


def play_spotify(query: str) -> str:
    """Search Spotify and play the best matching track.

    Parameters
    ----------
    query:
        Search query (artist, track, or album name).

    Returns
    -------
    str
        Spoken confirmation or error message.
    """
    query = query.strip()
    if not query:
        return "Please provide a song, artist, or album to play on Spotify."

    try:
        sp = _get_spotify()
    except RuntimeError as exc:
        return str(exc)

    try:
        results = sp.search(q=query, type="track", limit=1)
        tracks = results.get("tracks", {}).get("items", [])
        if not tracks:
            return f"I couldn't find any Spotify tracks matching '{query}'."

        track = tracks[0]
        track_uri = track["uri"]
        track_name = track["name"]
        artist_name = track["artists"][0]["name"] if track.get("artists") else "Unknown artist"

        # Get active devices
        devices = sp.devices().get("devices", [])
        if not devices:
            return (
                "No active Spotify device found. "
                "Please open Spotify on a device and try again."
            )

        device_id = devices[0]["id"]
        sp.start_playback(device_id=device_id, uris=[track_uri])
        log.info("play_spotify: playing '%s' by %s", track_name, artist_name)
        return f"Playing '{track_name}' by {artist_name} on Spotify."
    except Exception as exc:  # noqa: BLE001
        log.error("play_spotify failed: %s", exc)
        return f"I couldn't play that on Spotify: {exc}"


# ---------------------------------------------------------------------------
# pause_music
# ---------------------------------------------------------------------------


def pause_music() -> str:
    """Pause the current Spotify playback.

    Returns
    -------
    str
        Spoken confirmation or error message.
    """
    try:
        sp = _get_spotify()
    except RuntimeError as exc:
        return str(exc)

    try:
        sp.pause_playback()
        log.info("pause_music: paused Spotify")
        return "Spotify paused."
    except Exception as exc:  # noqa: BLE001
        log.error("pause_music failed: %s", exc)
        return f"I couldn't pause Spotify: {exc}"


# ---------------------------------------------------------------------------
# resume_music
# ---------------------------------------------------------------------------


def resume_music() -> str:
    """Resume Spotify playback.

    Returns
    -------
    str
        Spoken confirmation or error message.
    """
    try:
        sp = _get_spotify()
    except RuntimeError as exc:
        return str(exc)

    try:
        sp.start_playback()
        log.info("resume_music: resumed Spotify")
        return "Spotify resumed."
    except Exception as exc:  # noqa: BLE001
        log.error("resume_music failed: %s", exc)
        return f"I couldn't resume Spotify: {exc}"


# ---------------------------------------------------------------------------
# next_track
# ---------------------------------------------------------------------------


def next_track() -> str:
    """Skip to the next track on Spotify.

    Returns
    -------
    str
        Spoken confirmation or error message.
    """
    try:
        sp = _get_spotify()
    except RuntimeError as exc:
        return str(exc)

    try:
        sp.next_track()
        log.info("next_track: skipped to next")
        return "Skipping to the next track."
    except Exception as exc:  # noqa: BLE001
        log.error("next_track failed: %s", exc)
        return f"I couldn't skip to the next track: {exc}"


# ---------------------------------------------------------------------------
# previous_track
# ---------------------------------------------------------------------------


def previous_track() -> str:
    """Go back to the previous Spotify track.

    Returns
    -------
    str
        Spoken confirmation or error message.
    """
    try:
        sp = _get_spotify()
    except RuntimeError as exc:
        return str(exc)

    try:
        sp.previous_track()
        log.info("previous_track: went to previous")
        return "Going back to the previous track."
    except Exception as exc:  # noqa: BLE001
        log.error("previous_track failed: %s", exc)
        return f"I couldn't go to the previous track: {exc}"


# ---------------------------------------------------------------------------
# get_current_track
# ---------------------------------------------------------------------------


def get_current_track() -> str:
    """Return what is currently playing on Spotify.

    Returns
    -------
    str
        Spoken description of the current track, or a message if nothing is
        playing.
    """
    try:
        sp = _get_spotify()
    except RuntimeError as exc:
        return str(exc)

    try:
        current = sp.current_playback()
        if not current or not current.get("is_playing"):
            return "Nothing is currently playing on Spotify."

        item = current.get("item")
        if not item:
            return "Spotify is playing but I couldn't identify the current track."

        track_name = item.get("name", "Unknown track")
        artists = item.get("artists", [])
        artist_name = artists[0]["name"] if artists else "Unknown artist"
        album = item.get("album", {}).get("name", "")

        msg = f"Currently playing '{track_name}' by {artist_name}"
        if album:
            msg += f" from the album '{album}'"
        msg += "."
        log.info("get_current_track: %s by %s", track_name, artist_name)
        return msg
    except Exception as exc:  # noqa: BLE001
        log.error("get_current_track failed: %s", exc)
        return f"I couldn't get the current track: {exc}"


# ---------------------------------------------------------------------------
# play_apple_music
# ---------------------------------------------------------------------------


def play_apple_music(query: str) -> str:
    """Search and play a track in Apple Music via AppleScript.

    Parameters
    ----------
    query:
        Song, artist, or album to search for in Apple Music.

    Returns
    -------
    str
        Spoken confirmation or error message.
    """
    if sys.platform != "darwin":
        return "Apple Music is only available on macOS."

    from utils.macos_utils import run_applescript

    query = query.strip()
    if not query:
        return "Please provide a song or artist to play in Apple Music."

    safe_query = query.replace('"', '\\"')

    script = f"""
tell application "Music"
    activate
    search playlist "Library" for "{safe_query}"
    if (count of results) > 0 then
        set theTrack to item 1 of results
        play theTrack
        return name of theTrack
    else
        return "Not found"
    end if
end tell
"""
    try:
        result = run_applescript(script)
        if result.lower() == "not found" or "not found" in result.lower():
            # Fallback: just open the app and let the user search
            run_applescript('tell application "Music" to activate')
            return (
                f"I couldn't find '{query}' in your Apple Music library. "
                "Apple Music is now open."
            )
        log.info("play_apple_music: playing '%s'", result)
        return f"Playing '{result}' in Apple Music."
    except RuntimeError as exc:
        log.error("play_apple_music failed: %s", exc)
        return f"I couldn't play that in Apple Music: {exc}"
