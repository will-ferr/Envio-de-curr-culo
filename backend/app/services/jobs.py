"""Entrada e análise de vagas."""

import json
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai import prompts
from app.ai.base import AIProvider
from app.domain import matching
from app.domain.text import job_fingerprint
from app.errors import BusinessRule, Conflict
from app.models import Job, JobAnalysis
from app.schemas.ai import JobAnalysisResult
from app.services import profile as profile_svc
from app.services.ai_runtime import record_usage
from app.services.fetch import fetch_job

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


def create_job(
    db: Session,
    *,
    origin: str,
    url: str | None = None,
    title: str = "",
    company: str | None = None,
    location: str | None = None,
    description: str = "",
    source_id: int | None = None,
) -> Job:
    """Cria a vaga. Se só houver URL, busca a página. Vaga repetida gera Conflict com o id existente."""
    if url and not description:
        fetched = fetch_job(url)
        title = title or fetched.title
        company = company or fetched.company or None
        location = location or fetched.location or None
        description = fetched.description

    description = (description or "").strip()
    if len(description) < 30:
        raise BusinessRule("A descrição da vaga está vazia ou curta demais para análise.", code="JOB_TOO_SHORT")
    if not title:
        title = description.splitlines()[0][:120]

    fp = job_fingerprint(url, title, company, description)
    existing = db.scalar(select(Job).where(Job.fingerprint == fp))
    if existing:
        raise Conflict("Essa vaga já foi adicionada.", code="JOB_DUPLICATE", details={"job_id": existing.id})

    emails = _EMAIL.findall(description)
    job = Job(
        origin=origin,
        source_id=source_id,
        url=url,
        title=title[:300],
        company=(company or None),
        location=location,
        description=description[:50000],
        contact_email=emails[0] if emails else None,
        fingerprint=fp,
    )
    db.add(job)
    db.flush()
    return job


def _role_options(db: Session) -> list[matching.RoleOption]:
    return [
        matching.RoleOption(id=r.id, keywords=r.keywords, is_default=r.is_default) for r in profile_svc.list_roles(db)
    ]


def analyze(db: Session, job: Job, ai: AIProvider | None) -> JobAnalysis:
    profile = profile_svc.get_profile(db)
    text = f"{job.title}\n{job.company or ''}\n{job.description}"
    kw = matching.analyze(text, profile, _role_options(db))

    analysis = job.analysis or JobAnalysis(job_id=job.id)
    analysis.keyword_score = kw.score
    analysis.score = kw.score
    analysis.matched = kw.matched
    analysis.missing = kw.missing
    analysis.target_role_id = kw.target_role_id
    analysis.used_ai = False
    analysis.summary = (
        f"{len(kw.matched)} de {len(kw.matched) + len(kw.missing)} termos técnicos da vaga estão no seu perfil."
        if kw.matched or kw.missing
        else "Nenhum termo técnico conhecido encontrado. Configure a IA para uma análise completa."
    )
    analysis.seniority = None

    if ai is not None and not profile.is_empty():
        roles = [{"id": r.id, "name": r.name, "keywords": r.keywords} for r in profile_svc.list_roles(db)]
        prompt = (
            "<perfil>\n" + profile.model_dump_json(exclude={"contact"}) + "\n</perfil>\n"
            "<perfis_alvo>\n" + json.dumps(roles, ensure_ascii=False) + "\n</perfis_alvo>\n"
            "<vaga>\n" + text + "\n</vaga>"
        )
        result, usage = ai.structured(system=prompts.ANALYZE_JOB, prompt=prompt, schema=JobAnalysisResult)
        record_usage(db, "analyze_job", usage)
        valid_roles = {r["id"] for r in roles}
        analysis.score = max(0, min(100, result.score))
        analysis.matched = result.matched[:20]
        analysis.missing = result.missing[:20]
        analysis.summary = result.summary
        analysis.seniority = result.seniority or None
        if result.target_role_id in valid_roles:
            analysis.target_role_id = result.target_role_id
        analysis.used_ai = True
        # Completa dados que a página não trouxe, sem sobrescrever o que já existe.
        if not job.company and result.company:
            job.company = result.company[:200]
        if not job.location and result.location:
            job.location = result.location[:200]
        if not job.contact_email and _EMAIL.fullmatch(result.contact_email or ""):
            job.contact_email = result.contact_email

    if job.analysis is None:
        db.add(analysis)
    job.status = "analyzed" if job.status == "new" else job.status
    db.flush()
    return analysis
