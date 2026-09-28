"""Contacts: every prospect that has ever had a cadence started, grouped by
matched account, split into replied / not replied within each group.

Prospects still awaiting a decision ('detected', 'unmatched_domain') or
dismissed are excluded - this page is about contacts you've actually
engaged with, not the raw detection queue (see routers/prospects.py and
routers/targets.py for those)."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.db import get_session
from app.matching import find_matching_account
from app.models import Account, Prospect

router = APIRouter()

_EXCLUDED_STATUSES = ("detected", "dismissed", "unmatched_domain")


class ContactOut(BaseModel):
    prospect_id: int
    name: str | None
    email: str
    domain: str
    status: str
    replied: bool


class AccountGroupOut(BaseModel):
    account_id: int | None  # None for the "Unmatched" bucket
    account_name: str  # "Unmatched" when account_id is None
    replied: list[ContactOut]
    not_replied: list[ContactOut]


@router.get("/contacts", response_model=list[AccountGroupOut])
def list_contacts():
    session = get_session()
    try:
        prospects = (
            session.query(Prospect)
            .filter(~Prospect.status.in_(_EXCLUDED_STATUSES))
            .order_by(Prospect.first_detected_at.desc())
            .all()
        )
        accounts = session.query(Account).order_by(Account.name).all()

        groups: dict[int | None, AccountGroupOut] = {}
        for prospect in prospects:
            account = find_matching_account(prospect.domain, accounts)
            key = account.id if account else None
            if key not in groups:
                groups[key] = AccountGroupOut(
                    account_id=key,
                    account_name=account.name if account else "Unmatched",
                    replied=[],
                    not_replied=[],
                )

            # Derived from the prospect's own Cadence rows, not the mirrored
            # Prospect.status - status mirroring is a display convenience
            # set at the moment a transition happens (see routers/cadences.py,
            # replies.py), not guaranteed to stay in sync forever if a row
            # predates a mirroring fix or some future code path misses it.
            # Checking the real Cadence status directly can't drift.
            replied = any(c.status == "paused" for c in prospect.cadences)
            contact = ContactOut(
                prospect_id=prospect.id,
                name=prospect.name,
                email=prospect.email,
                domain=prospect.domain,
                status=prospect.status,
                replied=replied,
            )
            (groups[key].replied if contact.replied else groups[key].not_replied).append(contact)

        return sorted(groups.values(), key=lambda g: (g.account_id is None, g.account_name.lower()))
    finally:
        session.close()
