"""Target Detection: sales-looking emails to a domain not on your account
list. Instead of silently dropping these (the old behavior), they land here
so you can decide what to do with them.

"Ignore" (a single instance) reuses the existing POST /prospects/{id}/dismiss
- see routers/prospects.py, whose guard now also accepts "unmatched_domain".
"""

from __future__ import annotations

import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.cadence_service import create_cadence
from app.db import get_session
from app.matching import domain_root
from app.models import Account, IgnoredDomain, Prospect

router = APIRouter()


class TargetOut(BaseModel):
    id: int
    email: str
    name: str | None
    domain: str
    first_detected_at: str
    source_email_link: str | None


def _siblings(session, prospect: Prospect) -> list[Prospect]:
    """Other still-unresolved prospects on the same domain root."""
    root = domain_root(prospect.domain)
    candidates = session.query(Prospect).filter(Prospect.status == "unmatched_domain", Prospect.id != prospect.id).all()
    return [p for p in candidates if domain_root(p.domain) == root]


def _account_key(name: str) -> str:
    return " ".join(name.lower().split())


def _get_unmatched(session, prospect_id: int) -> Prospect:
    prospect = session.get(Prospect, prospect_id)
    if prospect is None:
        raise HTTPException(status_code=404, detail="Target not found")
    if prospect.status != "unmatched_domain":
        raise HTTPException(status_code=409, detail=f"Already resolved (status={prospect.status})")
    return prospect


@router.get("/targets", response_model=list[TargetOut])
def list_targets():
    """New targets (unmatched domain, not yet triaged), newest first."""
    session = get_session()
    try:
        targets = (
            session.query(Prospect)
            .filter(Prospect.status == "unmatched_domain")
            .order_by(Prospect.first_detected_at.desc())
            .all()
        )
        return [
            TargetOut(
                id=p.id,
                email=p.email,
                name=p.name,
                domain=p.domain,
                first_detected_at=p.first_detected_at.isoformat(),
                source_email_link=p.source_email_link,
            )
            for p in targets
        ]
    finally:
        session.close()


@router.post("/targets/{prospect_id}/add-account-and-start-cadence")
def add_account_and_start_cadence(prospect_id: int):
    """Add this domain as a recognized account and start a cadence.

    Every other unmatched target on this same domain is flipped to
    "detected" too, since the domain is now a known account - they flow into
    the normal Prospects queue instead of staying stuck as unmatched.
    """
    session = get_session()
    try:
        prospect = _get_unmatched(session, prospect_id)
        root = domain_root(prospect.domain)

        account_name = root.title()
        existing_names = {_account_key(a.name) for a in session.query(Account).all()}
        if _account_key(account_name) not in existing_names:
            session.add(Account(name=account_name, created_at=datetime.datetime.now(datetime.UTC)))
        for sibling in _siblings(session, prospect):
            sibling.status = "detected"

        cadence = create_cadence(session, prospect)
        session.commit()
        return {"prospect_id": prospect.id, "status": prospect.status, "cadence_id": cadence.id, "account": account_name}
    finally:
        session.close()


@router.post("/targets/{prospect_id}/start-cadence-only")
def start_cadence_only(prospect_id: int):
    """Start a cadence for this one contact without adding the domain as an
    account - the domain stays unresolved and will surface again for anyone
    else at that domain."""
    session = get_session()
    try:
        prospect = _get_unmatched(session, prospect_id)
        cadence = create_cadence(session, prospect)
        session.commit()
        return {"prospect_id": prospect.id, "status": prospect.status, "cadence_id": cadence.id}
    finally:
        session.close()


@router.post("/targets/{prospect_id}/always-ignore-domain")
def always_ignore_domain(prospect_id: int):
    """Never surface this domain again, for anyone. Resolves every other
    unmatched target on this domain too, so nothing is left stuck."""
    session = get_session()
    try:
        prospect = _get_unmatched(session, prospect_id)
        root = domain_root(prospect.domain)

        if session.query(IgnoredDomain).filter(IgnoredDomain.domain == root).first() is None:
            session.add(IgnoredDomain(domain=root, created_at=datetime.datetime.now(datetime.UTC)))

        prospect.status = "dismissed"
        for sibling in _siblings(session, prospect):
            sibling.status = "dismissed"

        session.commit()
        return {"prospect_id": prospect.id, "status": prospect.status, "ignored_domain": root}
    finally:
        session.close()
