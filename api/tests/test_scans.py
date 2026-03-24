import pytest
from core.rules import Decision, Detection


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_process_scan_liberado(client, sample_image_bytes, mock_detector):
    mock_detector.predict.return_value = (Decision.LIBERADO, [])

    response = client.post(
        "/scans/",
        files={"file": ("test_scan.jpg", sample_image_bytes, "image/jpeg")},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["decision"] == "LIBERADO"
    assert data["detections"] == []
    assert data["filename"] == "test_scan.jpg"
    assert "id" in data


def test_process_scan_verificar(client, sample_image_bytes, mock_detector):
    detections = [
        Detection(class_name="mobile_phone", confidence=0.92, bbox=[0.1, 0.1, 0.3, 0.4])
    ]
    mock_detector.predict.return_value = (Decision.VERIFICAR, detections)

    response = client.post(
        "/scans/",
        files={"file": ("bag_scan.jpg", sample_image_bytes, "image/jpeg")},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["decision"] == "VERIFICAR"
    assert len(data["detections"]) == 1
    assert data["detections"][0]["class_name"] == "mobile_phone"
    assert data["detections"][0]["confidence"] == pytest.approx(0.92)


def test_process_scan_inconclusivo(client, sample_image_bytes, mock_detector):
    mock_detector.predict.return_value = (Decision.INCONCLUSIVO, [])

    response = client.post(
        "/scans/",
        files={"file": ("blur_scan.jpg", sample_image_bytes, "image/jpeg")},
    )

    assert response.status_code == 200
    assert response.json()["decision"] == "INCONCLUSIVO"


def test_submit_feedback(client, sample_image_bytes, mock_detector):
    mock_detector.predict.return_value = (Decision.VERIFICAR, [
        Detection(class_name="tablet", confidence=0.88, bbox=[0.2, 0.2, 0.5, 0.6])
    ])

    # 1. Processa um scan
    scan_resp = client.post(
        "/scans/",
        files={"file": ("tablet_scan.jpg", sample_image_bytes, "image/jpeg")},
    )
    scan_id = scan_resp.json()["id"]

    # 2. Operador envia feedback
    fb_resp = client.post(
        f"/scans/{scan_id}/feedback",
        json={"operator_id": "op_001", "feedback": "confirmed"},
    )
    assert fb_resp.status_code == 200
    assert fb_resp.json() == {"status": "ok"}


def test_feedback_scan_nao_encontrado(client):
    response = client.post(
        "/scans/id-inexistente/feedback",
        json={"operator_id": "op_001", "feedback": "false_positive"},
    )
    assert response.status_code == 404


def test_audit_list_empty(client):
    response = client.get("/audit/")
    assert response.status_code == 200
    assert response.json() == []


def test_audit_stats_empty(client):
    response = client.get("/audit/stats")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["by_decision"] == {}
