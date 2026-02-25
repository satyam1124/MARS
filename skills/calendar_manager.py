"""
calendar_manager.py — Google Calendar skill for MARS.

All functions return a ``str`` response that MARS speaks aloud.

Required environment variables
-------------------------------
GOOGLE_CREDENTIALS_PATH : Path to a Google OAuth2 credentials JSON file.
                          Download from Google Cloud Console.

Required packages
-----------------
google-api-python-client : ``pip install google-api-python-client``
google-auth-httplib2     : ``pip install google-auth-httplib2``
google-auth-oauthlib     : ``pip install google-auth-oauthlib``

Functions
---------
get_todays_events    : List today's calendar events.
get_upcoming_events  : List events for the next *n* days.
create_event         : Create a new calendar event.
delete_event         : Delete a calendar event by ID.
"""

from __future__ import annotations

import datetime
import os
from pathlib import Path

from utils.logger import get_logger

log = get_logger(__name__)

_SCOPES = ["https://www.googleapis.com/auth/calendar"]
_TOKEN_PATH = Path(__file__).resolve().parents[1] / "config" / "google_token.json"


def _get_calendar_service():
    """Return an authenticated Google Calendar API service object.

    Raises
    ------
    RuntimeError
        If credentials are missing or authentication fails.
    """
    try:
        from google.oauth2.credentials import Credentials  # type: ignore[import]
        from google_auth_oauthlib.flow import InstalledAppFlow  # type: ignore[import]
        from google.auth.transport.requests import Request  # type: ignore[import]
        from googleapiclient.discovery import build  # type: ignore[import]
    except ImportError as exc:
        raise RuntimeError(
            f"Google API packages not installed: {exc}. "
            "Run: pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib"
        ) from exc

    credentials_path = os.environ.get("GOOGLE_CREDENTIALS_PATH", "")
    if not credentials_path or not Path(credentials_path).exists():
        raise RuntimeError(
            "GOOGLE_CREDENTIALS_PATH environment variable is not set or the file does not exist."
        )

    creds: Credentials | None = None
    if _TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(_TOKEN_PATH), _SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, _SCOPES)
            creds = flow.run_local_server(port=0)
        _TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
        _TOKEN_PATH.write_text(creds.to_json())

    return build("calendar", "v3", credentials=creds)


def _format_event(event: dict) -> str:
    """Format a Google Calendar event dict into a spoken string."""
    summary = event.get("summary", "Untitled event")
    start = event.get("start", {})
    start_str = start.get("dateTime", start.get("date", ""))
    if "T" in start_str:
        try:
            dt = datetime.datetime.fromisoformat(start_str.replace("Z", "+00:00"))
            start_str = dt.strftime("%-I:%M %p")
        except ValueError:
            pass
    return f"{summary} at {start_str}" if start_str else summary


# ---------------------------------------------------------------------------
# get_todays_events
# ---------------------------------------------------------------------------


def get_todays_events() -> str:
    """Return a spoken list of today's Google Calendar events.

    Returns
    -------
    str
        Spoken summary of today's events.
    """
    try:
        service = _get_calendar_service()
    except RuntimeError as exc:
        return str(exc)

    now = datetime.datetime.now(tz=datetime.timezone.utc)
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    end_of_day = now.replace(hour=23, minute=59, second=59, microsecond=0).isoformat()

    try:
        result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=start_of_day,
                timeMax=end_of_day,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        events = result.get("items", [])
        if not events:
            return "You have no events scheduled for today."

        descriptions = [_format_event(e) for e in events]
        count = len(descriptions)
        event_word = "event" if count == 1 else "events"
        return f"You have {count} {event_word} today: " + ", ".join(descriptions) + "."
    except Exception as exc:  # noqa: BLE001
        log.error("get_todays_events failed: %s", exc)
        return f"I couldn't retrieve today's events: {exc}"


# ---------------------------------------------------------------------------
# get_upcoming_events
# ---------------------------------------------------------------------------


