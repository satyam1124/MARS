"""
reminders.py — macOS Reminders and Alarm skills for MARS via AppleScript.

All functions return a ``str`` response that MARS speaks aloud.

Functions
---------
add_reminder      : Add a reminder to macOS Reminders via AppleScript.
get_reminders     : List reminders from a specific list or all lists.
complete_reminder : Mark a reminder as complete.
set_alarm         : Set a macOS Calendar alarm using AppleScript.
"""

from __future__ import annotations

import sys

from utils.logger import get_logger
from utils.macos_utils import run_applescript

log = get_logger(__name__)


def _require_macos() -> str | None:
    """Return an error string if not on macOS, otherwise ``None``."""
    if sys.platform != "darwin":
        return "Reminders and Alarms are only available on macOS."
    return None


# ---------------------------------------------------------------------------
# add_reminder
# ---------------------------------------------------------------------------


def add_reminder(
    title: str,
    notes: str = "",
    due_date: str = "",
) -> str:
    """Add a new reminder to macOS Reminders.

    Parameters
    ----------
    title:
        Short title / name of the reminder.
    notes:
        Optional longer notes for the reminder.
    due_date:
        Optional due date/time string in ``YYYY-MM-DD HH:MM`` format.
    returned:

    Returns
    -------
    str
        Spoken confirmation or error message.
    """
    err = _require_macos()
    if err:
        return err

    title = title.strip()
    if not title:
        return "Please provide a title for the reminder."

    # Build the AppleScript property list
    props = [f'name:"{title}"']
    if notes.strip():
        props.append(f'body:"{notes.strip()}"')
    if due_date.strip():
        # AppleScript date format: "MM/DD/YYYY HH:MM:SS"
        try:
            import datetime
            dt = datetime.datetime.fromisoformat(due_date.strip())
            apple_date = dt.strftime("%m/%d/%Y %H:%M:%S")
            props.append(f'due date:date "{apple_date}"')
        except ValueError:
            log.warning("add_reminder: could not parse due_date %r", due_date)

    props_str = ", ".join(props)
    script = f"""
tell application "Reminders"
    set newReminder to make new reminder at end of default list with properties {{{props_str}}}
end tell
"""
    try:
        run_applescript(script)
        log.info("add_reminder: added '%s'", title)
        msg = f"Reminder '{title}' has been added."
        if due_date.strip():
            msg += f" Due on {due_date}."
        return msg
    except RuntimeError as exc:
        log.error("add_reminder failed: %s", exc)
        return f"I couldn't add the reminder: {exc}"


# ---------------------------------------------------------------------------
# get_reminders
# ---------------------------------------------------------------------------


def get_reminders(list_name: str = "") -> str:
    """Get incomplete reminders from macOS Reminders.

    Parameters
    ----------
    list_name:
        Optional name of a specific Reminders list.  When empty, all lists
        are searched.

    Returns
    -------
    str
        Spoken summary of found reminders.
    """
    err = _require_macos()
    if err:
        return err

    list_name = list_name.strip()

    if list_name:
        script = f"""
tell application "Reminders"
    set resultText to ""
    try
        set theList to list "{list_name}"
        set incompleteReminders to (reminders in theList whose completed is false)
        repeat with r in incompleteReminders
            set resultText to resultText & (name of r) & " | "
        end repeat
    on error
        return "List not found: {list_name}"
    end try
    if resultText = "" then return "No incomplete reminders in {list_name}."
    return resultText
end tell
"""
    else:
        script = """
tell application "Reminders"
    set resultText to ""
    set allLists to every list
    repeat with aList in allLists
        set incompleteReminders to (reminders in aList whose completed is false)
        repeat with r in incompleteReminders
            set resultText to resultText & (name of r) & " | "
        end repeat
    end repeat
    if resultText = "" then return "You have no incomplete reminders."
    return resultText
end tell
"""

    try:
        result = run_applescript(script)
        log.info("get_reminders: retrieved (list=%r)", list_name)
        if not result or "no incomplete" in result.lower() or "not found" in result.lower():
            return result or "You have no incomplete reminders."
        return f"Your reminders: {result}"
    except RuntimeError as exc:
        log.error("get_reminders failed: %s", exc)
        return f"I couldn't retrieve your reminders: {exc}"


