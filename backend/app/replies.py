"""Reply detection: react once a prospect has replied in their outreach
thread - either pausing the cadence for a genuine reply, or marking it
out-of-office (with a best-effort return date) for an auto-reply, and
auto-resuming once that date passes.

Uses each prospect's stored conversationId (captured at detection time - see
poller.py) rather than "did this address email me at all", so an unrelated
email from the same person doesn't falsely affect their cadence - only a
reply within the actual outreach thread does.

Only covers prospects/cadences created after this feature was added -
conversation_id is NULL for anything detected earlier.
"""

from __future__ import annotations

import datetime

from app.db import get_session
from app.graph import GraphClient
from app.models import Cadence, Prospect, Task
from app.ooo_detection import extract_return_date, looks_like_ooo


def _received_at(message: dict) -> datetime.datetime:
    value = message.get("receivedDateTime") or ""
    return datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))


def check_for_replies() -> dict:
    """One pass over active/out-of-office/completed cadences. Returns a
    summary dict.

    Completed cadences are included so a reply that arrives after the final
    email still moves the contact to Replied instead of being silently
    missed forever - the sequence having finished doesn't mean the prospect
    stopped mattering.

    A cadence already "paused" (genuine reply) is left alone - that's a
    human-attention state, not something this keeps adjusting. A manually
    paused/stopped cadence is left alone too - that was a deliberate decision
    to stop pursuing this contact, not something a late reply should reopen
    on its own.
    """
    client = GraphClient()
    session = get_session()
    try:
        cadences = (
            session.query(Cadence)
            .join(Prospect, Cadence.prospect_id == Prospect.id)
            .filter(Cadence.status.in_(("active", "out_of_office", "completed")), Prospect.conversation_id.isnot(None))
            .all()
        )

        paused = []
        marked_ooo = []
        resumed = []
        today = datetime.date.today()

        for cadence in cadences:
            prospect = cadence.prospect
            try:
                messages = client.list_conversation_messages(prospect.conversation_id)
            except Exception as e:
                # One bad/stale conversationId shouldn't stop every other
                # cadence from being checked this cycle.
                print(f"WARNING: reply check failed for {prospect.email}: {e}")
                continue
            replies = [
                m
                for m in messages
                if (m.get("from") or {}).get("emailAddress", {}).get("address", "").lower() == prospect.email.lower()
            ]
            # Only react to messages newer than the last one already processed,
            # so an old auto-reply that's still the latest message doesn't get
            # re-flagged forever after the cadence has already resumed.
            if cadence.last_reply_at:
                replies = [m for m in replies if (m.get("receivedDateTime") or "") > cadence.last_reply_at]

            if replies:
                replies.sort(key=lambda m: m.get("receivedDateTime") or "")
                latest = replies[-1]
                cadence.last_reply_at = latest.get("receivedDateTime")

                if looks_like_ooo(latest.get("subject")):
                    cadence.status = "out_of_office"
                    cadence.ooo_return_date = extract_return_date(latest.get("body"), _received_at(latest))
                    prospect.status = "out_of_office"
                    marked_ooo.append(prospect.email)
                else:
                    cadence.status = "paused"
                    cadence.ooo_return_date = None
                    prospect.status = "paused"
                    paused.append(prospect.email)

            if (
                cadence.status == "out_of_office"
                and cadence.ooo_return_date is not None
                and cadence.ooo_return_date <= today
            ):
                cadence.status = "active"
                cadence.ooo_return_date = None
                prospect.status = "active"
                # Anything that fell due while they were away shouldn't greet
                # them back as a pile of "overdue" reminders - push it to
                # today instead, same as if it had just become due.
                for task in cadence.tasks:
                    if task.status == "pending" and task.due_date < today:
                        task.due_date = today
                resumed.append(prospect.email)

        session.commit()
    finally:
        session.close()

    return {"checked": len(cadences), "paused": paused, "marked_ooo": marked_ooo, "resumed": resumed}
