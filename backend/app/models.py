"""Modelos de persistência.

O perfil é guardado como documento JSON validado por Pydantic (app/schemas/profile.py):
ele é editado e lido sempre por inteiro, e normalizá-lo em 7 tabelas não traria
consulta útil. Vagas, documentos e candidaturas são tabelas normais porque são
filtradas, ordenadas e relacionadas.
"""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, JsonType, TimestampMixin, utcnow

JOB_STATUSES = ("new", "analyzed", "discarded")
APPLICATION_STATUSES = ("draft", "approved", "sent", "interview", "offer", "rejected", "withdrawn")
TASK_STATUSES = ("pending", "running", "done", "failed")


class Owner(TimestampMixin, Base):
    """Dono da instância. Self-hosted: existe exatamente um."""

    __tablename__ = "owner"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(254))
    password_hash: Mapped[str] = mapped_column(String(255))


class AppSetting(Base):
    """Configurações editáveis pela interface. Segredos ficam criptografados (Fernet)."""

    __tablename__ = "app_settings"
    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[dict | list | str | int | float | bool | None] = mapped_column(JsonType, nullable=True)
    is_secret: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Profile(TimestampMixin, Base):
    __tablename__ = "profile"
    id: Mapped[int] = mapped_column(primary_key=True)
    data: Mapped[dict] = mapped_column(JsonType)


class TargetRole(TimestampMixin, Base):
    """Perfil-alvo: um "tipo de vaga" que a pessoa busca (ex.: Back-end .NET)."""

    __tablename__ = "target_roles"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    headline: Mapped[str] = mapped_column(String(160))
    summary: Mapped[str] = mapped_column(Text, default="")
    skills_focus: Mapped[list] = mapped_column(JsonType, default=list)
    keywords: Mapped[list] = mapped_column(JsonType, default=list)
    template: Mapped[str] = mapped_column(String(40), default="classico")
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)


class JobSource(TimestampMixin, Base):
    __tablename__ = "job_sources"
    __table_args__ = (CheckConstraint("kind IN ('rss')", name="ck_job_sources_kind"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(10), default="rss")
    name: Mapped[str] = mapped_column(String(80))
    url: Mapped[str] = mapped_column(String(2000))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)


