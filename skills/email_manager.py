"""
email_manager.py — Gmail send/read skills for MARS.

All functions return a ``str`` response that MARS speaks aloud.

Required environment variables
-------------------------------
GMAIL_ADDRESS      : Your Gmail address (e.g. you@gmail.com).
GMAIL_APP_PASSWORD : A Gmail App Password (not your regular password).
                     Create one at https://myaccount.google.com/apppasswords.

Functions
---------
send_email   : Send an email via Gmail SMTP over TLS.
read_emails  : Read the most recent emails via IMAP.
"""

from __future__ import annotations

import email
import imaplib
import os
import smtplib
import textwrap
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from utils.logger import get_logger

log = get_logger(__name__)

_GMAIL_SMTP_HOST = "smtp.gmail.com"
_GMAIL_SMTP_PORT = 587
_GMAIL_IMAP_HOST = "imap.gmail.com"


def _get_credentials() -> tuple[str, str]:
    """Return *(address, app_password)* from environment variables."""
    address = os.environ.get("GMAIL_ADDRESS", "")
    password = os.environ.get("GMAIL_APP_PASSWORD", "")
    return address, password


# ---------------------------------------------------------------------------
# send_email
# ---------------------------------------------------------------------------


def send_email(to: str, subject: str, body: str) -> str:
    """Send a plain-text email via Gmail SMTP.

    Parameters
    ----------
    to:
        Recipient email address.
    subject:
        Email subject line.
    body:
        Plain-text email body.

    Returns
    -------
    str
        Spoken confirmation or error message.
    """
    if not to.strip():
        return "Please specify a recipient email address."
    if not subject.strip():
        return "Please provide a subject for the email."
    if not body.strip():
        return "The email body cannot be empty."

    address, password = _get_credentials()
    if not address or not password:
        return (
            "Email is unavailable. Please set the GMAIL_ADDRESS and "
            "GMAIL_APP_PASSWORD environment variables."
        )

    msg = MIMEMultipart("alternative")
    msg["From"] = address
    msg["To"] = to
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP(_GMAIL_SMTP_HOST, _GMAIL_SMTP_PORT, timeout=15) as server:
            server.ehlo()
            server.starttls()
            server.login(address, password)
            server.sendmail(address, to, msg.as_string())
        log.info("send_email: sent to %r with subject %r", to, subject)
        return f"Email sent to {to} with subject '{subject}'."
    except smtplib.SMTPAuthenticationError:
        log.error("send_email: authentication failed")
        return (
            "Email authentication failed. Please check your GMAIL_ADDRESS "
            "and GMAIL_APP_PASSWORD."
        )
    except smtplib.SMTPException as exc:
        log.error("send_email failed: %s", exc)
        return f"I was unable to send the email: {exc}"
    except OSError as exc:
        log.error("send_email network error: %s", exc)
        return f"I couldn't reach the mail server: {exc}"


# ---------------------------------------------------------------------------
# read_emails
# ---------------------------------------------------------------------------


def read_emails(count: int = 5) -> str:
    """Read the most recent emails from the Gmail inbox.

    Parameters
    ----------
    count:
        Number of recent emails to fetch (1–20).

    Returns
    -------
    str
        Spoken summary of recent emails, or an error message.
    """
    count = max(1, min(20, count))
    address, password = _get_credentials()
    if not address or not password:
        return (
            "Email reading is unavailable. Please set the GMAIL_ADDRESS and "
            "GMAIL_APP_PASSWORD environment variables."
        )

    try:
        mail = imaplib.IMAP4_SSL(_GMAIL_IMAP_HOST, timeout=15)
        mail.login(address, password)
        mail.select("inbox")

        # Search for all messages, newest first
        status, message_ids = mail.search(None, "ALL")
        if status != "OK" or not message_ids or not message_ids[0]:
            mail.logout()
            return "Your inbox appears to be empty."

        ids: list[bytes] = message_ids[0].split()
        # Take the last `count` IDs (most recent)
        recent_ids = ids[-count:][::-1]

        summaries: list[str] = []
        for raw_id in recent_ids:
            status, msg_data = mail.fetch(raw_id, "(RFC822)")
            if status != "OK" or not msg_data:
                continue
            raw_email: bytes = msg_data[0][1]  # type: ignore[index]
            parsed = email.message_from_bytes(raw_email)

            sender: str = parsed.get("From", "Unknown sender")
            subject: str = parsed.get("Subject", "(no subject)")
            date: str = parsed.get("Date", "")

            # Extract a brief plain-text snippet
            snippet = _extract_body_snippet(parsed, max_chars=80)
            entry = f"From {sender}, subject: {subject}"
            if date:
                entry += f", dated {date}"
            if snippet:
                entry += f". Preview: {snippet}"
            summaries.append(entry)

        mail.logout()

        if not summaries:
            return "I couldn't read any emails from your inbox."

        intro = f"You have {len(summaries)} recent email{'s' if len(summaries) != 1 else ''}. "
        result = intro + " | ".join(
            f"Email {i + 1}: {s}" for i, s in enumerate(summaries)
        )
        log.info("read_emails: fetched %d emails", len(summaries))
        return result

    except imaplib.IMAP4.error as exc:
        log.error("read_emails IMAP error: %s", exc)
        return f"I was unable to read your emails: {exc}"
    except OSError as exc:
        log.error("read_emails network error: %s", exc)
        return f"I couldn't connect to the mail server: {exc}"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _extract_body_snippet(parsed_msg: email.message.Message, max_chars: int = 80) -> str:
    """Extract a short plain-text snippet from an email message."""
    text = ""
    if parsed_msg.is_multipart():
        for part in parsed_msg.walk():
            if part.get_content_type() == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    text = payload.decode("utf-8", errors="replace")
                    break
    else:
        payload = parsed_msg.get_payload(decode=True)
        if payload:
            text = payload.decode("utf-8", errors="replace")

    # Collapse whitespace and truncate
    import re
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > max_chars:
        text = text[:max_chars].rsplit(" ", 1)[0] + "…"
    return text
