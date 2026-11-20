"""Execução de cada tipo de tarefa da fila."""

import logging
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai import prompts
from app.ai.base import AINotConfigured, PDFInput
from app.db import utcnow
from app.errors import BusinessRule, Conflict, ExternalError, NotFound
from app.models import Application, Document, Job, JobSource, ProcessedEmail
from app.schemas.ai import ExtractedJobList, ExtractedProfile
from app.services import applications as apps_svc
from app.services import documents as docs_svc
from app.services import jobs as jobs_svc
from app.services import mail, notify, queue, settings
from app.services import profile as profile_svc
from app.services.ai_runtime import get_provider, record_usage
from app.services.rss import read_feed

log = logging.getLogger(__name__)


def _job(db: Session, job_id: int) -> Job:
    job = db.get(Job, job_id)
    if job is None:
        raise NotFound(f"Vaga {job_id} não existe mais.")
    return job


def import_profile_pdf(db: Session, payload: dict) -> dict:
    """Extrai o perfil de um PDF. O resultado NÃO é salvo: a pessoa revisa antes."""
    path = Path(payload["path"])
    ai = get_provider(db)
    try:
        if ai is None:
            raise AINotConfigured("Configure a chave de IA para importar o currículo.")
        extracted, usage = ai.structured(
            system=prompts.IMPORT_PROFILE,
            prompt="Extraia os dados deste currículo.",
            schema=ExtractedProfile,
            pdf=PDFInput(path.read_bytes()),
            effort="low",
        )
        record_usage(db, "import_profile", usage)
        return {"profile": profile_svc.from_extracted(extracted).model_dump(mode="json")}
    finally:
        path.unlink(missing_ok=True)  # o PDF enviado não fica guardado


def analyze_job(db: Session, payload: dict) -> dict:
    job = _job(db, payload["job_id"])
    analysis = jobs_svc.analyze(db, job, get_provider(db))
    db.commit()
    if payload.get("notify"):
        notify.job_matched(db, job)
    return {"score": analysis.score, "used_ai": analysis.used_ai}


def generate_documents(db: Session, payload: dict) -> dict:
    job = _job(db, payload["job_id"])
    resume, letter = docs_svc.generate(
        db, job, get_provider(db), role_id=payload.get("role_id"), template=payload.get("template")
    )
    db.commit()
    docs_svc.render_pdf(db, resume)
    docs_svc.render_pdf(db, letter)
    db.commit()
    db.refresh(job)
    if payload.get("notify"):
        notify.documents_ready(db, job)
    return {"resume_id": resume.id, "cover_letter_id": letter.id}


def render_document(db: Session, payload: dict) -> dict:
    doc = db.get(Document, payload["document_id"])
    if doc is None:
        raise NotFound("Documento não existe mais.")
    docs_svc.render_pdf(db, doc)
    db.commit()
    return {"document_id": doc.id}


def send_application(db: Session, payload: dict) -> dict:
    app = db.get(Application, payload["application_id"])
    if app is None:
        raise NotFound("Candidatura não existe mais.")
    actor = payload.get("actor", "owner")
    try:
        apps_svc.send_email(db, app, actor=actor)
        db.commit()
    except Exception as exc:
        db.rollback()
        notify.text(db, f"❌ Falha ao enviar a candidatura “{app.job.title}”: {getattr(exc, 'message', exc)}")
        raise
    notify.text(db, f"📤 Candidatura enviada para {app.job.contact_email} — {app.job.title}")
    return {"sent_to": app.job.contact_email}


def _new_job(db: Session, **kwargs) -> Job | None:
    try:
        with db.begin_nested():
            job = jobs_svc.create_job(db, **kwargs)
        queue.enqueue(db, "analyze_job", {"job_id": job.id, "notify": True})
        return job
    except (Conflict, BusinessRule, ExternalError):
        return None  # repetida, sem descrição suficiente ou página inacessível


def poll_sources(db: Session, payload: dict) -> dict:
    created, errors = 0, []

    for source in db.scalars(select(JobSource).where(JobSource.enabled.is_(True))):
        try:
            for entry in read_feed(source.url):
                # Resumo curto no feed: busca a página da vaga para ter a descrição completa.
                description = entry.description if len(entry.description) >= 200 else ""
                if _new_job(
                    db,
                    origin="rss",
                    source_id=source.id,
                    url=entry.url,
                    title=entry.title,
                    company=entry.company or None,
                    description=description,
                ):
                    created += 1
            source.last_error = None
        except Exception as exc:  # uma fonte com problema não interrompe as outras
            source.last_error = str(getattr(exc, "message", exc))[:500]
            errors.append(source.name)
        source.last_checked_at = utcnow()
        db.commit()

    if settings.get(db, "imap.enabled") and settings.imap_configured(db):
        created += _poll_imap(db)

    return {"created": created, "failed_sources": errors}


def _poll_imap(db: Session) -> int:
    ai = get_provider(db)
    if ai is None:
        log.info("IMAP habilitado mas sem IA configurada; alertas por e-mail ignorados")
        return 0
    cfg = mail.IMAPConfig(
        host=settings.get(db, "imap.host"),
        port=int(settings.get(db, "imap.port")),
        username=settings.get(db, "imap.username"),
        password=settings.get(db, "imap.password") or "",
        folder=settings.get(db, "imap.folder"),
        sender_filter=settings.get(db, "imap.sender_filter") or "",
    )
    created = 0
    for msg in mail.fetch_recent(cfg):
        if db.scalar(select(ProcessedEmail).where(ProcessedEmail.message_id == msg.message_id[:500])):
            continue
        result, usage = ai.structured(
            system=prompts.EXTRACT_JOBS_FROM_EMAIL,
            prompt=f"Assunto: {msg.subject}\nDe: {msg.sender}\n\n{msg.text}",
            schema=ExtractedJobList,
            effort="low",
        )
        record_usage(db, "extract_email_jobs", usage)
        count = 0
        for j in result.jobs:
            if j.url.startswith("http") and _new_job(
                db, origin="email", url=j.url, title=j.title, company=j.company or None, location=j.location or None
            ):
                count += 1
        db.add(ProcessedEmail(message_id=msg.message_id[:500], jobs_created=count))
        db.commit()
        created += count
    return created


HANDLERS = {
    "import_profile_pdf": import_profile_pdf,
    "analyze_job": analyze_job,
    "generate_documents": generate_documents,
    "render_document": render_document,
    "send_application": send_application,
    "poll_sources": poll_sources,
}