class Job(TimestampMixin, Base):
    __tablename__ = "jobs"
    __table_args__ = (
        CheckConstraint(f"status IN {JOB_STATUSES}", name="ck_jobs_status"),
        Index("ix_jobs_status_created", "status", "created_at"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    origin: Mapped[str] = mapped_column(String(10))  # manual | url | rss | email
    source_id: Mapped[int | None] = mapped_column(ForeignKey("job_sources.id", ondelete="SET NULL"))
    url: Mapped[str | None] = mapped_column(String(2000))
    title: Mapped[str] = mapped_column(String(300))
    company: Mapped[str | None] = mapped_column(String(200))
    location: Mapped[str | None] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    contact_email: Mapped[str | None] = mapped_column(String(254))
    # Impede a mesma vaga de entrar duas vezes (URL normalizada ou hash do conteúdo).
    fingerprint: Mapped[str] = mapped_column(String(64), unique=True)
    status: Mapped[str] = mapped_column(String(12), default="new")

    analysis: Mapped["JobAnalysis | None"] = relationship(back_populates="job", cascade="all, delete-orphan")
    documents: Mapped[list["Document"]] = relationship(back_populates="job", cascade="all, delete-orphan")
    application: Mapped["Application | None"] = relationship(back_populates="job", cascade="all, delete-orphan")


class JobAnalysis(TimestampMixin, Base):
    __tablename__ = "job_analyses"
    __table_args__ = (CheckConstraint("score BETWEEN 0 AND 100", name="ck_job_analyses_score"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), unique=True)
    score: Mapped[int] = mapped_column(Integer)
    keyword_score: Mapped[int] = mapped_column(Integer)
    target_role_id: Mapped[int | None] = mapped_column(ForeignKey("target_roles.id", ondelete="SET NULL"))
    matched: Mapped[list] = mapped_column(JsonType, default=list)
    missing: Mapped[list] = mapped_column(JsonType, default=list)
    summary: Mapped[str] = mapped_column(Text, default="")
    seniority: Mapped[str | None] = mapped_column(String(40))
    used_ai: Mapped[bool] = mapped_column(Boolean, default=False)

    job: Mapped[Job] = relationship(back_populates="analysis")


class Document(TimestampMixin, Base):
    """Currículo ou carta gerados para uma vaga. `content` é editável; `issues` vem da validação."""

    __tablename__ = "documents"
    __table_args__ = (CheckConstraint("kind IN ('resume','cover_letter')", name="ck_documents_kind"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    target_role_id: Mapped[int | None] = mapped_column(ForeignKey("target_roles.id", ondelete="SET NULL"))
    kind: Mapped[str] = mapped_column(String(15))
    template: Mapped[str] = mapped_column(String(40), default="classico")
    content: Mapped[dict] = mapped_column(JsonType)
    issues: Mapped[list] = mapped_column(JsonType, default=list)
    used_ai: Mapped[bool] = mapped_column(Boolean, default=False)
    pdf_path: Mapped[str | None] = mapped_column(String(500))

    job: Mapped[Job] = relationship(back_populates="documents")


class Application(TimestampMixin, Base):
    __tablename__ = "applications"
    __table_args__ = (CheckConstraint(f"status IN {APPLICATION_STATUSES}", name="ck_applications_status"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), unique=True)
    status: Mapped[str] = mapped_column(String(12), default="draft")
    resume_document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id", ondelete="SET NULL"))
    cover_document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id", ondelete="SET NULL"))
    sent_via: Mapped[str | None] = mapped_column(String(10))  # email | manual
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    notes: Mapped[str] = mapped_column(Text, default="")

    job: Mapped[Job] = relationship(back_populates="application")
    events: Mapped[list["ApplicationEvent"]] = relationship(
        back_populates="application", cascade="all, delete-orphan", order_by="ApplicationEvent.id"
    )


class ApplicationEvent(Base):
    """Histórico imutável de mudanças de status (auditoria do funil)."""

    __tablename__ = "application_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), index=True)
    from_status: Mapped[str | None] = mapped_column(String(12))
    to_status: Mapped[str] = mapped_column(String(12))
    actor: Mapped[str] = mapped_column(String(10))  # owner | telegram | system
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    application: Mapped[Application] = relationship(back_populates="events")


class Task(TimestampMixin, Base):
    """Fila de trabalho no próprio PostgreSQL (SELECT ... FOR UPDATE SKIP LOCKED)."""

    __tablename__ = "tasks"
    __table_args__ = (
        CheckConstraint(f"status IN {TASK_STATUSES}", name="ck_tasks_status"),
        Index("ix_tasks_claim", "status", "run_after"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(40))
    payload: Mapped[dict] = mapped_column(JsonType, default=dict)
    status: Mapped[str] = mapped_column(String(10), default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    run_after: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_error: Mapped[str | None] = mapped_column(Text)
    result: Mapped[dict | None] = mapped_column(JsonType)


class AiUsage(Base):
    """Uso de tokens por operação — a pessoa paga a própria chave e precisa ver o gasto."""

    __tablename__ = "ai_usage"
    id: Mapped[int] = mapped_column(primary_key=True)
    operation: Mapped[str] = mapped_column(String(40))
    model: Mapped[str] = mapped_column(String(60))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class ProcessedEmail(Base):
    """Mensagens IMAP já lidas, para não importar o mesmo alerta duas vezes."""

    __tablename__ = "processed_emails"
    __table_args__ = (UniqueConstraint("message_id", name="uq_processed_emails_message_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    message_id: Mapped[str] = mapped_column(String(500))
    jobs_created: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
