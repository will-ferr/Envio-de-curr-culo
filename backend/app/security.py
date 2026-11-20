"""Senhas (Argon2), sessão (JWT em cookie httpOnly) e criptografia de segredos (Fernet)."""

import base64
import hashlib
from datetime import timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings
from app.db import utcnow

_hasher = PasswordHasher()
SESSION_COOKIE = "candidaturas_session"


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False


def create_session_token(owner_id: int, password_hash: str) -> str:
    s = get_settings()
    now = utcnow()
    payload = {
        "sub": str(owner_id),
        "iat": now,
        "exp": now + timedelta(hours=s.session_hours),
        # Trocar a senha invalida todas as sessões existentes.
        "pwv": _password_version(password_hash),
    }
    return jwt.encode(payload, s.secret_key, algorithm="HS256")


def decode_session_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, get_settings().secret_key, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None


def session_matches_password(claims: dict, password_hash: str) -> bool:
    return claims.get("pwv") == _password_version(password_hash)


def _password_version(password_hash: str) -> str:
    return hashlib.sha256(password_hash.encode()).hexdigest()[:16]


def _fernet() -> Fernet:
    # Chave derivada da SECRET_KEY com separação de domínio (não reaproveita a chave do JWT).
    digest = hashlib.sha256(b"candidaturas:secrets:" + get_settings().secret_key.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt(token: str) -> str | None:
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken:
        return None
