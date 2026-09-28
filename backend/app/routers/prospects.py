"""Prospects: newly detected external contacts with no cadence started yet."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.cadence_service import create_cadence
from app.db import get_session
from app.models import Prospect
from app.poller import sync_sent_items

router = APIRouter()


class ProspectOut(BaseModel):
    id: int
    email: str
    name: str | None
    domain: str
    status: str
    first_detected_at: str
    source_email_link: str | None


class TaskOut(BaseModel):
    label: str
    due_date: str
    status: str


class CadenceOut(BaseModel):
    cadence_id: int
    prospect_id: int
    tasks: list[TaskOut]


@router.get("/prospects", response_model=list[ProspectOut])
def list_prospects():
    """New prospects (detected, no cadence started), newest first."""
    session = get_session()
    try:
        prospects = (
            session.query(Prospect)
            .filter(Prospect.status == "detected")
            .order_by(Prospect.first_detected_at.desc())
            .all()
        )
        return [
            ProspectOut(
                id=p.id,
                email=p.email,
                name=p.name,
                domain=p.domain,
                status=p.status,
                first_detected_at=p.first_detected_at.isoformat(),
                source_email_link=p.source_email_link,
            )
            for p in prospects
        ]
    finally:
        session.close()


@router.post("/sync")
def trigger_sync():
    """Manually run a Sent Items sync instead of waiting for the poll loop."""
    return sync_sent_items()


@router.post("/prospects/{prospect_id}/dismiss")
def dismiss_prospect(prospect_id: int):
    """Mark a false-positive prospect as dismissed.

    This is a status change, not a row delete: the poller dedups by "has this
    email ever been seen before" regardless of status, so a dismissed
    prospect's row has to stick around or the same false positive would just
    come back the next time that person emails you.
    """
    session = get_session()
    try:
        prospect = session.get(Prospect, prospect_id)
        if prospect is None:
            raise HTTPException(status_code=404, detail="Prospect not found")
        if prospect.status not in ("detected", "unmatched_domain"):
            raise HTTPException(
                status_code=409,
                detail=f"Cannot dismiss a prospect with an existing cadence (status={prospect.status})",
            )
        prospect.status = "dismissed"
        session.commit()
        return {"id": prospect.id, "status": prospect.status}
    finally:
        session.close()


@router.post("/prospects/{prospect_id}/start-cadence", response_model=CadenceOut)
def start_cadence(prospect_id: int):
    """Create the default 6-step sequence for a prospect and flip it to active.

    Day 0 ("Initial email") is created already done - it's the email that got
    this prospect detected in the first place, not something still to do.
    """
    session = get_session()
    try:
        prospect = session.get(Prospect, prospect_id)
        if prospect is None:
            raise HTTPException(status_code=404, detail="Prospect not found")
        if prospect.status != "detected":
            raise HTTPException(
                status_code=409,
                detail=f"Cadence already started for this prospect (status={prospect.status})",
            )

        cadence = create_cadence(session, prospect)
        session.commit()

        return CadenceOut(
            cadence_id=cadence.id,
            prospect_id=prospect.id,
            tasks=[TaskOut(label=t.label, due_date=t.due_date.isoformat(), status=t.status) for t in cadence.tasks],
        )
    finally:
        session.close()
