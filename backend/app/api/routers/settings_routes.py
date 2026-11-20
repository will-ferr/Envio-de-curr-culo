"""Configurações: IA, Telegram, SMTP, IMAP, preferências e fontes RSS."""

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, EmailStr, Field, HttpUrl

from app.ai.anthropic_provider import EFFORT_CHOICES, MODEL_CHOICES, AnthropicProvider
from app.api.deps import DB, CurrentOwner
from app.errors import BusinessRule, NotFound
from app.models import JobSource
from app.services import applications as apps_svc
from app.services import mail, notify, queue, settings
from app.services.fetch import assert_public_url
from app.services.render import RESUME_TEMPLATES

router = APIRouter(prefix="/settings", tags=["configurações"])


@router.get("")
def get_all(db: DB, _: CurrentOwner) -> dict:
    return {
        "ai": {
            **settings.group(db, "ai", ["api_key", "model", "effort"]),
            "models": MODEL_CHOICES,
            "efforts": list(EFFORT_CHOICES),
        },
        "telegram": {
            **settings.group(db, "telegram", ["bot_token"]),
            "linked": settings.telegram_linked(db),
            "pair_code": settings.get(db, "telegram.pair_code"),
        },
        "smtp": settings.group(
            db, "smtp", ["host", "port", "username", "password", "security", "from_email", "from_name"]
        ),
        "imap": settings.group(
            db, "imap", ["host", "port", "username", "password", "folder", "enabled", "sender_filter"]
        ),
        "prefs": {
            **settings.group(db, "prefs", ["daily_send_limit", "min_score_notify", "default_template"]),
            "templates": RESUME_TEMPLATES,
        },
    }


# ---------- IA ----------
class AIIn(BaseModel):
    api_key: str | None = Field(None, max_length=300)
    model: str = "claude-opus-5-5"
    effort: Literal["low", "medium", "high"] = "medium"


@router.put("/ai")
def put_ai(body: AIIn, db: DB, _: CurrentOwner) -> dict:
    if body.model not in MODEL_CHOICES:
        raise BusinessRule("Modelo não suportado.", code="MODEL_UNKNOWN")
    if body.api_key:
        # Valida antes de salvar: uma chave errada falharia mais tarde, no meio de uma tarefa.
        AnthropicProvider(api_key=body.api_key.strip(), model=body.model).check()
    settings.set_many(
        db,
        {"api_key": body.api_key.strip() if body.api_key else None, "model": body.model, "effort": body.effort},
        "ai",
    )
    db.commit()
    return {"ok": True}


@router.delete("/ai/key", status_code=204)
def delete_ai_key(db: DB, _: CurrentOwner) -> None:
    settings.set_value(db, "ai.api_key", None)
    db.commit()


@router.post("/ai/test")
def test_ai(db: DB, _: CurrentOwner) -> dict:
    key = settings.get(db, "ai.api_key")
    if not key:
        raise BusinessRule("Nenhuma chave cadastrada.", code="AI_NOT_CONFIGURED")
    AnthropicProvider(api_key=key, model=settings.get(db, "ai.model")).check()
    return {"ok": True}


# ---------- Telegram ----------
class TelegramIn(BaseModel):
    bot_token: str = Field(min_length=20, max_length=100)


@router.put("/telegram")
def put_telegram(body: TelegramIn, db: DB, _: CurrentOwner) -> dict:
    from app.services.telegram import TelegramClient

    tg = TelegramClient(body.bot_token.strip(), timeout=10)
    try:
        bot = tg.get_me()
    finally:
        tg.close()
    settings.set_value(db, "telegram.bot_token", body.bot_token.strip())
    settings.set_value(db, "telegram.chat_id", None)
    settings.set_value(db, "telegram.offset", None)
    code = notify.new_pair_code(db)
    db.commit()
    return {"bot_username": bot.get("username"), "pair_code": code}


@router.post("/telegram/pair")
def new_pair(db: DB, _: CurrentOwner) -> dict:
    if not settings.is_set(db, "telegram.bot_token"):
        raise BusinessRule("Cadastre o token do bot primeiro.", code="TELEGRAM_NOT_CONFIGURED")
    code = notify.new_pair_code(db)
    db.commit()
    return {"pair_code": code}


@router.post("/telegram/test")
def test_telegram(db: DB, _: CurrentOwner) -> dict:
    if not settings.telegram_linked(db):
        raise BusinessRule("Vincule o chat enviando /start <código> para o bot.", code="TELEGRAM_NOT_LINKED")
    notify.text(db, "🔔 Teste do Candidaturas: as notificações estão funcionando.")
    return {"ok": True}


