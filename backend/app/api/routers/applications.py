"""Candidaturas (funil): aprovar, enviar, mudar status."""

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import DB, CurrentOwner
from app.api.routers.jobs import app_out, job_summary
from app.errors import NotFound
from app.models import Application, Job
from app.services import applications as apps_svc
from app.services import queue

router = APIRouter(prefix="/applications", tags=["candidaturas"])


def _out(a: Application) -> dict:
    return {**app_out(a), "job": job_summary(a.job)}  # type: ignore[dict-item]


@router.get("")
def list_applications(db: DB, _: CurrentOwner) -> list[dict]:
    return [_out(a) for a in db.scalars(select(Application).order_by(Application.updated_at.desc()))]


class ApproveIn(BaseModel):
    job_id: int


@router.post("", status_code=201)
def approve(body: ApproveIn, db: DB, _: CurrentOwner) -> dict:
    job = db.get(Job, body.job_id)
    if job is None:
        raise NotFound("Vaga não encontrada.")
    apps_svc.ensure_unique(job)
    app = apps_svc.approve(db, job)
    db.commit()
    return _out(app)


class StatusIn(BaseModel):
    status: Literal["sent", "interview", "offer", "rejected", "withdrawn"]
    note: str = Field("", max_length=1000)


@router.post("/{app_id}/status")
def change_status(app_id: int, body: StatusIn, db: DB, _: CurrentOwner) -> dict:
    app = apps_svc.get_or_404(db, app_id)
    if body.status == "sent":
        apps_svc.mark_sent_manually(db, app)
    else:
        apps_svc.transition(db, app, body.status, "owner", body.note)
    db.commit()
    return _out(app)


class NotesIn(BaseModel):
    notes: str = Field("", max_length=5000)


@router.patch("/{app_id}")
def update_notes(app_id: int, body: NotesIn, db: DB, _: CurrentOwner) -> dict:
    app = apps_svc.get_or_404(db, app_id)
    app.notes = body.notes
    db.commit()
    return _out(app)


@router.post("/{app_id}/send", status_code=202)
def send(app_id: int, db: DB, _: CurrentOwner) -> dict:
    """Valida tudo agora (para o erro aparecer na hora) e envia em segundo plano."""
    app = apps_svc.get_or_404(db, app_id)
    apps_svc.check_can_email(db, app)
    task = queue.enqueue(db, "send_application", {"application_id": app.id, "actor": "owner"}, max_attempts=1)
    db.commit()
    return {"task_id": task.id}