# ---------------------------------------------------------------------------
# complete_reminder
# ---------------------------------------------------------------------------


def complete_reminder(title: str) -> str:
    """Mark a reminder as complete in macOS Reminders.

    Parameters
    ----------
    title:
        The name / title of the reminder to mark as complete.

    Returns
    -------
    str
        Spoken confirmation or error message.
    """
    err = _require_macos()
    if err:
        return err

    title = title.strip()
    if not title:
        return "Please specify the title of the reminder to complete."

    script = f"""
tell application "Reminders"
    set found to false
    set allLists to every list
    repeat with aList in allLists
        set matchingReminders to (reminders in aList whose name = "{title}" and completed is false)
        if (count of matchingReminders) > 0 then
            set completed of (item 1 of matchingReminders) to true
            set found to true
            exit repeat
        end if
    end repeat
    if found then
        return "Completed"
    else
        return "Not found"
    end if
end tell
"""
    try:
        result = run_applescript(script)
        if "completed" in result.lower():
            log.info("complete_reminder: completed '%s'", title)
            return f"Reminder '{title}' marked as complete."
        else:
            return f"I couldn't find an incomplete reminder named '{title}'."
    except RuntimeError as exc:
        log.error("complete_reminder failed: %s", exc)
        return f"I couldn't complete the reminder: {exc}"


# ---------------------------------------------------------------------------
# set_alarm
# ---------------------------------------------------------------------------


def set_alarm(time_str: str, label: str = "MARS Alarm") -> str:
    """Set a macOS alarm by creating a Calendar event with an alarm trigger.

    Parameters
    ----------
    time_str:
        Time for the alarm in ``HH:MM`` or ``HH:MM AM/PM`` format.
        If no date is specified, today's date is assumed.
    label:
        Label / title for the alarm event.

    Returns
    -------
    str
        Spoken confirmation or error message.
    """
    err = _require_macos()
    if err:
        return err

    import datetime

    time_str = time_str.strip()
    label = label.strip() or "MARS Alarm"

    if not time_str:
        return "Please provide a time for the alarm."

    # Parse the time string
    parsed_dt: datetime.datetime | None = None
    for fmt in ("%I:%M %p", "%I:%M%p", "%H:%M", "%I %p", "%I%p"):
        try:
            t = datetime.datetime.strptime(time_str.upper(), fmt.upper())
            today = datetime.date.today()
            parsed_dt = datetime.datetime.combine(today, t.time())
            break
        except ValueError:
            continue

    if parsed_dt is None:
        return (
            f"I couldn't understand the time '{time_str}'. "
            "Please use a format like '7:30 AM' or '14:00'."
        )

    # Format for AppleScript
    apple_date = parsed_dt.strftime("%m/%d/%Y %H:%M:%S")

    script = f"""
tell application "Calendar"
    tell calendar "Home"
        set alarmEvent to make new event with properties {{summary:"{label}", start date:date "{apple_date}", end date:date "{apple_date}"}}
        tell alarmEvent
            make new sound alarm at end of sound alarms with properties {{trigger interval:0}}
        end tell
    end tell
end tell
"""
    try:
        run_applescript(script)
        display_time = parsed_dt.strftime("%-I:%M %p")
        log.info("set_alarm: set alarm '%s' at %s", label, display_time)
        return f"Alarm '{label}' set for {display_time}."
    except RuntimeError as exc:
        log.error("set_alarm failed: %s", exc)
        return f"I couldn't set the alarm: {exc}"
