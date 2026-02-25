"""
imessage.py — iMessage send/read skills for MARS via AppleScript.

All functions return a ``str`` response that MARS speaks aloud.

Functions
---------
send_imessage  : Send an iMessage to a contact or phone number.
read_imessages : Read recent iMessages from a contact or general inbox.
"""

from __future__ import annotations

import sys

from utils.logger import get_logger
from utils.macos_utils import run_applescript

log = get_logger(__name__)


def _require_macos() -> str | None:
    """Return an error string if not on macOS, otherwise ``None``."""
    if sys.platform != "darwin":
        return "iMessage is only available on macOS."
    return None


# ---------------------------------------------------------------------------
# send_imessage
# ---------------------------------------------------------------------------


def send_imessage(recipient: str, message: str, confirmed: bool = False) -> str:
    """Send an iMessage to *recipient* with the given *message* text.

    Parameters
    ----------
    recipient:
        Phone number (e.g. ``"+15551234567"``) or Apple ID email address.
    message:
        The text body to send.
    confirmed:
        When ``False`` (default) a confirmation prompt is returned instead
        of sending.  Set to ``True`` to actually send.

    Returns
    -------
    str
        Spoken confirmation or error message.
    """
    err = _require_macos()
    if err:
        return err

    recipient = recipient.strip()
    message = message.strip()

    if not recipient:
        return "Please specify a recipient for the iMessage."
    if not message:
        return "Please provide a message to send."

    if not confirmed:
        return (
            f"Ready to send iMessage to {recipient}: '{message}'. "
            "Please confirm to proceed."
        )

    script = f"""
tell application "Messages"
    set targetService to 1st service whose service type = iMessage
    set targetBuddy to buddy "{recipient}" of targetService
    send "{message}" to targetBuddy
end tell
"""
    try:
        run_applescript(script)
        log.info("send_imessage: sent to %r", recipient)
        return f"iMessage sent to {recipient}."
    except RuntimeError as exc:
        log.error("send_imessage failed: %s", exc)
        return f"I couldn't send the iMessage: {exc}"


# ---------------------------------------------------------------------------
# read_imessages
# ---------------------------------------------------------------------------


def read_imessages(contact: str = "", count: int = 5) -> str:
    """Read the most recent iMessages.

    Parameters
    ----------
    contact:
        Optional name or number to filter messages by.  When empty, the most
        recent messages across all conversations are returned.
    count:
        Number of recent messages to retrieve (clamped to 1–20).

    Returns
    -------
    str
        Spoken summary of recent messages, or an error message.
    """
    err = _require_macos()
    if err:
        return err

    count = max(1, min(20, count))
    contact = contact.strip()

    if contact:
        script = f"""
tell application "Messages"
    set msgList to {{}}
    set allChats to every chat
    repeat with aChat in allChats
        set chatName to name of aChat
        if chatName contains "{contact}" then
            set msgList to messages of aChat
            exit repeat
        end if
    end repeat
    set resultText to ""
    set msgCount to count of msgList
    if msgCount = 0 then
        return "No messages found for {contact}."
    end if
    set startIdx to msgCount - {count - 1}
    if startIdx < 1 then set startIdx to 1
    repeat with i from startIdx to msgCount
        set aMsg to item i of msgList
        set msgText to text of aMsg
        set resultText to resultText & msgText & " | "
    end repeat
    return resultText
end tell
"""
    else:
        script = f"""
tell application "Messages"
    set resultText to ""
    set allChats to every chat
    set collected to 0
    repeat with aChat in allChats
        if collected >= {count} then exit repeat
        set msgList to messages of aChat
        set msgCount to count of msgList
        if msgCount > 0 then
            set aMsg to last message of aChat
            set chatName to name of aChat
            set msgText to text of aMsg
            set resultText to resultText & "From " & chatName & ": " & msgText & " | "
            set collected to collected + 1
        end if
    end repeat
    if resultText = "" then return "No recent messages found."
    return resultText
end tell
"""

    try:
        result = run_applescript(script)
        log.info("read_imessages: retrieved messages (contact=%r, count=%d)", contact, count)
        if not result or result.strip() == "":
            return "No messages found."
        return f"Here are your recent messages: {result}"
    except RuntimeError as exc:
        log.error("read_imessages failed: %s", exc)
        return f"I couldn't read your iMessages: {exc}"
