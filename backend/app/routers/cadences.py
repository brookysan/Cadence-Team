"""Timeline: every active/completed cadence and where each prospect is in it."""

from __future__ import annotations

import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.cadence_service import restart_cadence
from app.db import get_session
from app.models import Cadence, Prospect, Task
from app.replies import check_for_replies

router = APIRouter()


class CadenceTaskOut(BaseModel):
    day_offset: int
    label: str
    due_date: str
    status: str
    is_overdue: bool


class CadenceTimelineOut(BaseModel):
    cadence_id: int
    prospect_id: int
    prospect_name: str | None
    prospect_email: str
    prospect_domain: str
    started_at: str
    status: str
    ooo_return_date: str | None
    last_reply_at: str | None
    tasks: list[CadenceTaskOut]


@router.get("/cadences", response_model=list[CadenceTimelineOut])
def list_cadences():
    """Every cadence (active or completed), most recently started first."""
    today = datetime.date.today()
    session = get_session()
    try:
        cadences = (
            session.query(Cadence)
            .join(Prospect, Cadence.prospect_id == Prospect.id)
            .order_by(Cadence.started_at.desc())
            .all()
        )
        result = []
        for cadence in cadences:
            prospect: Prospect = cadence.prospect
            tasks = sorted(cadence.tasks, key=lambda t: t.day_offset)
            result.append(
                CadenceTimelineOut(
                    cadence_id=cadence.id,
                    prospect_id=prospect.id,
                    prospect_name=prospect.name,
                    prospect_email=prospect.email,
                    prospect_domain=prospect.domain,
                    started_at=cadence.started_at.isoformat(),
                    status=cadence.status,
                    ooo_return_date=cadence.ooo_return_date.isoformat() if cadence.ooo_return_date else None,
                    last_reply_at=cadence.last_reply_at,
                    tasks=[
                        CadenceTaskOut(
                            day_offset=t.day_offset,
                            label=t.label,
                            due_date=t.due_date.isoformat(),
                            status=t.status,
                            is_overdue=(t.status == "pending" and t.due_date < today),
                        )
                        for t in tasks
                    ],
                )
            )
        return result
    finally:
        session.close()


@router.post("/cadences/check-replies")
def trigger_reply_check():
    """Manually run a reply check instead of waiting for the poll loop."""
    return check_for_replies()


@router.post("/cadences/{cadence_id}/resume")
def resume_cadence(cadence_id: int):
    """Manually resume an out-of-office cadence."""
    session = get_session()
    try:
        cadence = session.get(Cadence, cadence_id)
        if cadence is None:
            raise HTTPException(status_code=404, detail="Cadence not found")
        if cadence.status != "out_of_office":
            raise HTTPException(status_code=409, detail=f"Cannot resume cadence with status={cadence.status}")

        today = datetime.date.today()
        cadence.status = "active"
        cadence.ooo_return_date = None
        for task in cadence.tasks:
            if task.status == "pending" and task.due_date < today:
                task.due_date = today
        session.commit()
        return {"cadence_id": cadence.id, "status": cadence.status}
    finally:
        session.close()


@router.post("/cadences/{cadence_id}/pause")
def pause_cadence(cadence_id: int):
    """Manually pause/stop an active or out-of-office cadence - distinct
    from the automatic 'paused' status set when a prospect genuinely
    replies. Moves it to the Timeline's Paused section, where it can be
    restarted or permanently deleted."""
    session = get_session()
    try:
        cadence = session.get(Cadence, cadence_id)
        if cadence is None:
            raise HTTPException(status_code=404, detail="Cadence not found")
        if cadence.status not in ("active", "out_of_office"):
            raise HTTPException(status_code=409, detail=f"Cannot pause cadence with status={cadence.status}")

        cadence.status = "manual_pause"
        cadence.ooo_return_date = None
        cadence.prospect.status = "manual_pause"
        session.commit()
        return {"cadence_id": cadence.id, "status": cadence.status}
    finally:
        session.close()


@router.post("/cadences/{cadence_id}/mark-replied")
def mark_replied(cadence_id: int):
    """Manually mark a cadence as replied - for a genuine reply that landed
    outside the tracked conversation thread (e.g. a new email rather than a
    reply-in-thread) and so was never picked up by check_for_replies(), or
    any other case where a human knows better than the automated check.

    Sets last_reply_at to now (Graph-string-shaped, so it displays sensibly
    in the Replied section) rather than leaving it at whatever stale value
    (or None) it had before."""
    session = get_session()
    try:
        cadence = session.get(Cadence, cadence_id)
        if cadence is None:
            raise HTTPException(status_code=404, detail="Cadence not found")
        if cadence.status == "paused":
            raise HTTPException(status_code=409, detail="Already marked as replied")

        cadence.status = "paused"
        cadence.ooo_return_date = None
        cadence.last_reply_at = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        cadence.prospect.status = "paused"
        session.commit()
        return {"cadence_id": cadence.id, "status": cadence.status}
    finally:
        session.close()


@router.post("/cadences/{cadence_id}/restart")
def restart_cadence_endpoint(cadence_id: int):
    """Restart a completed or manually-paused cadence back to active - see
    app/cadence_service.py's restart_cadence()."""
    session = get_session()
    try:
        cadence = session.get(Cadence, cadence_id)
        if cadence is None:
            raise HTTPException(status_code=404, detail="Cadence not found")
        if cadence.status not in ("completed", "manual_pause"):
            raise HTTPException(status_code=409, detail=f"Cannot restart cadence with status={cadence.status}")

        restart_cadence(session, cadence)
        session.commit()
        return {"cadence_id": cadence.id, "status": cadence.status}
    finally:
        session.close()


@router.delete("/cadences/{cadence_id}")
def delete_cadence(cadence_id: int):
    """Permanently delete a manually-paused cadence, its tasks, and its
    prospect record - the prospect is deleted too (not just the cadence/
    tasks) so this email can surface again as a brand-new prospect if they
    email again later, matching app/poller.py's existing-email dedup.

    SQLite foreign-key enforcement is never enabled in this app and the
    Cadence->Task relationship has no ORM delete-cascade, so rows must be
    deleted explicitly in child-to-parent order: tasks, then cadence, then
    prospect - otherwise the task rows would be silently orphaned rather
    than removed or blocked.
    """
    session = get_session()
    try:
        cadence = session.get(Cadence, cadence_id)
        if cadence is None:
            raise HTTPException(status_code=404, detail="Cadence not found")
        if cadence.status != "manual_pause":
            raise HTTPException(status_code=409, detail=f"Cannot delete cadence with status={cadence.status}")

        prospect = cadence.prospect
        prospect_id = prospect.id
        session.query(Task).filter(Task.cadence_id == cadence.id).delete()
        session.delete(cadence)
        session.flush()
        session.delete(prospect)
        session.commit()
        return {"deleted_cadence_id": cadence_id, "deleted_prospect_id": prospect_id}
    finally:
        session.close()
