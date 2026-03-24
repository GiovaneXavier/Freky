"""
Testes para core/detector.py.

Cobre:
- Detector.__init__: sem modelo, thresholds padrão e customizados
- Detector.predict: modo sem modelo → INCONCLUSIVO
- Detector._preprocess: shape, normalização, conversão de modo
- Detector._postprocess: sem detecções, detecção com confiança alta,
  clamp de bbox, classe desconhecida
- Detector._load_model: carregamento via onnxruntime mockado
"""
import numpy as np
import pytest
from PIL import Image
from unittest.mock import MagicMock, patch

from core.detector import Detector
from core.rules import Decision


# ── Fixture ────────────────────────────────────────────────────────────────


@pytest.fixture
def detector(tmp_path):
    """Detector sem modelo ONNX (arquivo inexistente)."""
    return Detector(model_path=str(tmp_path / "naoexiste.onnx"))


# ── Detector.__init__ ──────────────────────────────────────────────────────


class TestDetectorInit:
    def test_session_none_sem_modelo(self, detector):
        assert detector._session is None

    def test_thresholds_padrao(self, detector):
        assert detector.confidence_threshold == 0.60
        assert detector.high_confidence_threshold == 0.85

    def test_class_thresholds_padrao_vazio(self, detector):
        assert detector.class_confidence_thresholds == {}

    def test_class_thresholds_customizados(self, tmp_path):
        d = Detector(
            model_path=str(tmp_path / "naoexiste.onnx"),
            class_confidence_thresholds={"mobile_phone": 0.42},
        )
        assert d.class_confidence_thresholds["mobile_phone"] == 0.42


# ── Detector.predict ───────────────────────────────────────────────────────


class TestDetectorPredict:
    def test_predict_sem_modelo_retorna_inconclusivo(self, detector):
        decision, detections = detector.predict("qualquer.jpg")
        assert decision == Decision.INCONCLUSIVO
        assert detections == []


# ── Detector._preprocess ──────────────────────────────────────────────────


class TestDetectorPreprocess:
    def test_shape_correto(self, detector):
        img = Image.new("RGB", (300, 200))
        tensor = detector._preprocess(img, target_size=640)
        # [batch=1, channels=3, height=640, width=640]
        assert tensor.shape == (1, 3, 640, 640)

    def test_valores_normalizados_entre_0_e_1(self, detector):
        img = Image.new("RGB", (100, 100), color=(255, 128, 0))
        tensor = detector._preprocess(img)
        assert tensor.min() >= 0.0
        assert tensor.max() <= 1.0

    def test_imagem_branca_max_igual_a_1(self, detector):
        img = Image.new("RGB", (10, 10), color=(255, 255, 255))
        tensor = detector._preprocess(img)
        assert tensor.max() == pytest.approx(1.0)

    def test_imagem_preta_min_igual_a_0(self, detector):
        img = Image.new("RGB", (10, 10), color=(0, 0, 0))
        tensor = detector._preprocess(img)
        assert tensor.min() == pytest.approx(0.0)

    def test_aceita_imagem_rgba(self, detector):
        img = Image.new("RGBA", (100, 100), color=(100, 100, 100, 200))
        tensor = detector._preprocess(img)
        assert tensor.shape == (1, 3, 640, 640)

    def test_target_size_customizado(self, detector):
        img = Image.new("RGB", (200, 200))
        tensor = detector._preprocess(img, target_size=320)
        assert tensor.shape == (1, 3, 320, 320)


# ── Detector._postprocess ─────────────────────────────────────────────────


def _make_yolo_output(predictions: list[list[float]]) -> list[np.ndarray]:
    """
    Monta output no formato YOLOv8: [1, num_classes+4, num_anchors].
    Cada prediction é [x_c, y_c, w, h, score_class0, ..., score_classN].
    """
    arr = np.array(predictions, dtype=np.float32).T  # [features, anchors]
    return [arr[np.newaxis, ...]]                     # [1, features, anchors]


def _pred(class_id: int, confidence: float, num_classes: int = 8,
          x=320.0, y=320.0, w=100.0, h=100.0) -> list[float]:
    scores = [0.01] * num_classes
    scores[class_id] = confidence
    return [x, y, w, h] + scores


