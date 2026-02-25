"""
facetime.py — FaceTime call skill for MARS via AppleScript.

All functions return a ``str`` response that MARS speaks aloud.

Functions
---------
make_facetime_call : Initiate a FaceTime audio or video call.
"""

from __future__ import annotations

import sys

from utils.logger import get_logger
from utils.macos_utils import run_applescript

log = get_logger(__name__)


def _require_macos() -> str | None:
    """Return an error string if not on macOS, otherwise ``None``."""
    if sys.platform != "darwin":
        return "FaceTime is only available on macOS."
    return None


# ---------------------------------------------------------------------------
# make_facetime_call
# ---------------------------------------------------------------------------


def make_facetime_call(contact: str, confirmed: bool = False) -> str:
    """Initiate a FaceTime call to *contact*.

    Uses the ``facetime://`` URL scheme to open FaceTime and dial the
    specified contact, phone number, or Apple ID email address.

    Parameters
    ----------
    contact:
        Name, phone number, or Apple ID email of the person to call.
    confirmed:
        When ``False`` (default) a confirmation prompt is returned.  Set to
        ``True`` to actually initiate the call.

    Returns
    -------
    str
        Spoken confirmation or error message.
    """
    err = _require_macos()
    if err:
        return err

    contact = contact.strip()
    if not contact:
        return "Please specify a contact name or number for the FaceTime call."

    if not confirmed:
        return (
            f"Ready to start a FaceTime call with {contact}. "
            "Please confirm to proceed."
        )

    # Use the facetime:// URL scheme — works with phone numbers and Apple IDs
    script = f'open location "facetime://{contact}"'
    try:
        run_applescript(script)
        log.info("make_facetime_call: calling %r", contact)
        return f"Starting FaceTime call with {contact}."
    except RuntimeError as exc:
        log.error("make_facetime_call failed: %s", exc)
        # Fallback: open FaceTime app directly
        try:
            fallback = f"""
tell application "FaceTime"
    activate
end tell
"""
            run_applescript(fallback)
            return f"FaceTime is open. Please call {contact} manually: {exc}"
        except RuntimeError as exc2:
            log.error("make_facetime_call fallback failed: %s", exc2)
            return f"I couldn't initiate the FaceTime call: {exc}"
