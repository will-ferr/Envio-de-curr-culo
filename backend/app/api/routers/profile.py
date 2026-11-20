"""Perfil, importação de currículo em PDF e perfis-alvo."""

import uuid

from fastapi import APIRouter, UploadFile
from pydantic import BaseModel, Field

from app.api.deps import DB, CurrentOwner
from app.config import get_settings
from app.errors import BusinessRule, Conflict, NotFound
from app.models import TargetRole
from app.schemas.profile import ProfileData
from app.services import profile as profile_svc
from app.services import queue, render, settings

router = APIRouter(tags=["perfil"])

MAX_PDF = 10 * 1024 * 1024


@router.get("/profile")
def get_profile(db: DB, _: CurrentOwner) -> ProfileData:
    return profile_svc.get_profile(db)


@router.put("/profile")
def put_profile(body: ProfileData, db: DB, _: CurrentOwner) -> ProfileData:
    profile_svc.save_profile(db, body)
    db.commit()
    return body


@router.post("/profile/import", status_code=202)
async def import_pdf(file: UploadFile, db: DB, _: CurrentOwner) -> dict:
    """Recebe o PDF e agenda a extração. O resultado volta para revisão, não é salvo direto."""
    if not settings.is_set(db, "ai.api_key"):
        raise BusinessRule("Configure a chave de IA para importar o currículo.", code="AI_NOT_CONFIGURED")
    data = await file.read(MAX_PDF + 1)
    if len(data) > MAX_PDF:
        raise BusinessRule("O PDF deve ter no máximo 10 MB.", code="FILE_TOO_LARGE")
    if not data.startswith(b"%PDF"):
        raise BusinessRule("Envie um arquivo PDF.", code="NOT_PDF")
    folder = get_settings().uploads_dir
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{uuid.uuid4().hex}.pdf"
    path.write_bytes(data)
    task = queue.enqueue(db, "import_profile_pdf", {"path": str(path)}, max_attempts=2)
    db.commit()
    return {"task_id": task.id}


# ---------- perfis-alvo ----------
class RoleIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    headline: str = Field(min_length=2, max_length=160)
    summary: str = Field("", max_length=2000)
    skills_focus: list[str] = Field(default_factory=list, max_length=60)
    keywords: list[str] = Field(default_factory=list, max_length=60)
    template: str = "classico"
    is_default: bool = False


def _role_out(r: TargetRole) -> dict:
    return {
        "id": r.id,
        "name": r.name,
        "headline": r.headline,
        "summary": r.summary,
        "skills_focus": r.skills_focus,
        "keywords": r.keywords,
        "template": r.template,
        "is_default": r.is_default,
    }


def _clean(items: list[str]) -> list[str]:
    seen, out = set(), []
    for i in items:
        k = i.strip()
        if k and k.casefold() not in seen:
            seen.add(k.casefold())
            out.append(k)
    return out


def _apply(role: TargetRole, body: RoleIn) -> None:
    if body.template not in render.RESUME_TEMPLATES:
        raise BusinessRule("Template desconhecido.", code="TEMPLATE_UNKNOWN")
    role.name, role.headline, role.summary = body.name.strip(), body.headline.strip(), body.summary.strip()
    role.skills_focus, role.keywords, role.template = _clean(body.skills_focus), _clean(body.keywords), body.template


@router.get("/target-roles")
def list_roles(db: DB, _: CurrentOwner) -> list[dict]:
    return [_role_out(r) for r in profile_svc.list_roles(db)]


@router.post("/target-roles", status_code=201)
def create_role(body: RoleIn, db: DB, _: CurrentOwner) -> dict:
    if any(r.name.casefold() == body.name.strip().casefold() for r in profile_svc.list_roles(db)):
        raise Conflict("Já existe um perfil-alvo com esse nome.", code="ROLE_DUPLICATE")
    role = TargetRole(name="", headline="")
    _apply(role, body)
    db.add(role)
    db.flush()
    if body.is_default or len(profile_svc.list_roles(db)) == 1:
        profile_svc.set_default_role(db, role)
    db.commit()
    return _role_out(role)


def _get_role(db: DB, role_id: int) -> TargetRole:
    role = db.get(TargetRole, role_id)
    if role is None:
        raise NotFound("Perfil-alvo não encontrado.")
    return role


@router.put("/target-roles/{role_id}")
def update_role(role_id: int, body: RoleIn, db: DB, _: CurrentOwner) -> dict:
    role = _get_role(db, role_id)
    if any(r.id != role.id and r.name.casefold() == body.name.strip().casefold() for r in profile_svc.list_roles(db)):
        raise Conflict("Já existe um perfil-alvo com esse nome.", code="ROLE_DUPLICATE")
    _apply(role, body)
    if body.is_default:
        profile_svc.set_default_role(db, role)
    db.commit()
    return _role_out(role)


@router.delete("/target-roles/{role_id}", status_code=204)
def delete_role(role_id: int, db: DB, _: CurrentOwner) -> None:
    role = _get_role(db, role_id)
    was_default = role.is_default
    db.delete(role)
    db.flush()
    remaining = profile_svc.list_roles(db)
    if was_default and remaining:
        profile_svc.set_default_role(db, remaining[0])
    db.commit()


@router.get("/templates")
def templates(_: CurrentOwner) -> list[dict]:
    return [{"id": k, "name": v} for k, v in render.RESUME_TEMPLATES.items()]
