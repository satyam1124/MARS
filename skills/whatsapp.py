"""
whatsapp.py — WhatsApp messaging skill for MARS via pywhatkit.

All functions return a ``str`` response that MARS speaks aloud.

Required packages
-----------------
pywhatkit : ``pip install pywhatkit``

Functions
---------
send_whatsapp_message : Send a WhatsApp message to a phone number.
"""

from __future__ import annotations

import datetime

from utils.logger import get_logger

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# send_whatsapp_message
# ---------------------------------------------------------------------------


def send_whatsapp_message(
    phone: str,
    message: str,
    confirmed: bool = False,
) -> str:
    """Send a WhatsApp message to *phone* via pywhatkit.

    Opens WhatsApp Web in the default browser and sends the message
    automatically.  The browser must be able to reach WhatsApp Web and you
    must be logged in to WhatsApp Web.

    Parameters
    ----------
    phone:
        Recipient phone number in international format (e.g. ``"+15551234567"``).
        The leading ``+`` is required.
    message:
        Text body of the message.
    confirmed:
        When ``False`` (default) a confirmation prompt is returned.  Set to
        ``True`` to actually send.

    Returns
    -------
    str
        Spoken confirmation or error message.
    """
    phone = phone.strip()
    message = message.strip()

    if not phone:
        return "Please specify a phone number for the WhatsApp message."
    if not phone.startswith("+"):
        return (
            "The phone number must be in international format, "
            "for example plus one five five five one two three four five six seven."
        )
    if not message:
        return "Please provide a message to send."

    if not confirmed:
        return (
            f"Ready to send WhatsApp message to {phone}: '{message}'. "
            "Please confirm to proceed."
        )

    try:
        import pywhatkit  # type: ignore[import]
    except ImportError:
        return (
            "pywhatkit is not installed. "
            "Please run: pip install pywhatkit"
        )

    # Schedule the message 2 minutes from now to give the browser time to open
    now = datetime.datetime.now()
    send_time = now + datetime.timedelta(minutes=2)
    hour = send_time.hour
    minute = send_time.minute

    try:
        pywhatkit.sendwhatmsg(
            phone_no=phone,
            message=message,
            time_hour=hour,
            time_min=minute,
            wait_time=15,
            tab_close=True,
            close_time=3,
        )
        log.info("send_whatsapp_message: queued to %r at %02d:%02d", phone, hour, minute)
        return (
            f"WhatsApp message to {phone} has been scheduled. "
            "WhatsApp Web will open in your browser shortly."
        )
    except Exception as exc:  # noqa: BLE001
        log.error("send_whatsapp_message failed: %s", exc)
        return f"I couldn't send the WhatsApp message: {exc}"
