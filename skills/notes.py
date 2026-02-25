"""
notes.py — Apple Notes skill for MARS via AppleScript.

All functions return a ``str`` response that MARS speaks aloud.

Functions
---------
create_note      : Create a new note in Apple Notes.
search_notes     : Search notes by keyword.
get_note_content : Retrieve the full text of a note by title.
append_to_note   : Append content to an existing note.
"""

from __future__ import annotations

import sys

from utils.logger import get_logger
from utils.macos_utils import run_applescript

log = get_logger(__name__)


def _require_macos() -> str | None:
    """Return an error string if not on macOS, otherwise ``None``."""
    if sys.platform != "darwin":
        return "Apple Notes is only available on macOS."
    return None


def _escape(text: str) -> str:
    """Escape double-quotes for safe embedding in AppleScript strings."""
    return text.replace("\\", "\\\\").replace('"', '\\"')


# ---------------------------------------------------------------------------
# create_note
# ---------------------------------------------------------------------------


def create_note(title: str, body: str, folder: str = "Notes") -> str:
    """Create a new note in Apple Notes.

    Parameters
    ----------
    title:
        Note title.
    body:
        Note body text.
    folder:
        Name of the Notes folder to create the note in (default ``"Notes"``).

    Returns
    -------
    str
        Spoken confirmation or error message.
    """
    err = _require_macos()
    if err:
        return err

    title = title.strip()
    body = body.strip()
    folder = folder.strip() or "Notes"

    if not title:
        return "Please provide a title for the note."

    safe_title = _escape(title)
    safe_body = _escape(body)
    safe_folder = _escape(folder)

    full_body = f"{safe_title}\\n\\n{safe_body}"

    script = f"""
tell application "Notes"
    tell account "iCloud"
        try
            set targetFolder to folder "{safe_folder}"
        on error
            set targetFolder to make new folder with properties {{name:"{safe_folder}"}}
        end try
        make new note at targetFolder with properties {{name:"{safe_title}", body:"{full_body}"}}
    end tell
end tell
"""
    try:
        run_applescript(script)
        log.info("create_note: created '%s' in folder '%s'", title, folder)
        return f"Note '{title}' created in the '{folder}' folder."
    except RuntimeError as exc:
        log.error("create_note failed: %s", exc)
        return f"I couldn't create the note: {exc}"


# ---------------------------------------------------------------------------
# search_notes
# ---------------------------------------------------------------------------


def search_notes(query: str) -> str:
    """Search Apple Notes for notes matching *query*.

    Parameters
    ----------
    query:
        Keyword or phrase to search for.

    Returns
    -------
    str
        Spoken list of matching note titles.
    """
    err = _require_macos()
    if err:
        return err

    query = query.strip()
    if not query:
        return "Please provide a search term."

    safe_query = _escape(query)

    script = f"""
tell application "Notes"
    set matchingNotes to every note whose name contains "{safe_query}" or body contains "{safe_query}"
    set resultText to ""
    repeat with n in matchingNotes
        set resultText to resultText & (name of n) & " | "
    end repeat
    if resultText = "" then return "No notes found matching: {safe_query}"
    return resultText
end tell
"""
    try:
        result = run_applescript(script)
        log.info("search_notes: query=%r", query)
        if "no notes found" in result.lower():
            return result
        return f"Found notes matching '{query}': {result}"
    except RuntimeError as exc:
        log.error("search_notes failed: %s", exc)
        return f"I couldn't search your notes: {exc}"


# ---------------------------------------------------------------------------
# get_note_content
# ---------------------------------------------------------------------------


def get_note_content(title: str) -> str:
    """Retrieve the text content of an Apple Note by title.

    Parameters
    ----------
    title:
        The exact or partial title of the note to retrieve.

    Returns
    -------
    str
        The note content, or an error message.
    """
    err = _require_macos()
    if err:
        return err

    title = title.strip()
    if not title:
        return "Please provide the title of the note to retrieve."

    safe_title = _escape(title)

    script = f"""
tell application "Notes"
    set matchingNotes to every note whose name contains "{safe_title}"
    if (count of matchingNotes) = 0 then
        return "No note found with title: {safe_title}"
    end if
    set targetNote to item 1 of matchingNotes
    return body of targetNote
end tell
"""
    try:
        result = run_applescript(script)
        log.info("get_note_content: retrieved '%s'", title)
        if "no note found" in result.lower():
            return result
        # Strip HTML tags from Notes body
        import re
        clean = re.sub(r"<[^>]+>", " ", result)
        clean = re.sub(r"\s+", " ", clean).strip()
        if not clean:
            return f"The note '{title}' appears to be empty."
        # Truncate for speech
        if len(clean) > 500:
            clean = clean[:500].rsplit(" ", 1)[0] + "… and more."
        return f"Note '{title}': {clean}"
    except RuntimeError as exc:
        log.error("get_note_content failed: %s", exc)
        return f"I couldn't retrieve the note: {exc}"


# ---------------------------------------------------------------------------
# append_to_note
# ---------------------------------------------------------------------------


def append_to_note(title: str, content: str) -> str:
    """Append *content* to an existing Apple Note.

    Parameters
    ----------
    title:
        The exact or partial title of the note to append to.
    content:
        Text to append to the note body.

    Returns
    -------
    str
        Spoken confirmation or error message.
    """
    err = _require_macos()
    if err:
        return err

    title = title.strip()
    content = content.strip()

    if not title:
        return "Please provide the title of the note to append to."
    if not content:
        return "Please provide the content to append to the note."

    safe_title = _escape(title)
    safe_content = _escape(content)

    script = f"""
tell application "Notes"
    set matchingNotes to every note whose name contains "{safe_title}"
    if (count of matchingNotes) = 0 then
        return "No note found with title: {safe_title}"
    end if
    set targetNote to item 1 of matchingNotes
    set currentBody to body of targetNote
    set body of targetNote to currentBody & "<br>{safe_content}"
    return "OK"
end tell
"""
    try:
        result = run_applescript(script)
        if "no note found" in result.lower():
            return result
        log.info("append_to_note: appended to '%s'", title)
        return f"Content appended to note '{title}'."
    except RuntimeError as exc:
        log.error("append_to_note failed: %s", exc)
        return f"I couldn't append to the note: {exc}"
