"""
Utilitários de autenticação JWT para o Freky.

Fluxo:
  1. POST /auth/login {username, password} → {access_token, token_type}
  2. Demais endpoints recebem  Authorization: Bearer <token>
  3. WebSocket recebe token como query param: /ws?token=<token>
"""

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import Depends, HTTPException, Query, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from core.settings import settings

log = logging.getLogger(__name__)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


# ── Usuários ──────────────────────────────────────────────────────

def _load_users() -> dict[str, dict]:
    """Carrega usuários definidos em FREKY_USERS (JSON)."""
    try:
        users = json.loads(settings.freky_users)
        return {u["username"]: u for u in users}
    except Exception:
        return {}

_USERS: dict[str, dict] = _load_users()


def authenticate_user(username: str, password: str) -> dict | None:
    user = _USERS.get(username)
    if not user:
        log.warning("Tentativa de login para usuário inexistente: %s", username)
        return None
    stored = user["password"]
    is_test = os.getenv("FREKY_ENV") == "test"
    if stored.startswith("$2b$"):
        valid = pwd_context.verify(password, stored)
    elif is_test:
        # Permite senha em texto puro apenas em ambiente de testes
        valid = password == stored
    else:
        log.error(
            "Usuário '%s' tem senha em texto puro. "
            "Use bcrypt hash em produção ($2b$...).",
            username,
        )
        return None
    if not valid:
        log.warning("Falha de autenticação para usuário: %s", username)
    return user if valid else None


# ── Token ─────────────────────────────────────────────────────────

def create_access_token(data: dict[str, Any]) -> str:
    payload = data.copy()
    payload["exp"] = datetime.now(timezone.utc) + timedelta(
        minutes=settings.jwt_expire_minutes
    )
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def _decode_token(token: str) -> dict:
    try:
        return jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido ou expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ── Dependências FastAPI ──────────────────────────────────────────

async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    payload = _decode_token(token)
    username: str | None = payload.get("sub")
    if not username or username not in _USERS:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuário não encontrado")
    return _USERS[username]


async def get_current_user_ws(token: str = Query(...)) -> dict:
    """Dependência para WebSocket — token via query param."""
    payload = _decode_token(token)
    username: str | None = payload.get("sub")
    if not username or username not in _USERS:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuário não encontrado")
    return _USERS[username]
