"""Geração, validação, edição e renderização de currículos e cartas."""

import json
from pathlib import Path

from sqlalchemy.orm import Session

from app.ai import prompts
from app.ai.base import AIProvider
from app.config import get_settings
from app.domain import compose, validation
from app.domain.text import slug
from app.errors import BusinessRule, NotFound
from app.models import Document, Job, TargetRole
from app.schemas.ai import TailoredCoverLetter, TailoredDocuments, TailoredResume
from app.schemas.profile import ProfileData
from app.services import profile as profile_svc
from app.services import render, settings
from app.services.ai_runtime import record_usage


def _role(db: Session, job: Job, role_id: int | None) -> TargetRole | None:
    rid = role_id or (job.analysis.target_role_id if job.analysis else None)
    if rid:
        role = db.get(TargetRole, rid)
        if role is None:
            raise NotFound("Perfil-alvo não encontrado.")
        return role
    return next(iter(profile_svc.list_roles(db)), None)


def generate(
    db: Session, job: Job, ai: AIProvider | None, *, role_id: int | None = None, template: str | None = None
) -> tuple[Document, Document]:
    profile = profile_svc.get_profile(db)
    if profile.is_empty():
        raise BusinessRule("Preencha ou importe seu perfil antes de gerar currículos.", code="PROFILE_EMPTY")

    role = _role(db, job, role_id)
    template = template or (role.template if role else None) or settings.get(db, "prefs.default_template")

    if ai is not None:
        prompt = (
            "<perfil>\n"
            + profile.model_dump_json(exclude={"contact"})
            + "\n</perfil>\n"
            + (
                "<perfil_alvo>\n"
                + json.dumps(
                    {"titulo": role.headline, "resumo": role.summary, "foco": role.skills_focus}, ensure_ascii=False
                )
                + "\n</perfil_alvo>\n"
                if role
                else ""
            )
            + f"<nome_do_candidato>{profile.contact.name}</nome_do_candidato>\n"
            + f"<vaga>\n{job.title}\n{job.company or ''}\n{job.description}\n</vaga>"
        )
        tailored, usage = ai.structured(system=prompts.TAILOR, prompt=prompt, schema=TailoredDocuments, effort="high")
        record_usage(db, "tailor_documents", usage)
        resume, letter, used_ai = tailored.resume, tailored.cover_letter, True
    else:
        resume = compose.baseline_resume(
            profile, role.headline if role else "", role.summary if role else "", role.skills_focus if role else []
        )
        letter = compose.baseline_cover_letter(profile, job.title, job.company)
        used_ai = False

    # Uma versão nova substitui a anterior da mesma vaga.
    for old in list(job.documents):
        db.delete(old)
    db.flush()

    allowed = validation.allowed_job_terms(job.company)
    resume_doc = Document(
        job_id=job.id,
        target_role_id=role.id if role else None,
        kind="resume",
        template=template,
        content=resume.model_dump(),
        used_ai=used_ai,
        issues=[i.as_dict() for i in validation.validate_resume(profile, resume, allowed)],
    )
    letter_doc = Document(
        job_id=job.id,
        target_role_id=role.id if role else None,
        kind="cover_letter",
        template="carta",
        content=letter.model_dump(),
        used_ai=used_ai,
        issues=[
            i.as_dict()
            for i in validation.validate_cover_letter(profile, letter, allowed, validation.job_title_terms(job.title))
        ],
    )
    db.add_all([resume_doc, letter_doc])
    db.flush()
    return resume_doc, letter_doc


def update_content(db: Session, doc: Document, content: dict, template: str | None = None) -> Document:
    """Edição manual: revalida e invalida o PDF antigo."""
    profile = profile_svc.get_profile(db)
    allowed = validation.allowed_job_terms(doc.job.company)
    if doc.kind == "resume":
        parsed = TailoredResume.model_validate(content)
        doc.issues = [i.as_dict() for i in validation.validate_resume(profile, parsed, allowed)]
        if template:
            if template not in render.RESUME_TEMPLATES:
                raise BusinessRule("Template desconhecido.", code="TEMPLATE_UNKNOWN")
            doc.template = template
    else:
        parsed = TailoredCoverLetter.model_validate(content)
        doc.issues = [
            i.as_dict()
            for i in validation.validate_cover_letter(
                profile, parsed, allowed, validation.job_title_terms(doc.job.title)
            )
        ]
    doc.content = parsed.model_dump()
    doc.pdf_path = None
    db.flush()
    return doc


def html_for(doc: Document, profile: ProfileData) -> str:
    if doc.kind == "resume":
        ctx = compose.render_resume_context(profile, TailoredResume.model_validate(doc.content))
        return render.render_resume_html(doc.template, ctx)
    return render.render_letter_html(
        compose.render_letter_context(profile, TailoredCoverLetter.model_validate(doc.content))
    )


def pdf_filename(doc: Document, profile: ProfileData) -> str:
    kind = "Curriculo" if doc.kind == "resume" else "Carta"
    return f"{slug(profile.contact.name or 'Candidato')}_{kind}_{slug(doc.job.company or doc.job.title)[:40]}.pdf"


def render_pdf(db: Session, doc: Document) -> Path:
    profile = profile_svc.get_profile(db)
    dest = get_settings().documents_dir / f"{doc.id}.pdf"
    render.html_to_pdf(html_for(doc, profile), dest)
    doc.pdf_path = str(dest)
    db.flush()
    return dest


def ensure_pdf(db: Session, doc: Document) -> Path:
    if doc.pdf_path and Path(doc.pdf_path).exists():
        return Path(doc.pdf_path)
    return render_pdf(db, doc)
