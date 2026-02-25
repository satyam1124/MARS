"""
media_control.py — System-wide media controls for MARS via AppleScript.

All functions return a ``str`` response that MARS speaks aloud.

Functions
---------
play_pause    : Toggle play/pause for the active media player.
volume_up     : Increase system volume by a given amount.
volume_down   : Decrease system volume by a given amount.
mute_toggle   : Toggle system audio mute.
"""

from __future__ import annotations

import sys

from utils.logger import get_logger
from utils.macos_utils import get_volume, run_applescript, run_command, set_volume

log = get_logger(__name__)


def _require_macos() -> str | None:
    """Return an error string if not on macOS, otherwise ``None``."""
    if sys.platform != "darwin":
        return "Media controls are only available on macOS."
    return None


# ---------------------------------------------------------------------------
# play_pause
# ---------------------------------------------------------------------------


def play_pause() -> str:
    """Toggle play/pause for the currently active media player.

    Uses the macOS media key simulation via AppleScript to send a
    play/pause key event.

    Returns
    -------
    str
        Spoken confirmation or error message.
    """
    err = _require_macos()
    if err:
        return err

    # Send the play/pause media key (key code 100 = F8 = play/pause on Apple keyboards)
    script = """
tell application "System Events"
    key code 100
end tell
"""
    try:
        run_applescript(script)
        log.info("play_pause: toggled play/pause")
        return "Play/pause toggled."
    except RuntimeError as exc:
        log.error("play_pause failed: %s", exc)
        return f"I couldn't toggle play/pause: {exc}"


# ---------------------------------------------------------------------------
# volume_up
# ---------------------------------------------------------------------------


def volume_up(amount: int = 10) -> str:
    """Increase the system output volume by *amount* percent.

    Parameters
    ----------
    amount:
        Percentage points to increase volume (clamped to 1–100).

    Returns
    -------
    str
        Spoken confirmation with the new volume level.
    """
    err = _require_macos()
    if err:
        return err

    amount = max(1, min(100, amount))
    current = get_volume()
    if current < 0:
        current = 50  # sensible fallback

    new_level = min(100, current + amount)
    result = set_volume(new_level)
    log.info("volume_up: %d → %d", current, new_level)
    return result


# ---------------------------------------------------------------------------
# volume_down
# ---------------------------------------------------------------------------


def volume_down(amount: int = 10) -> str:
    """Decrease the system output volume by *amount* percent.

    Parameters
    ----------
    amount:
        Percentage points to decrease volume (clamped to 1–100).

    Returns
    -------
    str
        Spoken confirmation with the new volume level.
    """
    err = _require_macos()
    if err:
        return err

    amount = max(1, min(100, amount))
    current = get_volume()
    if current < 0:
        current = 50  # sensible fallback

    new_level = max(0, current - amount)
    result = set_volume(new_level)
    log.info("volume_down: %d → %d", current, new_level)
    return result


# ---------------------------------------------------------------------------
# mute_toggle
# ---------------------------------------------------------------------------


def mute_toggle() -> str:
    """Toggle the system audio mute state.

    Reads the current mute setting via AppleScript and toggles it.

    Returns
    -------
    str
        Spoken confirmation of the new mute state.
    """
    err = _require_macos()
    if err:
        return err

    # Read current mute state
    read_script = "output muted of (get volume settings)"
    try:
        result = run_applescript(read_script)
        currently_muted = result.strip().lower() == "true"
    except RuntimeError:
        currently_muted = False

    new_muted = not currently_muted
    mute_value = "true" if new_muted else "false"
    set_script = f"set volume output muted {mute_value}"

    try:
        run_applescript(set_script)
        state = "muted" if new_muted else "unmuted"
        log.info("mute_toggle: %s", state)
        return f"Audio {state}."
    except RuntimeError as exc:
        log.error("mute_toggle failed: %s", exc)
        return f"I couldn't toggle mute: {exc}"
