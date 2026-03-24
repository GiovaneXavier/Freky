"""
Testes para as melhorias implementadas:
  - Validação de upload (413 arquivo grande, 422 formato inválido)
  - Health check /health/ready (200 ready, 503 degraded)
  - Export CSV /audit/export (conteúdo, filtros)
"""
import csv
import io
from unittest.mock import AsyncMock, MagicMock, patch

from PIL import Image

from core.rules import Decision


# ── Fixtures helpers ───────────────────────────────────────────────────────

def _make_invalid_bytes() -> bytes:
    return b"this is not an image - plain text content"


def _make_large_bytes(size_bytes: int) -> bytes:
    # Gera bytes que passam na verificação de tamanho mas não no PIL
    return b"\x00" * size_bytes


# ── Upload validation ──────────────────────────────────────────────────────


class TestUploadValidation:
    def test_arquivo_muito_grande_retorna_413(self, client):
        """Arquivo acima de MAX_UPLOAD_BYTES deve ser rejeitado com 413."""
        from core.settings import settings

        big = _make_large_bytes(settings.max_upload_bytes + 1)
        response = client.post(
            "/scans/",
            files={"file": ("big_scan.jpg", big, "image/jpeg")},
        )
        assert response.status_code == 413
        assert "grande" in response.json()["detail"].lower()

    def test_arquivo_invalido_retorna_422(self, client):
        """Arquivo com bytes que não formam uma imagem válida deve retornar 422."""
        response = client.post(
            "/scans/",
            files={"file": ("fake.jpg", _make_invalid_bytes(), "image/jpeg")},
        )
        assert response.status_code == 422
        assert "imagem" in response.json()["detail"].lower()

    def test_imagem_valida_passa_validacao(self, client, sample_image_bytes, mock_detector):
        """JPEG válido deve passar pela validação e ser processado normalmente."""
        mock_detector.predict.return_value = (Decision.LIBERADO, [])
        response = client.post(
            "/scans/",
            files={"file": ("valid.jpg", sample_image_bytes, "image/jpeg")},
        )
        assert response.status_code == 200

    def test_imagem_png_valida_passa_validacao(self, client, mock_detector):
        """PNG válido também deve ser aceito."""
        buf = io.BytesIO()
        Image.new("RGB", (64, 64)).save(buf, format="PNG")
        png_bytes = buf.getvalue()

        mock_detector.predict.return_value = (Decision.LIBERADO, [])
        response = client.post(
            "/scans/",
            files={"file": ("scan.png", png_bytes, "image/png")},
        )
        assert response.status_code == 200


# ── Health checks ──────────────────────────────────────────────────────────


