"""Today dashboard: tasks currently due (due today or overdue), and completing them."""

from __future__ import annotations

import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.db import get_session
from app.models import Cadence, Prospect, Task

router = APIRouter()


class DueTaskOut(BaseModel):
    id: int
    label: str
    due_date: str
    is_overdue: bool
    prospect_id: int
    prospect_email: str
    prospect_name: str | None
    prospect_domain: str


class CompleteTaskOut(BaseModel):
    id: int
    status: str
    cadence_status: str


@router.get("/today", response_model=list[DueTaskOut])
def list_due_tasks():
    """Pending tasks due today or earlier, oldest due date first."""
    today = datetime.date.today()
    session = get_session()
    try:
        rows = (
            session.query(Task, Prospect)
            .join(Cadence, Task.cadence_id == Cadence.id)
            .join(Prospect, Cadence.prospect_id == Prospect.id)
            .filter(Task.status == "pending", Task.due_date <= today, Cadence.status == "active")
            .order_by(Task.due_date.asc())
            .all()
        )
        return [
            DueTaskOut(
                id=task.id,
                label=task.label,
                due_date=task.due_date.isoformat(),
                is_overdue=task.due_date < today,
                prospect_id=prospect.id,
                prospect_email=prospect.email,
                prospect_name=prospect.name,
                prospect_domain=prospect.domain,
            )
            for task, prospect in rows
        ]
    finally:
        session.close()


@router.post("/tasks/{task_id}/complete", response_model=CompleteTaskOut)
def complete_task(task_id: int):
    """Mark a task done. If it was the cadence's last pending task, the
    cadence itself is marked completed too."""
    session = get_session()
    try:
        task = session.get(Task, task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found")
        if task.status == "done":
            raise HTTPException(status_code=409, detail="Task already completed")

        task.status = "done"
        task.completed_at = datetime.datetime.now(datetime.UTC)

        cadence = session.get(Cadence, task.cadence_id)
        remaining = (
            session.query(Task)
            .filter(Task.cadence_id == cadence.id, Task.status == "pending")
            .count()
        )
        if remaining == 0:
            cadence.status = "completed"
            cadence.prospect.status = "completed"

        session.commit()
        return CompleteTaskOut(id=task.id, status=task.status, cadence_status=cadence.status)
    finally:
        session.close()