class TestDetectorPostprocess:
    def test_sem_deteccoes_quando_confianca_baixa(self, detector):
        pred = _pred(class_id=2, confidence=0.01)  # abaixo do threshold
        output = _make_yolo_output([pred])
        detections = detector._postprocess(output, orig_width=640, orig_height=640)
        assert detections == []

    def test_detecta_mobile_phone_alta_confianca(self, detector):
        # class_id=2 → mobile_phone, threshold padrão global=0.60
        pred = _pred(class_id=2, confidence=0.95)
        output = _make_yolo_output([pred])
        detections = detector._postprocess(output, orig_width=640, orig_height=640)
        assert len(detections) == 1
        assert detections[0].class_name == "mobile_phone"
        assert detections[0].confidence == pytest.approx(0.95)

    def test_detecta_laptop_com_threshold_de_classe(self, tmp_path):
        # class_id=3 → laptop; threshold customizado=0.80
        d = Detector(
            model_path=str(tmp_path / "naoexiste.onnx"),
            class_confidence_thresholds={"laptop": 0.80},
        )
        # Confiança 0.75 → abaixo do threshold customizado
        pred = _pred(class_id=3, confidence=0.75)
        output = _make_yolo_output([pred])
        assert d._postprocess(output, 640, 640) == []

        # Confiança 0.90 → acima do threshold customizado
        pred = _pred(class_id=3, confidence=0.90)
        output = _make_yolo_output([pred])
        detections = d._postprocess(output, 640, 640)
        assert len(detections) == 1
        assert detections[0].class_name == "laptop"

    def test_multiplas_deteccoes(self, detector):
        pred1 = _pred(class_id=2, confidence=0.95, x=100.0, y=100.0)
        pred2 = _pred(class_id=3, confidence=0.90, x=400.0, y=400.0)
        pred_low = _pred(class_id=5, confidence=0.10, x=320.0, y=320.0)
        output = _make_yolo_output([pred1, pred2, pred_low])
        detections = detector._postprocess(output, orig_width=640, orig_height=640)
        assert len(detections) == 2
        names = {d.class_name for d in detections}
        assert names == {"mobile_phone", "laptop"}

    def test_bbox_clampado_entre_0_e_1(self, detector):
        # bbox muito grande → coordenadas devem ser clampadas
        pred = _pred(class_id=3, confidence=0.99, x=10.0, y=10.0, w=900.0, h=900.0)
        output = _make_yolo_output([pred])
        detections = detector._postprocess(output, orig_width=640, orig_height=640)
        assert len(detections) == 1
        x1, y1, x2, y2 = detections[0].bbox
        assert x1 >= 0.0
        assert y1 >= 0.0
        assert x2 <= 1.0
        assert y2 <= 1.0

    def test_classe_desconhecida_retorna_class_n(self, detector):
        # class_id fora de HIXRAY_CLASSES → "class_N"
        num_classes = 12
        scores = [0.01] * num_classes
        scores[10] = 0.99
        pred = [320.0, 320.0, 50.0, 50.0] + scores
        output = _make_yolo_output([pred])
        detections = detector._postprocess(output, orig_width=640, orig_height=640)
        assert len(detections) == 1
        assert detections[0].class_name == "class_10"

    def test_bbox_normalizado_pela_dimensao_original(self, detector):
        # Imagem 1280x960; detecção centrada em (640, 480)
        pred = _pred(class_id=2, confidence=0.95, x=640.0, y=480.0, w=128.0, h=96.0)
        output = _make_yolo_output([pred])
        detections = detector._postprocess(output, orig_width=1280, orig_height=960)
        x1, y1, x2, y2 = detections[0].bbox
        assert x1 == pytest.approx(0.45)  # (640 - 64) / 1280
        assert y1 == pytest.approx(0.45)  # (480 - 48) / 960
        assert x2 == pytest.approx(0.55)  # (640 + 64) / 1280
        assert y2 == pytest.approx(0.55)  # (480 + 48) / 960


# ── Detector._load_model ───────────────────────────────────────────────────


class TestDetectorLoadModel:
    def test_load_model_configura_session_e_input_name(self, tmp_path):
        model_file = tmp_path / "fake.onnx"
        model_file.write_bytes(b"fake model content")

        mock_input = MagicMock()
        mock_input.name = "images"
        mock_session = MagicMock()
        mock_session.get_inputs.return_value = [mock_input]

        mock_ort = MagicMock()
        mock_ort.InferenceSession.return_value = mock_session

        with patch.dict("sys.modules", {"onnxruntime": mock_ort}):
            d = Detector.__new__(Detector)
            d.confidence_threshold = 0.60
            d.high_confidence_threshold = 0.85
            d.class_confidence_thresholds = {}
            d._session = None
            d._load_model(str(model_file))

        assert d._session is mock_session
        assert d._input_name == "images"
        mock_ort.InferenceSession.assert_called_once_with(
            str(model_file),
            providers=["CUDAExecutionProvider", "CPUExecutionProvider"],
        )
