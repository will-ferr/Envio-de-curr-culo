from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.errors import Unauthorized
from app.models import Owner
from app.security import SESSION_COOKIE, decode_session_token, session_matches_password

DB = Annotated[Session, Depends(get_db)]


def get_owner_optional(request: Request, db: DB) -> Owner | None:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    claims = decode_session_token(token)
    if not claims:
        return None
    owner = db.scalar(select(Owner).where(Owner.id == int(claims["sub"])))
    if owner is None or not session_matches_password(claims, owner.password_hash):
        return None
    return owner


def get_owner(owner: Annotated[Owner | None, Depends(get_owner_optional)]) -> Owner:
    if owner is None:
        raise Unauthorized("Faça login para continuar.", code="NOT_AUTHENTICATED")
    return owner


CurrentOwner = Annotated[Owner, Depends(get_owner)]
