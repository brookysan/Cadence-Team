"""Shared cadence-creation logic, used by both the normal Prospects flow and
the Target Detection actions that also start a cadence - one place that
creates the 6-step sequence, not two copies that could drift apart."""

from __future__ import annotations

import datetime

from app.cadence_rules import DEFAULT_SEQUENCE
from app.models import Cadence, Prospect, Task


def create_cadence(session, prospect: Prospect) -> Cadence:
    """Create the default 6-step sequence for a prospect and flip it to active.

    Day 0 ("Initial email") is created already done - it's the email that got
    this prospect detected in the first place, not something still to do.

    Callers are responsible for their own status guard before calling this -
    the required prior status differs (e.g. "detected" vs "unmatched_domain").
    """
    today = datetime.date.today()
    cadence = Cadence(prospect_id=prospect.id, started_at=today, status="active")
    session.add(cadence)
    session.flush()  # assigns cadence.id for the tasks below

    for day_offset, label in DEFAULT_SEQUENCE:
        is_day_zero = day_offset == 0
        session.add(
            Task(
                cadence_id=cadence.id,
                day_offset=day_offset,
                label=label,
                due_date=today + datetime.timedelta(days=day_offset),
                status="done" if is_day_zero else "pending",
                completed_at=datetime.datetime.now(datetime.UTC) if is_day_zero else None,
            )
        )

    prospect.status = "active"
    return cadence


def restart_cadence(session, cadence: Cadence) -> Cadence:
    """Reset a completed or manually-paused cadence back to a fresh active
    run, reusing its existing Task rows (keyed by day_offset) rather than
    deleting and recreating them - same day-0-done/rest-pending convention as
    create_cadence(), with due dates recalculated from today.

    Callers are responsible for their own status guard before calling this -
    see routers/cadences.py's restart endpoint.
    """
    today = datetime.date.today()
    cadence.started_at = today
    cadence.status = "active"
    cadence.ooo_return_date = None
    # Cleared so a stale value can't suppress a genuinely new reply after
    # restart - check_for_replies() treats None as "process everything".
    cadence.last_reply_at = None

    for task in cadence.tasks:
        is_day_zero = task.day_offset == 0
        task.due_date = today + datetime.timedelta(days=task.day_offset)
        task.status = "done" if is_day_zero else "pending"
        task.completed_at = datetime.datetime.now(datetime.UTC) if is_day_zero else None

    cadence.prospect.status = "active"
    return cadence