def get_upcoming_events(days: int = 7) -> str:
    """Return a spoken list of upcoming events over the next *days* days.

    Parameters
    ----------
    days:
        Number of days to look ahead (clamped to 1–90).

    Returns
    -------
    str
        Spoken summary of upcoming events.
    """
    days = max(1, min(90, days))

    try:
        service = _get_calendar_service()
    except RuntimeError as exc:
        return str(exc)

    now = datetime.datetime.now(tz=datetime.timezone.utc)
    end = now + datetime.timedelta(days=days)

    try:
        result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=now.isoformat(),
                timeMax=end.isoformat(),
                singleEvents=True,
                orderBy="startTime",
                maxResults=20,
            )
            .execute()
        )
        events = result.get("items", [])
        if not events:
            return f"You have no events in the next {days} days."

        descriptions = [_format_event(e) for e in events]
        count = len(descriptions)
        event_word = "event" if count == 1 else "events"
        return (
            f"You have {count} upcoming {event_word} in the next {days} days: "
            + ", ".join(descriptions)
            + "."
        )
    except Exception as exc:  # noqa: BLE001
        log.error("get_upcoming_events failed: %s", exc)
        return f"I couldn't retrieve upcoming events: {exc}"


# ---------------------------------------------------------------------------
# create_event
# ---------------------------------------------------------------------------


def create_event(
    title: str,
    date: str,
    time: str,
    duration_minutes: int = 60,
    description: str = "",
) -> str:
    """Create a new Google Calendar event.

    Parameters
    ----------
    title:
        Event title / summary.
    date:
        Date string in ``YYYY-MM-DD`` format.
    time:
        Start time string in ``HH:MM`` (24-hour) format.
    duration_minutes:
        Duration of the event in minutes (default 60).
    description:
        Optional event description.

    Returns
    -------
    str
        Spoken confirmation or error message.
    """
    title = title.strip()
    date = date.strip()
    time = time.strip()

    if not title:
        return "Please provide a title for the event."
    if not date:
        return "Please provide a date for the event."
    if not time:
        return "Please provide a time for the event."

    try:
        start_dt = datetime.datetime.fromisoformat(f"{date}T{time}:00")
    except ValueError:
        return f"I couldn't parse the date '{date}' and time '{time}'. Please use YYYY-MM-DD and HH:MM format."

    end_dt = start_dt + datetime.timedelta(minutes=max(1, duration_minutes))

    # Determine local timezone offset
    local_tz = datetime.datetime.now(datetime.timezone.utc).astimezone().tzinfo
    start_str = start_dt.replace(tzinfo=local_tz).isoformat()
    end_str = end_dt.replace(tzinfo=local_tz).isoformat()

    try:
        service = _get_calendar_service()
    except RuntimeError as exc:
        return str(exc)

    event_body: dict = {
        "summary": title,
        "description": description,
        "start": {"dateTime": start_str},
        "end": {"dateTime": end_str},
    }

    try:
        created = service.events().insert(calendarId="primary", body=event_body).execute()
        event_id = created.get("id", "unknown")
        log.info("create_event: created '%s' id=%s", title, event_id)
        return (
            f"Event '{title}' created on {date} at {time} "
            f"for {duration_minutes} minutes."
        )
    except Exception as exc:  # noqa: BLE001
        log.error("create_event failed: %s", exc)
        return f"I couldn't create the event: {exc}"


# ---------------------------------------------------------------------------
# delete_event
# ---------------------------------------------------------------------------


def delete_event(event_id: str, confirmed: bool = False) -> str:
    """Delete a Google Calendar event by its ID.

    Parameters
    ----------
    event_id:
        The Google Calendar event ID.
    confirmed:
        When ``False`` (default) a confirmation prompt is returned.  Set to
        ``True`` to actually delete.

    Returns
    -------
    str
        Spoken confirmation or error message.
    """
    event_id = event_id.strip()
    if not event_id:
        return "Please provide the event ID to delete."

    if not confirmed:
        return (
            f"Ready to delete calendar event with ID {event_id}. "
            "Please confirm to proceed."
        )

    try:
        service = _get_calendar_service()
    except RuntimeError as exc:
        return str(exc)

    try:
        service.events().delete(calendarId="primary", eventId=event_id).execute()
        log.info("delete_event: deleted event id=%s", event_id)
        return f"Calendar event {event_id} has been deleted."
    except Exception as exc:  # noqa: BLE001
        log.error("delete_event failed: %s", exc)
        return f"I couldn't delete the event: {exc}"
