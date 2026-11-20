"""Saúde, primeiro acesso (assistente de configuração) e acompanhamento de tarefas."""

from fastapi import APIRouter
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select, text

from app import __version__
from app.api.deps import DB, CurrentOwner
from app.errors import Conflict, NotFound
from app.models import Owner, Task
from app.security import hash_password
from app.services import profile as profile_svc
from app.services import settings

router = APIRouter(tags=["sistema"])


@router.get("/health")
def health(db: DB) -> dict:
    db.execute(text("SELECT 1"))
    return {"status": "ok", "version": __version__}


@router.get("/setup/status")
def setup_status(db: DB) -> dict:
    """Público: o frontend usa para decidir entre assistente de configuração e login."""
    has_owner = (db.scalar(select(func.count(Owner.id))) or 0) > 0
    return {"needs_owner": not has_owner}


@router.get("/setup/checklist")
def setup_checklist(db: DB, _: CurrentOwner) -> dict:
    profile = profile_svc.get_profile(db)
    return {
        "ai": settings.is_set(db, "ai.api_key"),
        "profile": not profile.is_empty(),
        "target_roles": len(profile_svc.list_roles(db)) > 0,
        "telegram": settings.telegram_linked(db),
        "smtp": settings.smtp_configured(db),
    }


class OwnerIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=10, max_length=200)


@router.post("/setup/owner", status_code=201)
def create_owner(body: OwnerIn, db: DB) -> dict:
    """Cria a conta do dono. Só funciona uma vez — depois disso a instância está protegida."""
    if (db.scalar(select(func.count(Owner.id))) or 0) > 0:
        raise Conflict("A instância já foi configurada.", code="ALREADY_SETUP")
    db.add(Owner(name=body.name, email=str(body.email).strip().lower(), password_hash=hash_password(body.password)))
    db.commit()
    return {"ok": True}


@router.get("/tasks/{task_id}")
def get_task(task_id: int, db: DB, _: CurrentOwner) -> dict:
    task = db.get(Task, task_id)
    if task is None:
        raise NotFound("Tarefa não encontrada.")
    return {
        "id": task.id,
        "kind": task.kind,
        "status": task.status,
        "attempts": task.attempts,
        "error": task.last_error,
        "result": task.result,
    }
