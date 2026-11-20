"""Configurações editáveis pela interface, persistidas em `app_settings`.

Segredos (chave de IA, senhas, token do bot) são criptografados com Fernet e
nunca voltam para o navegador: a API só informa se estão definidos.
"""

from typing import Any

from sqlalchemy.orm import Session

from app.models import AppSetting
from app.security import decrypt, encrypt

DEFAULTS: dict[str, Any] = {
    "ai.model": "claude-opus-5-5",
    "ai.effort": "medium",
    "smtp.port": 587,
    "smtp.security": "starttls",
    "imap.port": 993,
    "imap.folder": "INBOX",
    "imap.enabled": False,
    "imap.sender_filter": "",
    "prefs.daily_send_limit": 10,
    "prefs.min_score_notify": 60,
    "prefs.default_template": "classico",
}

SECRET_KEYS = {"ai.api_key", "telegram.bot_token", "smtp.password", "imap.password"}


def get(db: Session, key: str, default: Any = None) -> Any:
    row = db.get(AppSetting, key)
    if row is None or row.value in (None, ""):
        return DEFAULTS.get(key, default)
    if row.is_secret:
        return decrypt(str(row.value))
    return row.value


def set_value(db: Session, key: str, value: Any) -> None:
    secret = key in SECRET_KEYS
    stored = encrypt(str(value)) if secret and value not in (None, "") else value
    row = db.get(AppSetting, key)
    if row is None:
        db.add(AppSetting(key=key, value=stored, is_secret=secret))
    else:
        row.value = stored
        row.is_secret = secret


def set_many(db: Session, values: dict[str, Any], prefix: str) -> None:
    """Atualiza um grupo. Segredo enviado como None é mantido (o formulário não o reenvia)."""
    for name, value in values.items():
        key = f"{prefix}.{name}"
        if key in SECRET_KEYS and value is None:
            continue
        set_value(db, key, value)


def is_set(db: Session, key: str) -> bool:
    return bool(get(db, key))


def group(db: Session, prefix: str, fields: list[str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for f in fields:
        key = f"{prefix}.{f}"
        out[f] = {"configured": is_set(db, key)} if key in SECRET_KEYS else get(db, key)
    return out


def smtp_configured(db: Session) -> bool:
    return all(is_set(db, k) for k in ("smtp.host", "smtp.username", "smtp.password", "smtp.from_email"))


def imap_configured(db: Session) -> bool:
    return all(is_set(db, k) for k in ("imap.host", "imap.username", "imap.password"))


def telegram_linked(db: Session) -> bool:
    return is_set(db, "telegram.bot_token") and is_set(db, "telegram.chat_id")