class TestHealthReady:
    def test_health_simples_sempre_ok(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_health_ready_all_ok(self, client):
        """Quando DB, Redis e modelo estão operacionais, retorna 200 ready."""
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.execute = AsyncMock(return_value=None)
        mock_session_factory = MagicMock(return_value=mock_session)

        mock_redis_client = AsyncMock()
        mock_redis_client.ping = AsyncMock(return_value=True)

        with patch("models.database.SessionLocal", mock_session_factory), \
             patch("core.cache.get_redis", return_value=mock_redis_client):
            response = client.get("/health/ready")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
        assert data["checks"]["database"] == "ok"
        assert data["checks"]["redis"] == "ok"
        assert data["checks"]["model"] == "ok"

    def test_health_ready_db_falha_retorna_503(self, client):
        """Falha na conexão com o banco retorna 503 degraded."""
        mock_session_factory = MagicMock(side_effect=Exception("DB offline"))

        mock_redis_client = AsyncMock()
        mock_redis_client.ping = AsyncMock(return_value=True)

        with patch("models.database.SessionLocal", mock_session_factory), \
             patch("core.cache.get_redis", return_value=mock_redis_client):
            response = client.get("/health/ready")

        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "degraded"
        assert "error" in data["checks"]["database"]

    def test_health_ready_redis_falha_retorna_503(self, client):
        """Falha no Redis retorna 503 degraded."""
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.execute = AsyncMock(return_value=None)
        mock_session_factory = MagicMock(return_value=mock_session)

        mock_redis_client = AsyncMock()
        mock_redis_client.ping = AsyncMock(side_effect=Exception("Redis offline"))

        with patch("models.database.SessionLocal", mock_session_factory), \
             patch("core.cache.get_redis", return_value=mock_redis_client):
            response = client.get("/health/ready")

        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "degraded"
        assert "error" in data["checks"]["redis"]

    def test_health_ready_sem_modelo_retorna_503(self, client):
        """Sem modelo ONNX carregado retorna 503 degraded."""
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.execute = AsyncMock(return_value=None)
        mock_session_factory = MagicMock(return_value=mock_session)

        mock_redis_client = AsyncMock()
        mock_redis_client.ping = AsyncMock(return_value=True)

        # Simula detector sem _session (modelo não carregado)
        from main import app
        original_detector = app.state.detector
        app.state.detector = MagicMock(_session=None)

        try:
            with patch("models.database.SessionLocal", mock_session_factory), \
                 patch("core.cache.get_redis", return_value=mock_redis_client):
                response = client.get("/health/ready")
        finally:
            app.state.detector = original_detector

        assert response.status_code == 503
        data = response.json()
        assert data["checks"]["model"] == "not loaded"

    def test_health_ready_retorna_todos_checks(self, client):
        """Resposta deve sempre conter as três chaves de checks."""
        response = client.get("/health/ready")
        data = response.json()
        assert "database" in data["checks"]
        assert "redis" in data["checks"]
        assert "model" in data["checks"]


# ── Audit export ───────────────────────────────────────────────────────────


class TestAuditExport:
    def _criar_scan(self, client, sample_image_bytes, mock_detector, decision=Decision.LIBERADO):
        mock_detector.predict.return_value = (decision, [])
        resp = client.post(
            "/scans/",
            files={"file": ("test.jpg", sample_image_bytes, "image/jpeg")},
        )
        assert resp.status_code == 200
        return resp.json()

    def test_export_sem_scans_retorna_so_cabecalho(self, client):
        response = client.get("/audit/export")
        assert response.status_code == 200
        assert "text/csv" in response.headers["content-type"]

        rows = list(csv.DictReader(io.StringIO(response.text)))
        assert rows == []
        assert "id" in response.text
        assert "decision" in response.text

    def test_export_retorna_csv_com_dados(self, client, sample_image_bytes, mock_detector):
        self._criar_scan(client, sample_image_bytes, mock_detector)

        response = client.get("/audit/export")

        assert response.status_code == 200
        assert "attachment" in response.headers.get("content-disposition", "")
        assert ".csv" in response.headers.get("content-disposition", "")

        rows = list(csv.DictReader(io.StringIO(response.text)))
        assert len(rows) == 1
        assert rows[0]["decision"] == "LIBERADO"
        assert rows[0]["filename"] == "test.jpg"

    def test_export_filtro_decision(self, client, sample_image_bytes, mock_detector):
        self._criar_scan(client, sample_image_bytes, mock_detector, Decision.LIBERADO)
        self._criar_scan(client, sample_image_bytes, mock_detector, Decision.VERIFICAR)

        response = client.get("/audit/export?decision=LIBERADO")

        rows = list(csv.DictReader(io.StringIO(response.text)))
        assert len(rows) == 1
        assert rows[0]["decision"] == "LIBERADO"

    def test_export_multiplos_scans(self, client, sample_image_bytes, mock_detector):
        for _ in range(3):
            self._criar_scan(client, sample_image_bytes, mock_detector, Decision.LIBERADO)

        response = client.get("/audit/export")
        rows = list(csv.DictReader(io.StringIO(response.text)))
        assert len(rows) == 3

    def test_export_colunas_esperadas(self, client, sample_image_bytes, mock_detector):
        self._criar_scan(client, sample_image_bytes, mock_detector)
        response = client.get("/audit/export")

        reader = csv.DictReader(io.StringIO(response.text))
        expected = {
            "id", "created_at", "filename", "decision",
            "processing_time_ms", "operator_id", "operator_feedback", "feedback_at",
        }
        assert set(reader.fieldnames) == expected
