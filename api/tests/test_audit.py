"""
Testes para as rotas de auditoria:
  GET /audit/           — listagem com filtros e paginacao
  GET /audit/stats      — contagem por decisao
  GET /audit/daily      — serie temporal por dia
"""
import pytest
from datetime import datetime, timedelta


# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────

def _post_scan(client, sample_image_bytes, mock_detector, decision, detections=None):
    """Registra um scan via POST /scans/ e retorna o JSON de resposta."""
    from core.rules import Decision as D
    mock_detector.predict.return_value = (D[decision], detections or [])
    resp = client.post(
        "/scans/",
        files={"file": (f"{decision.lower()}.jpg", sample_image_bytes, "image/jpeg")},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


# ──────────────────────────────────────────────────────────────
# GET /audit/  — listagem
# ──────────────────────────────────────────────────────────────

class TestAuditList:
    def test_lista_vazia(self, client):
        resp = client.get("/audit/")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_retorna_scans_criados(self, client, sample_image_bytes, mock_detector):
        _post_scan(client, sample_image_bytes, mock_detector, "LIBERADO")
        _post_scan(client, sample_image_bytes, mock_detector, "VERIFICAR")

        resp = client.get("/audit/")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2

    def test_campos_obrigatorios_presentes(self, client, sample_image_bytes, mock_detector):
        _post_scan(client, sample_image_bytes, mock_detector, "LIBERADO")

        item = client.get("/audit/").json()[0]
        for field in ("id", "filename", "decision", "created_at", "detections",
                      "processing_time_ms", "operator_feedback", "operator_id"):
            assert field in item, f"Campo ausente: {field}"

    def test_filtro_decision_verificar(self, client, sample_image_bytes, mock_detector):
        _post_scan(client, sample_image_bytes, mock_detector, "LIBERADO")
        _post_scan(client, sample_image_bytes, mock_detector, "VERIFICAR")
        _post_scan(client, sample_image_bytes, mock_detector, "INCONCLUSIVO")

        resp = client.get("/audit/?decision=VERIFICAR")
        data = resp.json()
        assert len(data) == 1
        assert data[0]["decision"] == "VERIFICAR"

    def test_filtro_decision_liberado(self, client, sample_image_bytes, mock_detector):
        for _ in range(3):
            _post_scan(client, sample_image_bytes, mock_detector, "LIBERADO")
        _post_scan(client, sample_image_bytes, mock_detector, "VERIFICAR")

        resp = client.get("/audit/?decision=LIBERADO")
        data = resp.json()
        assert len(data) == 3
        assert all(s["decision"] == "LIBERADO" for s in data)

    def test_filtro_decision_invalida_retorna_vazio(self, client, sample_image_bytes, mock_detector):
        _post_scan(client, sample_image_bytes, mock_detector, "LIBERADO")
        resp = client.get("/audit/?decision=INVALIDA")
        # FastAPI nao valida o enum na query, a busca simplesmente nao casa
        assert resp.status_code == 200
        assert resp.json() == []

    def test_paginacao_page_size(self, client, sample_image_bytes, mock_detector):
        for _ in range(5):
            _post_scan(client, sample_image_bytes, mock_detector, "LIBERADO")

        resp = client.get("/audit/?page=1&page_size=3")
        assert len(resp.json()) == 3

    def test_paginacao_segunda_pagina(self, client, sample_image_bytes, mock_detector):
        for _ in range(5):
            _post_scan(client, sample_image_bytes, mock_detector, "LIBERADO")

        p1 = client.get("/audit/?page=1&page_size=3").json()
        p2 = client.get("/audit/?page=2&page_size=3").json()

        assert len(p1) == 3
        assert len(p2) == 2
        ids_p1 = {s["id"] for s in p1}
        ids_p2 = {s["id"] for s in p2}
        assert ids_p1.isdisjoint(ids_p2)

    def test_paginacao_pagina_alem_do_fim(self, client, sample_image_bytes, mock_detector):
        _post_scan(client, sample_image_bytes, mock_detector, "LIBERADO")
        resp = client.get("/audit/?page=999&page_size=50")
        assert resp.json() == []

    def test_ordenacao_decrescente_por_data(self, client, sample_image_bytes, mock_detector):
        _post_scan(client, sample_image_bytes, mock_detector, "LIBERADO")
        _post_scan(client, sample_image_bytes, mock_detector, "VERIFICAR")

        data = client.get("/audit/").json()
        datas = [s["created_at"] for s in data]
        assert datas == sorted(datas, reverse=True)

    def test_filtro_date_from(self, client, sample_image_bytes, mock_detector):
        """date_from filtra scans a partir daquela data (inclusive)."""
        _post_scan(client, sample_image_bytes, mock_detector, "LIBERADO")

        hoje = datetime.utcnow().date().isoformat()
        amanha = (datetime.utcnow().date() + timedelta(days=1)).isoformat()

        resp_hoje = client.get(f"/audit/?date_from={hoje}")
        assert len(resp_hoje.json()) == 1

        resp_amanha = client.get(f"/audit/?date_from={amanha}")
        assert resp_amanha.json() == []

    def test_filtro_date_to(self, client, sample_image_bytes, mock_detector):
        """date_to filtra scans ate aquela data (inclusive)."""
        _post_scan(client, sample_image_bytes, mock_detector, "LIBERADO")

        hoje = datetime.utcnow().date().isoformat()
        ontem = (datetime.utcnow().date() - timedelta(days=1)).isoformat()

        resp_hoje = client.get(f"/audit/?date_to={hoje}")
        assert len(resp_hoje.json()) == 1

        resp_ontem = client.get(f"/audit/?date_to={ontem}")
        assert resp_ontem.json() == []

    def test_filtro_combinado_decision_e_data(self, client, sample_image_bytes, mock_detector):
        _post_scan(client, sample_image_bytes, mock_detector, "VERIFICAR")
        _post_scan(client, sample_image_bytes, mock_detector, "LIBERADO")

        hoje = datetime.utcnow().date().isoformat()
        resp = client.get(f"/audit/?decision=VERIFICAR&date_from={hoje}")
        data = resp.json()
        assert len(data) == 1
        assert data[0]["decision"] == "VERIFICAR"


# ──────────────────────────────────────────────────────────────
# GET /audit/stats
# ──────────────────────────────────────────────────────────────

class TestAuditStats:
    def test_stats_vazio(self, client):
        resp = client.get("/audit/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["by_decision"] == {}

    def test_stats_com_um_scan(self, client, sample_image_bytes, mock_detector):
        _post_scan(client, sample_image_bytes, mock_detector, "LIBERADO")

        data = client.get("/audit/stats").json()
        assert data["total"] == 1
        assert data["by_decision"]["LIBERADO"] == 1

    def test_stats_soma_total_correta(self, client, sample_image_bytes, mock_detector):
        _post_scan(client, sample_image_bytes, mock_detector, "LIBERADO")
        _post_scan(client, sample_image_bytes, mock_detector, "LIBERADO")
        _post_scan(client, sample_image_bytes, mock_detector, "VERIFICAR")
        _post_scan(client, sample_image_bytes, mock_detector, "INCONCLUSIVO")

        data = client.get("/audit/stats").json()
        assert data["total"] == 4
        assert data["by_decision"]["LIBERADO"] == 2
        assert data["by_decision"]["VERIFICAR"] == 1
        assert data["by_decision"]["INCONCLUSIVO"] == 1
        assert sum(data["by_decision"].values()) == data["total"]

    def test_stats_sem_decisao_ausente_nao_aparece(self, client, sample_image_bytes, mock_detector):
        _post_scan(client, sample_image_bytes, mock_detector, "LIBERADO")

        data = client.get("/audit/stats").json()
        assert "VERIFICAR" not in data["by_decision"]
        assert "INCONCLUSIVO" not in data["by_decision"]


# ──────────────────────────────────────────────────────────────
# GET /audit/daily
# ──────────────────────────────────────────────────────────────

class TestAuditDaily:
    def test_retorna_lista(self, client):
        resp = client.get("/audit/daily")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_numero_de_dias_padrao(self, client):
        data = client.get("/audit/daily").json()
        assert len(data) == 14

    def test_numero_de_dias_customizado(self, client):
        data = client.get("/audit/daily?days=7").json()
        assert len(data) == 7

    def test_campos_presentes_em_cada_dia(self, client):
        data = client.get("/audit/daily?days=3").json()
        for item in data:
            assert "date" in item
            assert "LIBERADO" in item
            assert "VERIFICAR" in item
            assert "INCONCLUSIVO" in item

    def test_dias_sem_scan_tem_zeros(self, client):
        data = client.get("/audit/daily?days=7").json()
        for item in data:
            assert item["LIBERADO"] == 0
            assert item["VERIFICAR"] == 0
            assert item["INCONCLUSIVO"] == 0

    def test_scan_hoje_incrementa_contador(self, client, sample_image_bytes, mock_detector):
        _post_scan(client, sample_image_bytes, mock_detector, "LIBERADO")
        _post_scan(client, sample_image_bytes, mock_detector, "VERIFICAR")
        _post_scan(client, sample_image_bytes, mock_detector, "VERIFICAR")

        hoje = datetime.utcnow().date().isoformat()
        data = client.get("/audit/daily?days=7").json()
        hoje_row = next((r for r in data if r["date"] == hoje), None)

        assert hoje_row is not None
        assert hoje_row["LIBERADO"] == 1
        assert hoje_row["VERIFICAR"] == 2
        assert hoje_row["INCONCLUSIVO"] == 0

    def test_dias_em_ordem_crescente(self, client):
        data = client.get("/audit/daily?days=7").json()
        datas = [r["date"] for r in data]
        assert datas == sorted(datas)

    def test_limite_maximo_de_dias(self, client):
        resp = client.get("/audit/daily?days=91")
        assert resp.status_code == 422  # Query validation: ge=1, le=90

    def test_limite_minimo_de_dias(self, client):
        resp = client.get("/audit/daily?days=0")
        assert resp.status_code == 422
