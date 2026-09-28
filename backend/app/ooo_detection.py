"""Tell a genuine reply apart from an automatic out-of-office reply, and try
to pull a return date out of the OOO message text.

Necessarily best-effort - there's no universal machine-readable flag for
"this is an auto-reply," and free-text date phrasing varies endlessly. This
catches the common Outlook/Exchange patterns; it won't catch everything.
"""

from __future__ import annotations

import datetime
import re

from dateutil import parser as dateutil_parser

# Case-insensitive prefixes Outlook/Exchange (and most other mail systems)
# use for auto-reply subjects.
OOO_SUBJECT_PREFIXES = (
    "automatic reply:",
    "auto reply:",
    "auto-reply:",
    "autoreply:",
    "out of office:",
    "out of office auto-reply:",
    "automatic response:",
)

# Outlook desktop wraps HTML replies in a <head> full of Word/CSS boilerplate
# (font-face declarations, MsoNormal styles, etc.) that's mostly numbers -
# strip that out first so it can't be mistaken for a date, before stripping
# the remaining tags.
_HEAD_RE = re.compile(r"(?is)<head\b.*?</head>")
_TAG_RE = re.compile(r"<[^>]+>")

# A day-month-year date, optionally preceded by a weekday, in either order
# ("13th August" or "August 13th"), with or without an explicit year.
# Matching a narrow, specific pattern - rather than handing the whole message
# to a fuzzy parser - is what makes this reliable even when the message also
# contains a phone number, reference code, or email address.
_DATE_RE = re.compile(
    r"(?:(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*\.?,?\s+)?"
    r"(?:\d{1,2}(?:st|nd|rd|th)?\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?"
    r"|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2}(?:st|nd|rd|th)?)"
    r"(?:,?\s*(\d{4}))?",
    re.IGNORECASE,
)

# A parsed date this far past the message's own received date, with no year
# in the text, is more likely a same-day-next-year wrap (e.g. a December
# message says "back 5th January") than a real multi-month-old OOO - nudge
# it forward a year rather than trust the raw parse.
_YEARLESS_PAST_WRAP_DAYS = 30
# A parsed date further out than this from when the message arrived is
# treated as a mis-parse and discarded, regardless of direction.
_MAX_FUTURE_WINDOW_DAYS = 200


def looks_like_ooo(subject: str | None) -> bool:
    subject = (subject or "").strip().lower()
    return subject.startswith(OOO_SUBJECT_PREFIXES)


def _clean_body(content: str, content_type: str | None) -> str:
    if content_type == "html":
        content = _HEAD_RE.sub(" ", content)
        content = _TAG_RE.sub(" ", content)
    return re.sub(r"\s+", " ", content).strip()


def extract_return_date(body: dict | None, received_at: datetime.datetime) -> datetime.date | None:
    """Best-effort return date from an OOO message body, or None if it can't
    find one it's confident about.

    `body` is a Graph message `body` object: {"contentType": "html"|"text", "content": "..."}.
    `received_at` anchors year-less dates ("13th August" is assumed relative
    to when the message arrived, not today).
    """
    if not body:
        return None
    text = _clean_body(body.get("content") or "", body.get("contentType"))

    match = _DATE_RE.search(text)
    if not match:
        return None

    had_year = match.group(1) is not None
    try:
        parsed = dateutil_parser.parse(match.group(0), default=received_at)
    except (ValueError, OverflowError):
        return None

    if not had_year:
        delta_days = (parsed.date() - received_at.date()).days
        if delta_days < -_YEARLESS_PAST_WRAP_DAYS:
            try:
                parsed = parsed.replace(year=parsed.year + 1)
            except ValueError:
                return None

    if abs((parsed.date() - received_at.date()).days) > _MAX_FUTURE_WINDOW_DAYS:
        return None

    return parsed.date()
