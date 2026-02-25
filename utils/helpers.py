"""
helpers.py — Common helper functions for MARS.

Functions
---------
format_size       : Convert byte counts to human-readable strings.
truncate_text     : Truncate a string to a maximum length with an ellipsis.
sanitize_filename : Strip characters that are unsafe in file-system paths.
parse_duration    : Parse a natural-language duration string into seconds.
confirm_action    : Display a yes/no CLI prompt and return the user's choice.
format_list       : Format a Python list into a natural-language speech string.
extract_number    : Extract the first numeric value from a string.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Final

# ---------------------------------------------------------------------------
# format_size
# ---------------------------------------------------------------------------

_SIZE_UNITS: Final[list[str]] = ["B", "KB", "MB", "GB", "TB", "PB"]


def format_size(bytes: int) -> str:  # noqa: A002  (shadows built-in intentionally)
    """Convert *bytes* to a human-readable size string.

    Parameters
    ----------
    bytes:
        Non-negative integer byte count.

    Returns
    -------
    str
        Formatted string such as ``"1.45 MB"`` or ``"512 B"``.

    Examples
    --------
    >>> format_size(0)
    '0 B'
    >>> format_size(1536)
    '1.50 KB'
    >>> format_size(1_073_741_824)
    '1.00 GB'
    """
    if bytes < 0:
        raise ValueError(f"byte count must be non-negative, got {bytes}")
    value = float(bytes)
    for unit in _SIZE_UNITS[:-1]:
        if abs(value) < 1024.0:
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.2f} {unit}"
        value /= 1024.0
    return f"{value:.2f} {_SIZE_UNITS[-1]}"


# ---------------------------------------------------------------------------
# truncate_text
# ---------------------------------------------------------------------------


def truncate_text(text: str, max_len: int) -> str:
    """Return *text* truncated to *max_len* characters, appending ``…`` if cut.

    Parameters
    ----------
    text:
        Input string.
    max_len:
        Maximum allowed length of the returned string **including** the
        ellipsis character when truncation occurs.

    Returns
    -------
    str
        Truncated (or unchanged) string.

    Examples
    --------
    >>> truncate_text("Hello, world!", 8)
    'Hello, …'
    >>> truncate_text("Hi", 10)
    'Hi'
    """
    if max_len < 1:
        raise ValueError(f"max_len must be >= 1, got {max_len}")
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"


# ---------------------------------------------------------------------------
# sanitize_filename
# ---------------------------------------------------------------------------

_UNSAFE_CHARS_RE: Final[re.Pattern[str]] = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_MULTI_SPACE_RE: Final[re.Pattern[str]] = re.compile(r"\s+")
_LEADING_TRAILING_DOT_DASH: Final[re.Pattern[str]] = re.compile(r"^[.\-\s]+|[.\-\s]+$")


def sanitize_filename(name: str) -> str:
    """Return *name* with characters that are unsafe for file-system paths removed.

    - Normalises unicode to NFC.
    - Removes control characters and ``< > : " / \\ | ? *``.
    - Collapses whitespace to a single space and strips leading/trailing dots,
      dashes, and spaces.
    - Falls back to ``"untitled"`` if the result would be empty.

    Parameters
    ----------
    name:
        Proposed file/directory name (not a full path).

    Returns
    -------
    str
        Sanitised filename string.

    Examples
    --------
    >>> sanitize_filename('hello/world?.txt')
    'helloworld.txt'
    >>> sanitize_filename('   ..  ')
    'untitled'
    """
    # Normalise unicode
    name = unicodedata.normalize("NFC", name)
    # Remove unsafe chars
    name = _UNSAFE_CHARS_RE.sub("", name)
    # Collapse whitespace
    name = _MULTI_SPACE_RE.sub(" ", name).strip()
    # Strip leading/trailing dots and dashes
    name = _LEADING_TRAILING_DOT_DASH.sub("", name)
    return name if name else "untitled"


# ---------------------------------------------------------------------------
# parse_duration
# ---------------------------------------------------------------------------

# Maps unit keywords → seconds multiplier
_DURATION_UNITS: Final[dict[str, int]] = {
    "second": 1,
    "seconds": 1,
    "sec": 1,
    "secs": 1,
    "s": 1,
    "minute": 60,
    "minutes": 60,
    "min": 60,
    "mins": 60,
    "m": 60,
    "hour": 3600,
    "hours": 3600,
    "hr": 3600,
    "hrs": 3600,
    "h": 3600,
    "day": 86400,
    "days": 86400,
    "d": 86400,
    "week": 604800,
    "weeks": 604800,
    "w": 604800,
}

_DURATION_TOKEN_RE: Final[re.Pattern[str]] = re.compile(
    r"(\d+(?:\.\d+)?)\s*([a-zA-Z]+)", re.IGNORECASE
)


def parse_duration(text: str) -> int:
    """Parse a human-readable duration string into a total number of seconds.

    Supports combinations such as ``"1 hour 30 minutes"``,
    ``"5 mins"``, ``"2h 15m"``, ``"90 seconds"``, etc.

    Parameters
    ----------
    text:
        Natural-language duration string.

    Returns
    -------
    int
        Total duration in seconds.  Returns ``0`` if no recognisable tokens
        are found.

    Examples
    --------
    >>> parse_duration("5 minutes")
    300
    >>> parse_duration("1 hour 30 minutes")
    5400
    >>> parse_duration("2h 15m 10s")
    8110
    """
    total = 0
    for match in _DURATION_TOKEN_RE.finditer(text):
        quantity_str, unit = match.group(1), match.group(2).lower()
        multiplier = _DURATION_UNITS.get(unit)
        if multiplier is not None:
            total += int(float(quantity_str) * multiplier)
    return total


# ---------------------------------------------------------------------------
# confirm_action
# ---------------------------------------------------------------------------


def confirm_action(action: str) -> bool:
    """Display a yes/no CLI prompt and return ``True`` if the user confirms.

    The prompt keeps asking until a valid response (``y``, ``yes``, ``n``,
    ``no``) is given.

    Parameters
    ----------
    action:
        Short description of the action to confirm, e.g.
        ``"delete all files"``.

    Returns
    -------
    bool
        ``True`` if the user answered *yes*, ``False`` otherwise.

    Examples
    --------
    >>> # confirm_action("reformat drive")  # interactive — not shown here
    """
    while True:
        try:
            answer = input(f"⚠️  Are you sure you want to {action}? [y/n]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return False
        if answer in {"y", "yes"}:
            return True
        if answer in {"n", "no"}:
            return False
        print("Please enter 'y' or 'n'.")


# ---------------------------------------------------------------------------
# format_list
# ---------------------------------------------------------------------------


def format_list(items: list) -> str:
    """Format *items* into a natural-language enumeration suitable for speech.

    Parameters
    ----------
    items:
        Sequence of items.  Each item is converted to a string via ``str()``.

    Returns
    -------
    str
        - Empty list → ``""``
        - Single item → the item itself.
        - Two items → ``"A and B"``.
        - Three or more → ``"A, B, and C"``.

    Examples
    --------
    >>> format_list([])
    ''
    >>> format_list(["apples"])
    'apples'
    >>> format_list(["apples", "bananas"])
    'apples and bananas'
    >>> format_list(["apples", "bananas", "cherries"])
    'apples, bananas, and cherries'
    """
    str_items = [str(i) for i in items]
    if not str_items:
        return ""
    if len(str_items) == 1:
        return str_items[0]
    if len(str_items) == 2:
        return f"{str_items[0]} and {str_items[1]}"
    return ", ".join(str_items[:-1]) + f", and {str_items[-1]}"


# ---------------------------------------------------------------------------
# extract_number
# ---------------------------------------------------------------------------

_NUMBER_RE: Final[re.Pattern[str]] = re.compile(
    r"[-+]?\d{1,3}(?:,\d{3})*(?:\.\d+)?|[-+]?\d+(?:\.\d+)?"
)


def extract_number(text: str) -> float | None:
    """Extract the first numeric value from *text*.

    Handles integers, decimals, and numbers with thousand separators
    (e.g. ``"1,024"``).

    Parameters
    ----------
    text:
        Input string potentially containing a number.

    Returns
    -------
    float | None
        The first number found as a ``float``, or ``None`` if none is present.

    Examples
    --------
    >>> extract_number("Set volume to 75 percent")
    75.0
    >>> extract_number("no numbers here") is None
    True
    >>> extract_number("pi is approximately 3.14159")
    3.14159
    """
    match = _NUMBER_RE.search(text)
    if match is None:
        return None
    return float(match.group().replace(",", ""))
