"""Funil de candidaturas: aprovação, envio e transições de status com histórico."""

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import utcnow
from app.domain import compose, validation
from app.errors import BusinessRule, Conflict, NotFound
from app.models import Application, ApplicationEvent, Document, Job
from app.schemas.ai import TailoredCoverLetter
from app.services import documents as docs_svc
from app.services import mail, settings
from app.services import profile as profile_svc

TRANSITIONS: dict[str, set[str]] = {
    "draft": {"approved", "withdrawn"},
    "approved": {"sent", "withdrawn"},
    "sent": {"interview", "rejected", "withdrawn"},
    "interview": {"offer", "rejected", "withdrawn"},
    "offer": {"withdrawn"},
    "rejected": set(),
    "withdrawn": set(),
}

LABELS = {
    "draft": "Rascunho",
    "approved": "Aprovada",
    "sent": "Enviada",
    "interview": "Entrevista",
    "offer": "Proposta",
    "rejected": "Recusada",
    "withdrawn": "Desistência",
}

TZ = ZoneInfo("America/Sao_Paulo")


def _latest(job: Job, kind: str) -> Document | None:
    found = [d for d in job.documents if d.kind == kind]
    return max(found, key=lambda d: d.id) if found else None


def transition(db: Session, app: Application, to: str, actor: str, note: str = "") -> Application:
    if to not in TRANSITIONS.get(app.status, set()):
        raise BusinessRule(
            f"Não é possível mudar de “{LABELS[app.status]}” para “{LABELS.get(to, to)}”.", code="INVALID_TRANSITION"
        )
    db.add(ApplicationEvent(application_id=app.id, from_status=app.status, to_status=to, actor=actor, note=note))
    app.status = to
    db.flush()
    return app


def approve(db: Session, job: Job, actor: str = "owner") -> Application:
    """Aprova a candidatura. Só é possível com um currículo gerado e sem erros de validação."""
    resume = _latest(job, "resume")
    if resume is None:
        raise BusinessRule("Gere o currículo antes de aprovar.", code="RESUME_MISSING")
    if validation.has_errors(resume.issues):
        raise BusinessRule(
            "O currículo tem informações que não estão no seu perfil. Corrija antes de aprovar.", code="RESUME_INVALID"
        )
    letter = _latest(job, "cover_letter")

    app = job.application
    if app is None:
        app = Application(job_id=job.id, status="draft")
        db.add(app)
        db.flush()
        db.add(ApplicationEvent(application_id=app.id, from_status=None, to_status="draft", actor=actor))
    app.resume_document_id = resume.id
    app.cover_document_id = letter.id if letter else None
    if app.status == "draft":
        transition(db, app, "approved", actor)
    return app


def sent_today(db: Session) -> int:
    start_local = datetime.combine(datetime.now(TZ).date(), time.min, tzinfo=TZ)
    return (
        db.scalar(
            select(func.count(Application.id)).where(
                Application.sent_via == "email", Application.sent_at >= start_local
            )
        )
        or 0
    )


def check_can_email(db: Session, app: Application) -> None:
    if app.status != "approved":
        raise BusinessRule("Só candidaturas aprovadas podem ser enviadas.", code="NOT_APPROVED")
    if not app.job.contact_email:
        raise BusinessRule(
            "A vaga não tem e-mail de contato. Candidate-se pelo link e marque como enviada.", code="NO_CONTACT_EMAIL"
        )
    if not settings.smtp_configured(db):
        raise BusinessRule("Configure o envio de e-mail (SMTP) nas configurações.", code="SMTP_NOT_CONFIGURED")
    limit = int(settings.get(db, "prefs.daily_send_limit"))
    if sent_today(db) >= limit:
        raise BusinessRule(
            f"Limite diário de {limit} envios atingido. Ajuste em Configurações se quiser.", code="DAILY_LIMIT"
        )


def smtp_config(db: Session) -> mail.SMTPConfig:
    return mail.SMTPConfig(
        host=settings.get(db, "smtp.host"),
        port=int(settings.get(db, "smtp.port")),
        username=settings.get(db, "smtp.username"),
        password=settings.get(db, "smtp.password") or "",
        security=settings.get(db, "smtp.security"),
        from_email=settings.get(db, "smtp.from_email"),
        from_name=settings.get(db, "smtp.from_name", ""),
    )


def send_email(db: Session, app: Application, actor: str = "owner") -> Application:
    check_can_email(db, app)
    profile = profile_svc.get_profile(db)
    resume = db.get(Document, app.resume_document_id) if app.resume_document_id else None
    if resume is None:
        raise NotFound("Currículo da candidatura não encontrado.")
    letter_doc = db.get(Document, app.cover_document_id) if app.cover_document_id else None

    attachments = [mail.Attachment(docs_svc.pdf_filename(resume, profile), docs_svc.ensure_pdf(db, resume))]
    if letter_doc:
        letter = TailoredCoverLetter.model_validate(letter_doc.content)
        subject, body = letter.subject, compose.letter_as_text(letter)
    else:
        subject = f"Candidatura — {app.job.title} — {profile.contact.name}"
        body = f"Olá,\n\nSegue meu currículo para a vaga de {app.job.title}.\n\nAtenciosamente,\n{profile.contact.name}"

    cfg = smtp_config(db)
    mail.send(cfg, mail.build_message(cfg, app.job.contact_email or "", subject, body, attachments))
    app.sent_via = "email"
    app.sent_at = utcnow()
    return transition(db, app, "sent", actor, note=f"E-mail enviado para {app.job.contact_email}")


def mark_sent_manually(db: Session, app: Application, actor: str = "owner") -> Application:
    app.sent_via = "manual"
    app.sent_at = utcnow()
    return transition(db, app, "sent", actor, note="Candidatura feita pelo site da vaga")


def get_or_404(db: Session, app_id: int) -> Application:
    app = db.get(Application, app_id)
    if app is None:
        raise NotFound("Candidatura não encontrada.")
    return app


def ensure_unique(job: Job) -> None:
    if job.application and job.application.status not in ("draft",):
        raise Conflict(
            "Já existe uma candidatura para essa vaga.",
            code="APPLICATION_EXISTS",
            details={"application_id": job.application.id},
        )


def stale_followups(db: Session, days: int = 10) -> list[Application]:
    """Candidaturas enviadas há muito tempo sem resposta — candidatas a follow-up."""
    cutoff = utcnow() - timedelta(days=days)
    return list(db.scalars(select(Application).where(Application.status == "sent", Application.sent_at < cutoff)))
