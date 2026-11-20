"""Notificações e comandos pelo Telegram.

Botões (callback_data):
  g:<job>  gerar currículo e carta      d:<job>  descartar vaga
  e:<job>  aprovar e enviar por e-mail  m:<job>  aprovar; candidato-me pelo site
Só o chat vinculado no pareamento pode acionar os botões.
"""

import logging
import secrets

from sqlalchemy.orm import Session

from app.config import get_settings
from app.domain import validation
from app.errors import AppError
from app.models import Job
from app.services import applications as apps_svc
from app.services import queue, settings
from app.services.telegram import TelegramClient, esc

log = logging.getLogger(__name__)


def client(db: Session) -> TelegramClient | None:
    token = settings.get(db, "telegram.bot_token")
    return TelegramClient(token) if token else None


def _panel(path: str) -> str:
    return f"{get_settings().public_url.rstrip('/')}{path}"


def new_pair_code(db: Session) -> str:
    code = f"{secrets.randbelow(10**6):06d}"
    settings.set_value(db, "telegram.pair_code", code)
    return code


def _send(db: Session, text: str, buttons: list[list[tuple[str, str]]] | None = None) -> None:
    if not settings.telegram_linked(db):
        return
    tg = client(db)
    if tg is None:
        return
    try:
        tg.send_message(settings.get(db, "telegram.chat_id"), text, buttons)
    finally:
        tg.close()


def job_matched(db: Session, job: Job) -> None:
    a = job.analysis
    if a is None or a.score < int(settings.get(db, "prefs.min_score_notify")):
        return
    missing = ", ".join(esc(m) for m in a.missing[:5]) or "—"
    text = (
        f"🎯 <b>{esc(job.title)}</b>{' — ' + esc(job.company) if job.company else ''}\n"
        f"Compatibilidade: <b>{a.score}%</b>\n\n{esc(a.summary)}\n\n<i>Falta:</i> {missing}"
    )
    _send(
        db,
        text,
        [
            [("✍️ Gerar currículo", f"g:{job.id}"), ("🗑 Descartar", f"d:{job.id}")],
            [("Abrir no painel", _panel(f"/vagas/{job.id}"))],
        ],
    )


def documents_ready(db: Session, job: Job) -> None:
    if not settings.telegram_linked(db):
        return
    resume = next((d for d in sorted(job.documents, key=lambda d: -d.id) if d.kind == "resume"), None)
    if resume is None or not resume.pdf_path:
        return
    errors = [i for i in resume.issues if i["severity"] == "error"]
    warnings = [i for i in resume.issues if i["severity"] == "warning"]
    caption = f"📄 Currículo para <b>{esc(job.title)}</b>"
    if errors:
        caption += f"\n⛔ {len(errors)} problema(s) impedem a aprovação. Revise no painel."
        buttons = [[("Revisar no painel", _panel(f"/vagas/{job.id}"))]]
    else:
        if warnings:
            caption += f"\n⚠️ {len(warnings)} ponto(s) para conferir antes de enviar."
        row = []
        if job.contact_email and settings.smtp_configured(db):
            row.append(("📤 Aprovar e enviar", f"e:{job.id}"))
        row.append(("✅ Vou me candidatar pelo site", f"m:{job.id}"))
        buttons = [row, [("Revisar no painel", _panel(f"/vagas/{job.id}"))]]

    from pathlib import Path

    tg = client(db)
    if tg is None:
        return
    try:
        tg.send_document(settings.get(db, "telegram.chat_id"), Path(resume.pdf_path), caption, buttons)
    finally:
        tg.close()


def text(db: Session, message: str) -> None:
    _send(db, message)


def handle_update(db: Session, update: dict, tg: TelegramClient) -> None:
    """Processa uma atualização do getUpdates. Chamado pelo worker."""
    if msg := update.get("message"):
        _handle_message(db, msg, tg)
    elif cb := update.get("callback_query"):
        _handle_callback(db, cb, tg)


def _handle_message(db: Session, msg: dict, tg: TelegramClient) -> None:
    chat_id = str(msg.get("chat", {}).get("id", ""))
    text_in = (msg.get("text") or "").strip()
    linked = settings.get(db, "telegram.chat_id")

    if text_in.startswith("/start"):
        code = text_in.removeprefix("/start").strip()
        expected = settings.get(db, "telegram.pair_code")
        if expected and secrets.compare_digest(code, str(expected)):
            settings.set_value(db, "telegram.chat_id", chat_id)
            settings.set_value(db, "telegram.pair_code", None)
            db.commit()
            tg.send_message(chat_id, "✅ Pronto! Este chat vai receber as vagas compatíveis e os currículos gerados.")
        elif chat_id != str(linked or ""):
            tg.send_message(chat_id, "Envie /start seguido do código mostrado em Configurações → Telegram.")
        return
    if chat_id == str(linked or ""):
        tg.send_message(chat_id, "Use os botões das mensagens de vaga, ou abra o painel para mais opções.")


def _handle_callback(db: Session, cb: dict, tg: TelegramClient) -> None:
    chat_id = str(cb.get("message", {}).get("chat", {}).get("id", ""))
    if chat_id != str(settings.get(db, "telegram.chat_id") or ""):
        tg.answer_callback(cb["id"], "Chat não autorizado.")
        return

    action, _, raw_id = (cb.get("data") or "").partition(":")
    job = db.get(Job, int(raw_id)) if raw_id.isdigit() else None
    if job is None:
        tg.answer_callback(cb["id"], "Vaga não encontrada.")
        return

    try:
        if action == "g":
            queue.enqueue(db, "generate_documents", {"job_id": job.id, "notify": True})
            reply = "Gerando currículo e carta…"
        elif action == "d":
            job.status = "discarded"
            reply = "Vaga descartada."
        elif action == "e":
            app = apps_svc.approve(db, job, actor="telegram")
            apps_svc.check_can_email(db, app)
            queue.enqueue(db, "send_application", {"application_id": app.id, "actor": "telegram"}, max_attempts=1)
            reply = "Aprovada. Enviando e-mail…"
        elif action == "m":
            app = apps_svc.approve(db, job, actor="telegram")
            apps_svc.mark_sent_manually(db, app, actor="telegram")
            reply = "Aprovada e marcada como enviada."
            if job.url:
                tg.send_message(chat_id, f"Candidate-se aqui: {esc(job.url)}")
        else:
            reply = "Ação desconhecida."
        db.commit()
    except AppError as exc:
        db.rollback()
        reply = exc.message[:190]
    tg.answer_callback(cb["id"], reply)


def resume_has_errors(job: Job) -> bool:
    resume = next((d for d in sorted(job.documents, key=lambda d: -d.id) if d.kind == "resume"), None)
    return resume is None or validation.has_errors(resume.issues)
