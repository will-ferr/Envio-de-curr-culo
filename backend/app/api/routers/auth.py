import time
from collections import defaultdict, deque

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import DB, CurrentOwner
from app.config import get_settings
from app.errors import BusinessRule, TooManyRequests, Unauthorized
from app.models import Owner
from app.security import SESSION_COOKIE, create_session_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["autenticação"])

# Limite simples contra força bruta: 5 tentativas por minuto por IP (instância de um único processo).
_ATTEMPTS: dict[str, deque[float]] = defaultdict(deque)
_WINDOW, _MAX = 60.0, 5


def _check_rate(ip: str) -> None:
    """Bloqueia o IP depois de 5 falhas no último minuto. Logins corretos não contam."""
    now = time.monotonic()
    q = _ATTEMPTS[ip]
    while q and now - q[0] > _WINDOW:
        q.popleft()
    if len(q) >= _MAX:
        raise TooManyRequests("Muitas tentativas. Aguarde um minuto.", code="LOGIN_RATE_LIMITED")


def _record_failure(ip: str) -> None:
    _ATTEMPTS[ip].append(time.monotonic())


def _set_cookie(response: Response, owner: Owner) -> None:
    s = get_settings()
    response.set_cookie(
        SESSION_COOKIE,
        create_session_token(owner.id, owner.password_hash),
        max_age=s.session_hours * 3600,
        httponly=True,
        samesite="strict",
        secure=s.public_url.startswith("https://"),
        path="/",
    )


class LoginIn(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=200)


@router.post("/login")
def login(body: LoginIn, request: Request, response: Response, db: DB) -> dict:
    ip = request.client.host if request.client else "?"
    _check_rate(ip)
    owner = db.scalar(select(Owner).where(Owner.email == body.email.strip().lower()))
    # Mesma resposta para e-mail ou senha errados (não revela qual dos dois).
    if owner is None or not verify_password(owner.password_hash, body.password):
        _record_failure(ip)
        raise Unauthorized("E-mail ou senha incorretos.", code="INVALID_CREDENTIALS")
    _ATTEMPTS.pop(ip, None)
    _set_cookie(response, owner)
    return {"name": owner.name, "email": owner.email}


@router.post("/logout")
def logout(response: Response) -> dict:
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"ok": True}


@router.get("/me")
def me(owner: CurrentOwner) -> dict:
    return {"name": owner.name, "email": owner.email}


class PasswordIn(BaseModel):
    current_password: str = Field(max_length=200)
    new_password: str = Field(min_length=10, max_length=200)


@router.post("/password")
def change_password(body: PasswordIn, response: Response, owner: CurrentOwner, db: DB) -> dict:
    if not verify_password(owner.password_hash, body.current_password):
        raise BusinessRule("Senha atual incorreta.", code="WRONG_PASSWORD")
    owner.password_hash = hash_password(body.new_password)
    db.commit()
    _set_cookie(response, owner)  # as outras sessões deixam de valer
    return {"ok": True}
