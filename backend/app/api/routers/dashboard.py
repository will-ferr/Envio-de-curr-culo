"""Painel, consumo de IA e controle dos dados (exportar / apagar)."""

from datetime import timedelta

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import delete, func, select

from app.api.deps import DB, CurrentOwner
from app.config import get_settings
from app.db import utcnow
from app.errors import BusinessRule
from app.models import (
    AiUsage,
    Application,
    ApplicationEvent,
    AppSetting,
    Document,
    Job,
    JobAnalysis,
    JobSource,
    ProcessedEmail,
    Profile,
    TargetRole,
    Task,
)
from app.services import applications as apps_svc
from app.services import profile as profile_svc

router = APIRouter(tags=["painel"])


@router.get("/dashboard")
def dashboard(db: DB, _: CurrentOwner) -> dict:
    by_status = dict(db.execute(select(Application.status, func.count()).group_by(Application.status)).all())
    week_ago = utcnow() - timedelta(days=7)
    jobs_week = db.scalar(select(func.count(Job.id)).where(Job.created_at >= week_ago)) or 0
    avg_score = db.scalar(select(func.avg(JobAnalysis.score)))
    to_review = db.scalars(
        select(Job)
        .join(JobAnalysis)
        .where(Job.status == "analyzed", ~Job.application.has())
        .order_by(JobAnalysis.score.desc())
        .limit(5)
    ).all()
    sent_total = sum(by_status.get(s, 0) for s in ("sent", "interview", "offer", "rejected"))
    responses = sum(by_status.get(s, 0) for s in ("interview", "offer", "rejected"))
    return {
        "funnel": {s: by_status.get(s, 0) for s in apps_svc.TRANSITIONS},
        "jobs_last_7_days": jobs_week,
        "average_score": round(avg_score) if avg_score is not None else None,
        "response_rate": round(100 * responses / sent_total) if sent_total else None,
        "sent_today": apps_svc.sent_today(db),
        "followups": [
            {
                "application_id": a.id,
                "job_id": a.job_id,
                "title": a.job.title,
                "company": a.job.company,
                "sent_at": a.sent_at,
            }
            for a in apps_svc.stale_followups(db)[:5]
        ],
        "to_review": [
            {"id": j.id, "title": j.title, "company": j.company, "score": j.analysis.score}
            for j in to_review
            if j.analysis
        ],
        "failed_tasks": db.scalar(
            select(func.count(Task.id)).where(Task.status == "failed", Task.updated_at >= week_ago)
        )
        or 0,
    }


@router.get("/ai-usage")
def ai_usage(db: DB, _: CurrentOwner) -> dict:
    since = utcnow() - timedelta(days=30)
    rows = db.execute(
        select(
            AiUsage.operation,
            AiUsage.model,
            func.count(),
            func.sum(AiUsage.input_tokens),
            func.sum(AiUsage.output_tokens),
        )
        .where(AiUsage.created_at >= since)
        .group_by(AiUsage.operation, AiUsage.model)
    ).all()
    return {
        "period_days": 30,
        "items": [
            {
                "operation": op,
                "model": model,
                "calls": calls,
                "input_tokens": int(inp or 0),
                "output_tokens": int(out or 0),
            }
            for op, model, calls, inp, out in rows
        ],
    }


@router.get("/data/export")
def export_data(db: DB, owner: CurrentOwner) -> JSONResponse:
    """Todos os dados da instância em JSON (portabilidade). Segredos não são exportados."""
    jobs = db.scalars(select(Job)).all()
    data = {
        "owner": {"name": owner.name, "email": owner.email},
        "profile": profile_svc.get_profile(db).model_dump(mode="json"),
        "target_roles": [
            {
                "name": r.name,
                "headline": r.headline,
                "summary": r.summary,
                "skills_focus": r.skills_focus,
                "keywords": r.keywords,
            }
            for r in profile_svc.list_roles(db)
        ],
        "jobs": [
            {
                "title": j.title,
                "company": j.company,
                "url": j.url,
                "status": j.status,
                "created_at": j.created_at.isoformat(),
                "application": None
                if not j.application
                else {
                    "status": j.application.status,
                    "sent_at": j.application.sent_at.isoformat() if j.application.sent_at else None,
                    "notes": j.application.notes,
                },
            }
            for j in jobs
        ],
    }
    return JSONResponse(data, headers={"Content-Disposition": 'attachment; filename="candidaturas-export.json"'})


class WipeIn(BaseModel):
    confirm: str


@router.post("/data/wipe")
def wipe(body: WipeIn, db: DB, _: CurrentOwner) -> dict:
    """Apaga perfil, vagas, documentos e configurações. A conta de acesso é mantida."""
    if body.confirm != "APAGAR":
        raise BusinessRule("Digite APAGAR para confirmar.", code="CONFIRMATION_REQUIRED")
    for model in (
        ApplicationEvent,
        Application,
        Document,
        JobAnalysis,
        Job,
        JobSource,
        TargetRole,
        Profile,
        Task,
        AiUsage,
        ProcessedEmail,
        AppSetting,
    ):
        db.execute(delete(model))
    db.commit()
    for folder in (get_settings().documents_dir, get_settings().uploads_dir):
        if folder.exists():
            for f in folder.iterdir():
                f.unlink(missing_ok=True)
    return {"ok": True}
