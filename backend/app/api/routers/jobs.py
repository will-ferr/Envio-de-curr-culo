"""Vagas: adicionar (link ou texto), listar, analisar e gerar documentos."""

from typing import Literal

from fastapi import APIRouter, Query
from pydantic import BaseModel, EmailStr, Field, model_validator
from sqlalchemy import or_, select

from app.api.deps import DB, CurrentOwner
from app.errors import NotFound
from app.models import Job
from app.services import applications as apps_svc
from app.services import jobs as jobs_svc
from app.services import queue

router = APIRouter(prefix="/jobs", tags=["vagas"])


def doc_out(d) -> dict:
    return {
        "id": d.id,
        "kind": d.kind,
        "template": d.template,
        "content": d.content,
        "issues": d.issues,
        "used_ai": d.used_ai,
        "has_pdf": bool(d.pdf_path),
        "target_role_id": d.target_role_id,
        "updated_at": d.updated_at,
    }


def app_out(a) -> dict | None:
    if a is None:
        return None
    return {
        "id": a.id,
        "status": a.status,
        "status_label": apps_svc.LABELS[a.status],
        "sent_via": a.sent_via,
        "sent_at": a.sent_at,
        "notes": a.notes,
        "resume_document_id": a.resume_document_id,
        "cover_document_id": a.cover_document_id,
        "events": [
            {"from": e.from_status, "to": e.to_status, "actor": e.actor, "note": e.note, "at": e.created_at}
            for e in a.events
        ],
    }


def job_summary(j: Job) -> dict:
    a = j.analysis
    return {
        "id": j.id,
        "title": j.title,
        "company": j.company,
        "location": j.location,
        "url": j.url,
        "origin": j.origin,
        "status": j.status,
        "created_at": j.created_at,
        "score": a.score if a else None,
        "used_ai": a.used_ai if a else None,
        "application_status": j.application.status if j.application else None,
    }


def job_detail(j: Job) -> dict:
    a = j.analysis
    return {
        **job_summary(j),
        "description": j.description,
        "contact_email": j.contact_email,
        "analysis": None
        if a is None
        else {
            "score": a.score,
            "keyword_score": a.keyword_score,
            "matched": a.matched,
            "missing": a.missing,
            "summary": a.summary,
            "seniority": a.seniority,
            "target_role_id": a.target_role_id,
            "used_ai": a.used_ai,
            "updated_at": a.updated_at,
        },
        "documents": [doc_out(d) for d in sorted(j.documents, key=lambda d: d.id)],
        "application": app_out(j.application),
    }


class JobIn(BaseModel):
    url: str | None = Field(None, max_length=2000)
    title: str = Field("", max_length=300)
    company: str | None = Field(None, max_length=200)
    description: str = Field("", max_length=50000)

    @model_validator(mode="after")
    def _url_or_text(self):
        if not (self.url or self.description.strip()):
            raise ValueError("Informe o link da vaga ou cole a descrição.")
        return self


@router.get("")
def list_jobs(
    db: DB,
    _: CurrentOwner,
    status: Literal["new", "analyzed", "discarded", "active"] | None = "active",
    q: str | None = Query(None, max_length=100),
    min_score: int | None = Query(None, ge=0, le=100),
) -> list[dict]:
    stmt = select(Job).order_by(Job.created_at.desc()).limit(300)
    if status == "active":
        stmt = stmt.where(Job.status != "discarded")
    elif status:
        stmt = stmt.where(Job.status == status)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Job.title.ilike(like), Job.company.ilike(like)))
    jobs = db.scalars(stmt).all()
    out = [job_summary(j) for j in jobs]
    if min_score is not None:
        out = [j for j in out if (j["score"] or 0) >= min_score]
    return out


@router.post("", status_code=201)
def create_job(body: JobIn, db: DB, _: CurrentOwner) -> dict:
    job = jobs_svc.create_job(
        db,
        origin="url" if body.url and not body.description else "manual",
        url=body.url or None,
        title=body.title.strip(),
        company=(body.company or "").strip() or None,
        description=body.description,
    )
    task = queue.enqueue(db, "analyze_job", {"job_id": job.id, "notify": False})
    db.commit()
    return {"job": job_detail(job), "task_id": task.id}


def _get(db: DB, job_id: int) -> Job:
    job = db.get(Job, job_id)
    if job is None:
        raise NotFound("Vaga não encontrada.")
    return job


@router.get("/{job_id}")
def get_job(job_id: int, db: DB, _: CurrentOwner) -> dict:
    return job_detail(_get(db, job_id))


class JobPatch(BaseModel):
    title: str | None = Field(None, min_length=2, max_length=300)
    company: str | None = Field(None, max_length=200)
    location: str | None = Field(None, max_length=200)
    contact_email: EmailStr | Literal[""] | None = None
    status: Literal["new", "analyzed", "discarded"] | None = None


@router.patch("/{job_id}")
def patch_job(job_id: int, body: JobPatch, db: DB, _: CurrentOwner) -> dict:
    job = _get(db, job_id)
    data = body.model_dump(exclude_unset=True)
    if "contact_email" in data:
        data["contact_email"] = str(data["contact_email"]) or None
    for k, v in data.items():
        setattr(job, k, v)
    db.commit()
    return job_detail(job)


@router.delete("/{job_id}", status_code=204)
def delete_job(job_id: int, db: DB, _: CurrentOwner) -> None:
    db.delete(_get(db, job_id))
    db.commit()


@router.post("/{job_id}/analyze", status_code=202)
def analyze(job_id: int, db: DB, _: CurrentOwner) -> dict:
    job = _get(db, job_id)
    task = queue.enqueue(db, "analyze_job", {"job_id": job.id, "notify": False})
    db.commit()
    return {"task_id": task.id}


class GenerateIn(BaseModel):
    target_role_id: int | None = None
    template: str | None = None


@router.post("/{job_id}/documents", status_code=202)
def generate(job_id: int, body: GenerateIn, db: DB, _: CurrentOwner) -> dict:
    job = _get(db, job_id)
    task = queue.enqueue(
        db,
        "generate_documents",
        {"job_id": job.id, "role_id": body.target_role_id, "template": body.template, "notify": False},
    )
    db.commit()
    return {"task_id": task.id}