@router.delete("/telegram", status_code=204)
def delete_telegram(db: DB, _: CurrentOwner) -> None:
    for k in ("telegram.bot_token", "telegram.chat_id", "telegram.pair_code", "telegram.offset"):
        settings.set_value(db, k, None)
    db.commit()


# ---------- E-mail ----------
class SMTPIn(BaseModel):
    host: str = Field(min_length=3, max_length=200)
    port: int = Field(587, ge=1, le=65535)
    username: str = Field(min_length=1, max_length=200)
    password: str | None = Field(None, max_length=200)
    security: Literal["starttls", "ssl", "none"] = "starttls"
    from_email: EmailStr
    from_name: str = Field("", max_length=120)


@router.put("/smtp")
def put_smtp(body: SMTPIn, db: DB, _: CurrentOwner) -> dict:
    settings.set_many(db, {**body.model_dump(), "from_email": str(body.from_email)}, "smtp")
    db.commit()
    return {"ok": True}


@router.post("/smtp/test")
def test_smtp(db: DB, _: CurrentOwner) -> dict:
    if not settings.smtp_configured(db):
        raise BusinessRule("Preencha o SMTP primeiro.", code="SMTP_NOT_CONFIGURED")
    mail.check_smtp(apps_svc.smtp_config(db))
    return {"ok": True}


class IMAPIn(BaseModel):
    host: str = Field(min_length=3, max_length=200)
    port: int = Field(993, ge=1, le=65535)
    username: str = Field(min_length=1, max_length=200)
    password: str | None = Field(None, max_length=200)
    folder: str = Field("INBOX", max_length=100)
    enabled: bool = False
    sender_filter: str = Field("", max_length=200)


@router.put("/imap")
def put_imap(body: IMAPIn, db: DB, _: CurrentOwner) -> dict:
    settings.set_many(db, body.model_dump(), "imap")
    db.commit()
    return {"ok": True}


# ---------- Preferências ----------
class PrefsIn(BaseModel):
    daily_send_limit: int = Field(10, ge=1, le=100)
    min_score_notify: int = Field(60, ge=0, le=100)
    default_template: str = "classico"


@router.put("/prefs")
def put_prefs(body: PrefsIn, db: DB, _: CurrentOwner) -> dict:
    if body.default_template not in RESUME_TEMPLATES:
        raise BusinessRule("Template desconhecido.", code="TEMPLATE_UNKNOWN")
    settings.set_many(db, body.model_dump(), "prefs")
    db.commit()
    return {"ok": True}


# ---------- Fontes RSS ----------
class SourceIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    url: HttpUrl
    enabled: bool = True


def _source_out(s: JobSource) -> dict:
    return {
        "id": s.id,
        "name": s.name,
        "url": s.url,
        "enabled": s.enabled,
        "last_checked_at": s.last_checked_at,
        "last_error": s.last_error,
    }


@router.get("/sources")
def list_sources(db: DB, _: CurrentOwner) -> list[dict]:
    return [_source_out(s) for s in db.query(JobSource).order_by(JobSource.name)]


@router.post("/sources", status_code=201)
def create_source(body: SourceIn, db: DB, _: CurrentOwner) -> dict:
    assert_public_url(str(body.url))
    s = JobSource(kind="rss", name=body.name, url=str(body.url), enabled=body.enabled)
    db.add(s)
    db.commit()
    return _source_out(s)


@router.put("/sources/{source_id}")
def update_source(source_id: int, body: SourceIn, db: DB, _: CurrentOwner) -> dict:
    s = db.get(JobSource, source_id)
    if s is None:
        raise NotFound("Fonte não encontrada.")
    assert_public_url(str(body.url))
    s.name, s.url, s.enabled = body.name, str(body.url), body.enabled
    db.commit()
    return _source_out(s)


@router.delete("/sources/{source_id}", status_code=204)
def delete_source(source_id: int, db: DB, _: CurrentOwner) -> None:
    s = db.get(JobSource, source_id)
    if s is None:
        raise NotFound("Fonte não encontrada.")
    db.delete(s)
    db.commit()


@router.post("/sources/poll", status_code=202)
def poll_now(db: DB, _: CurrentOwner) -> dict:
    task = queue.enqueue(db, "poll_sources", {}, dedupe=True, max_attempts=1)
    db.commit()
    return {"task_id": task.id}
