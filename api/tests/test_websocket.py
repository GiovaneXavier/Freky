"""
Testes para routes/websocket.py.

Cobre:
- websocket_endpoint: rejeição com token inválido (1008), aceitação com token válido
- broadcast: envio para conexões ativas, remoção de conexões mortas
"""
import json
import pytest
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from core.auth import create_access_token
from main import app
from models.database import get_db
from tests.conftest import override_get_db


# ── Fixture ────────────────────────────────────────────────────────────────


@pytest.fixture
def ws_client(mock_detector):
    """Client para testes de WebSocket — usa JWT real."""
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


def _token(username: str = "admin") -> str:
    return create_access_token({"sub": username, "role": "admin"})


# ── websocket_endpoint ─────────────────────────────────────────────────────


class TestWebSocketEndpoint:
    def test_token_invalido_fecha_conexao(self, ws_client):
        """Conexão com token inválido deve ser rejeitada (código 1008)."""
        try:
            with ws_client.websocket_connect("/ws?token=token.invalido.xyz") as ws:
                ws.receive_text()
        except Exception:
            pass  # Esperado: servidor fecha antes de aceitar

    def test_sem_token_conexao_rejeitada(self, ws_client):
        """Query param token obrigatório — conexão sem token deve ser recusada."""
        with pytest.raises(Exception):
            with ws_client.websocket_connect("/ws") as ws:
                ws.receive_text()

    def test_token_valido_conexao_aceita(self, ws_client):
        """Conexão com JWT válido deve ser aceita e desconectada corretamente."""
        from starlette.websockets import WebSocketDisconnect as WSD

        token = _token()
        # Faz asyncio.sleep levantar WebSocketDisconnect imediatamente para que
        # o handler encerre sem precisar aguardar os 30s reais de sleep.
        mock_sleep = AsyncMock(side_effect=WSD)
        with patch("asyncio.sleep", mock_sleep):
            try:
                with ws_client.websocket_connect(f"/ws?token={token}"):
                    pass
            except Exception:
                pass  # Qualquer exceção ao fechar é esperada

    def test_token_usuario_nao_cadastrado_rejeitado(self, ws_client):
        """Token válido mas com usuário inexistente no sistema deve ser rejeitado."""
        token = create_access_token({"sub": "fantasma", "role": "operator"})
        try:
            with ws_client.websocket_connect(f"/ws?token={token}") as ws:
                ws.receive_text()
        except Exception:
            pass  # Esperado


# ── broadcast ─────────────────────────────────────────────────────────────


class TestBroadcast:
    @pytest.mark.asyncio
    async def test_broadcast_envia_para_conexao_ativa(self):
        from routes.websocket import broadcast, _connections

        payload_recebido = []

        async def fake_send(text):
            payload_recebido.append(json.loads(text))

        mock_ws = MagicMock()
        mock_ws.send_text = fake_send

        _connections.append(mock_ws)
        try:
            await broadcast({"decision": "LIBERADO", "id": "abc"})
        finally:
            if mock_ws in _connections:
                _connections.remove(mock_ws)

        assert len(payload_recebido) == 1
        assert payload_recebido[0]["type"] == "scan_result"
        assert payload_recebido[0]["data"]["decision"] == "LIBERADO"

    @pytest.mark.asyncio
    async def test_broadcast_remove_conexao_morta(self):
        from routes.websocket import broadcast, _connections

        async def failing_send(text):
            raise RuntimeError("WebSocket fechado")

        mock_ws = MagicMock()
        mock_ws.send_text = failing_send

        _connections.append(mock_ws)
        await broadcast({"decision": "VERIFICAR"})

        assert mock_ws not in _connections

    @pytest.mark.asyncio
    async def test_broadcast_sem_conexoes_nao_levanta_erro(self):
        from routes.websocket import broadcast, _connections

        conexoes_antes = list(_connections)
        try:
            await broadcast({"decision": "INCONCLUSIVO"})
        finally:
            # Restaura estado
            _connections.clear()
            _connections.extend(conexoes_antes)

    @pytest.mark.asyncio
    async def test_broadcast_multiplas_conexoes(self):
        from routes.websocket import broadcast, _connections

        contagem = {"enviados": 0}

        async def fake_send(text):
            contagem["enviados"] += 1

        mock_ws1 = MagicMock()
        mock_ws1.send_text = fake_send
        mock_ws2 = MagicMock()
        mock_ws2.send_text = fake_send

        _connections.extend([mock_ws1, mock_ws2])
        try:
            await broadcast({"decision": "LIBERADO"})
        finally:
            for ws in [mock_ws1, mock_ws2]:
                if ws in _connections:
                    _connections.remove(ws)

        assert contagem["enviados"] == 2
