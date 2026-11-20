"""Envio (SMTP) e leitura de alertas (IMAP) usando a conta de e-mail da própria pessoa."""

import email
import imaplib
import smtplib
import ssl
from dataclasses import dataclass
from datetime import date, timedelta
from email.message import EmailMessage
from email.utils import formataddr, make_msgid
from pathlib import Path

from bs4 import BeautifulSoup

from app.errors import ExternalError


@dataclass
class SMTPConfig:
    host: str
    port: int
    username: str
    password: str
    security: str  # starttls | ssl | none
    from_email: str
    from_name: str = ""


@dataclass
class IMAPConfig:
    host: str
    port: int
    username: str
    password: str
    folder: str = "INBOX"
    sender_filter: str = ""


@dataclass
class Attachment:
    filename: str
    path: Path


def build_message(cfg: SMTPConfig, to: str, subject: str, body: str, attachments: list[Attachment]) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = formataddr((cfg.from_name, cfg.from_email)) if cfg.from_name else cfg.from_email
    msg["To"] = to
    msg["Subject"] = subject
    msg["Message-ID"] = make_msgid(domain=cfg.from_email.split("@")[-1])
    msg.set_content(body)
    for a in attachments:
        msg.add_attachment(a.path.read_bytes(), maintype="application", subtype="pdf", filename=a.filename)
    return msg


def send(cfg: SMTPConfig, msg: EmailMessage, timeout: float = 30) -> None:
    ctx = ssl.create_default_context()
    try:
        if cfg.security == "ssl":
            server: smtplib.SMTP = smtplib.SMTP_SSL(cfg.host, cfg.port, timeout=timeout, context=ctx)
        else:
            server = smtplib.SMTP(cfg.host, cfg.port, timeout=timeout)
        with server:
            if cfg.security == "starttls":
                server.starttls(context=ctx)
            server.login(cfg.username, cfg.password)
            server.send_message(msg)
    except smtplib.SMTPAuthenticationError as exc:
        raise ExternalError(
            "O servidor de e-mail recusou usuário/senha. Para Gmail, use uma senha de app.", code="SMTP_AUTH"
        ) from exc
    except (smtplib.SMTPException, OSError) as exc:
        raise ExternalError(f"Falha ao enviar e-mail: {exc}", code="SMTP_ERROR") from exc


def check_smtp(cfg: SMTPConfig) -> None:
    """Conecta e autentica sem enviar nada."""
    ctx = ssl.create_default_context()
    try:
        server = (
            smtplib.SMTP_SSL(cfg.host, cfg.port, timeout=15, context=ctx)
            if cfg.security == "ssl"
            else smtplib.SMTP(cfg.host, cfg.port, timeout=15)
        )
        with server:
            if cfg.security == "starttls":
                server.starttls(context=ctx)
            server.login(cfg.username, cfg.password)
    except smtplib.SMTPAuthenticationError as exc:
        raise ExternalError("Usuário ou senha do SMTP recusados.", code="SMTP_AUTH") from exc
    except (smtplib.SMTPException, OSError) as exc:
        raise ExternalError(f"Não foi possível conectar ao SMTP: {exc}", code="SMTP_ERROR") from exc


@dataclass
class IncomingEmail:
    message_id: str
    subject: str
    sender: str
    text: str


def _body_text(msg: email.message.Message) -> str:
    html, plain = "", ""
    for part in msg.walk() if msg.is_multipart() else [msg]:
        ctype = part.get_content_type()
        payload = part.get_payload(decode=True)
        if not isinstance(payload, bytes):
            continue
        content = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
        if ctype == "text/plain" and not plain:
            plain = content
        elif ctype == "text/html" and not html:
            html = content
    if html:
        soup = BeautifulSoup(html, "html.parser")
        # Mantém os links: alertas de vaga são basicamente listas de links.
        for a in soup.find_all("a", href=True):
            a.replace_with(f"{a.get_text(' ', strip=True)} <{a['href']}>")
        return soup.get_text("\n", strip=True)
    return plain


def fetch_recent(cfg: IMAPConfig, since_days: int = 3, limit: int = 30) -> list[IncomingEmail]:
    """Lê e-mails recentes (sem marcá-los como lidos), opcionalmente filtrando pelo remetente."""
    since = (date.today() - timedelta(days=since_days)).strftime("%d-%b-%Y")
    criteria = ["SINCE", since]
    # Remove caracteres que poderiam alterar o comando IMAP.
    sender = "".join(ch for ch in cfg.sender_filter if ch not in '"\\\r\n').strip()
    if sender:
        criteria += ["FROM", f'"{sender}"']
    try:
        with imaplib.IMAP4_SSL(cfg.host, cfg.port, ssl_context=ssl.create_default_context()) as imap:
            imap.login(cfg.username, cfg.password)
            imap.select(cfg.folder, readonly=True)
            _, data = imap.search(None, *criteria)
            ids = (data[0].split() if data and data[0] else [])[-limit:]
            out = []
            for num in ids:
                _, parts = imap.fetch(num, "(BODY.PEEK[])")
                raw = parts[0][1] if parts and isinstance(parts[0], tuple) else None
                if not raw:
                    continue
                msg = email.message_from_bytes(raw)
                out.append(
                    IncomingEmail(
                        message_id=str(msg.get("Message-ID") or f"{cfg.username}:{num.decode()}"),
                        subject=str(msg.get("Subject") or ""),
                        sender=str(msg.get("From") or ""),
                        text=_body_text(msg)[:30000],
                    )
                )
            return out
    except imaplib.IMAP4.error as exc:
        raise ExternalError(f"IMAP recusou o acesso: {exc}", code="IMAP_AUTH") from exc
    except OSError as exc:
        raise ExternalError(f"Não foi possível conectar ao IMAP: {exc}", code="IMAP_ERROR") from exc
