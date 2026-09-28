"""Milestone 3: sync Sent Items into the Prospect table.

Pulls Sent Items, runs them through detection + account matching, and creates
a Prospect row for anyone not already known (by email). Existing prospects
are left untouched - this never touches cadence state, so it's safe to call
repeatedly (from a poll loop or by hand).

Uses a persisted watermark (SyncState.last_synced_at) rather than a fixed
"most recent N" window: the first-ever run seeds from your recent history,
and every run after that asks Graph for everything since the watermark, so a
burst of sent mail between polls can never scroll a real prospect out of
view before it's ever checked.
"""

from __future__ import annotations

import datetime

from app.config import INITIAL_BACKFILL_COUNT
from app.db import get_session
from app.detection import classify_message
from app.graph import GraphClient
from app.matching import domain_root, find_matching_account
from app.models import Account, IgnoredDomain, Prospect, SyncState


def _parse_sent_at(value: str | None) -> datetime.datetime:
    if not value:
        return datetime.datetime.now(datetime.UTC)
    return datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))


def _get_or_create_state(session) -> SyncState:
    state = session.get(SyncState, 1)
    if state is None:
        state = SyncState(id=1, last_synced_at=None)
        session.add(state)
        session.flush()
    return state


def sync_sent_items() -> dict:
    """One sync pass. Returns a summary dict for logging/API responses."""
    client = GraphClient()
    session = get_session()
    try:
        state = _get_or_create_state(session)

        if state.last_synced_at is None:
            # First run ever: seed from recent history instead of crawling
            # the entire mailbox from the beginning of time. Every later run
            # is gap-free because it asks for "since the watermark", not a
            # fixed count.
            messages = list(reversed(client.list_sent_items(top=INITIAL_BACKFILL_COUNT)))
        else:
            messages = client.list_sent_items_since(state.last_synced_at)

        accounts = session.query(Account).all()
        # Lowercased so a differently-cased address for an already-known
        # contact (result.email is already lowercased in detection.py) is
        # never mistaken for someone new - see detection.py's comment.
        existing_emails = {email.lower() for (email,) in session.query(Prospect.email).all()}
        ignored_roots = {domain for (domain,) in session.query(IgnoredDomain.domain).all()}
        new_prospects = []
        new_targets = []

        for message in messages:
            result = classify_message(message)
            if result.is_prospect and result.email not in existing_emails:
                account = find_matching_account(result.domain, accounts)
                if account is not None:
                    status = "detected"
                elif domain_root(result.domain) in ignored_roots:
                    status = None  # always-ignored domain - drop silently, as before
                else:
                    status = "unmatched_domain"  # Target Detection: surface it instead of dropping

                if status is not None:
                    session.add(
                        Prospect(
                            email=result.email,
                            name=result.name,
                            domain=result.domain,
                            status=status,
                            first_detected_at=_parse_sent_at(message.get("sentDateTime")),
                            created_at=datetime.datetime.now(datetime.UTC),
                            source_email_link=message.get("webLink"),
                            conversation_id=message.get("conversationId"),
                        )
                    )
                    existing_emails.add(result.email)
                    if status == "detected":
                        new_prospects.append(result.email)
                    else:
                        new_targets.append(result.email)

            sent_at = message.get("sentDateTime")
            if sent_at:
                state.last_synced_at = sent_at

        session.commit()
    finally:
        session.close()

    return {"scanned": len(messages), "new_prospects": new_prospects, "new_targets": new_targets}
