"""
Testes para core/auth.py e routes/auth.py.

Cobre:
- authenticate_user: senha plain-text, bcrypt, senha errada, usuário inexistente
- create_access_token / _decode_token: geração e validação de JWT
- Rota /auth/login: sucesso, credenciais inválidas
- get_current_user: acesso com token válido e inválido a endpoint protegido
"""
import pytest
from contextlib import asynccontextmanager
from unittest.mock import patch
from fastapi.testclient import TestClient

from core.auth import authenticate_user, create_access_token, _decode_token
from main import app
from models.database import get_db
from tests.conftest import override_get_db


# ── Fixture: client sem override de autenticação ───────────────────────────


@pytest.fixture
def auth_client(mock_detector):
    """Client que usa JWT real — não bypassa get_current_user."""
    app.dependency_overrides[get_db] = override_get_db
    app.state.detector = mock_detector

    @asynccontextmanager
    async def mock_lifespan(_app):
        _app.state.detector = mock_detector
        yield

    with patch.object(app.router, "lifespan_context", mock_lifespan):
        with TestClient(app) as c:
            yield c

    app.dependency_overrides.clear()


# ── authenticate_user ──────────────────────────────────────────────────────


class TestAuthenticateUser:
    def test_credenciais_validas_plain_text(self):
        # Usuário padrão definido em settings.freky_users
        user = authenticate_user("admin", "admin")
        assert user is not None
        assert user["username"] == "admin"
        assert user["role"] == "admin"

    def test_senha_errada_retorna_none(self):
        assert authenticate_user("admin", "errada") is None

    def test_usuario_inexistente_retorna_none(self):
        assert authenticate_user("naoexiste", "qualquer") is None

    def test_credenciais_validas_bcrypt(self):
        # Usa hash bcrypt real ($2b$...) — autentica via pwd_context.verify
        # Mockamos pwd_context para não depender do binário bcrypt do ambiente
        from unittest.mock import call

        fake_hash = "$2b$12$fakehashfakehashfakehashfakehashfakehashfakehash"
        fake_users = {
            "operador": {
                "username": "operador",
                "password": fake_hash,
                "role": "operator",
            }
        }
        with patch("core.auth._USERS", fake_users):
            with patch("core.auth.pwd_context") as mock_ctx:
                mock_ctx.verify.return_value = True
                user = authenticate_user("operador", "senha_segura")
                assert user is not None
                mock_ctx.verify.assert_called_once_with("senha_segura", fake_hash)

            with patch("core.auth.pwd_context") as mock_ctx:
                mock_ctx.verify.return_value = False
                assert authenticate_user("operador", "errada") is None


# ── create_access_token / _decode_token ───────────────────────────────────


class TestTokenUtils:
    def test_create_access_token_retorna_string(self):
        token = create_access_token({"sub": "admin"})
        assert isinstance(token, str) and len(token) > 0

    def test_decode_token_valido(self):
        token = create_access_token({"sub": "admin", "role": "admin"})
        payload = _decode_token(token)
        assert payload["sub"] == "admin"
        assert payload["role"] == "admin"

    def test_decode_token_invalido_levanta_401(self):
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            _decode_token("token.invalido.aqui")
        assert exc_info.value.status_code == 401

    def test_decode_token_vazio_levanta_401(self):
        from fastapi import HTTPException

        with pytest.raises(HTTPException):
            _decode_token("")


# ── Rota /auth/login ───────────────────────────────────────────────────────


class TestLoginRoute:
    def test_login_sucesso(self, auth_client):
        resp = auth_client.post(
            "/auth/login",
            data={"username": "admin", "password": "admin"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["username"] == "admin"
        assert data["role"] == "admin"

    def test_login_credenciais_invalidas(self, auth_client):
        resp = auth_client.post(
            "/auth/login",
            data={"username": "admin", "password": "errado"},
        )
        assert resp.status_code == 401

    def test_login_usuario_inexistente(self, auth_client):
        resp = auth_client.post(
            "/auth/login",
            data={"username": "fantasma", "password": "qualquer"},
        )
        assert resp.status_code == 401


# ── get_current_user via endpoint protegido ───────────────────────────────


class TestGetCurrentUser:
    def test_acesso_sem_token_retorna_401(self, auth_client):
        resp = auth_client.get("/audit/")
        assert resp.status_code == 401

    def test_acesso_token_invalido_retorna_401(self, auth_client):
        resp = auth_client.get(
            "/audit/",
            headers={"Authorization": "Bearer token.invalido.xyz"},
        )
        assert resp.status_code == 401

    def test_acesso_token_valido_retorna_200(self, auth_client):
        login = auth_client.post(
            "/auth/login",
            data={"username": "admin", "password": "admin"},
        )
        token = login.json()["access_token"]

        resp = auth_client.get(
            "/audit/",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200

    def test_token_usuario_nao_cadastrado_retorna_401(self, auth_client):
        # Token válido assinado mas com sub de usuário que não existe no sistema
        token = create_access_token({"sub": "fantasma"})
        resp = auth_client.get(
            "/audit/",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 401
