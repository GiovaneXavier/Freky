import numpy as np
from pathlib import Path
from PIL import Image

from core.rules import Detection, Decision, apply_rules


# Mapeamento de indices do modelo para nomes de classes (HiXray)
HIXRAY_CLASSES = {
    0: "portable_charger_1",
    1: "portable_charger_2",
    2: "mobile_phone",
    3: "laptop",
    4: "tablet",
    5: "cosmetic",
    6: "water",
    7: "nonmetallic_lighter",
}


class Detector:
    def __init__(
        self,
        model_path: str,
        confidence_threshold: float = 0.60,
        high_confidence_threshold: float = 0.85,
    ):
        self.confidence_threshold = confidence_threshold
        self.high_confidence_threshold = high_confidence_threshold
        self._session = None

        if Path(model_path).exists():
            self._load_model(model_path)

    def _load_model(self, model_path: str):
        import onnxruntime as ort

        providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
        self._session = ort.InferenceSession(model_path, providers=providers)
        self._input_name = self._session.get_inputs()[0].name

    def _preprocess(self, image: Image.Image, target_size: int = 640) -> np.ndarray:
        img = image.convert("RGB").resize((target_size, target_size))
        arr = np.array(img, dtype=np.float32) / 255.0
        arr = arr.transpose(2, 0, 1)  # HWC -> CHW
        return arr[np.newaxis, ...]   # add batch dim

    def _postprocess(
        self,
        outputs: np.ndarray,
        orig_width: int,
        orig_height: int,
    ) -> list[Detection]:
        detections = []
        # YOLOv8 output shape: [1, num_classes+4, num_anchors]
        predictions = outputs[0][0].T  # [num_anchors, num_classes+4]

        for pred in predictions:
            x_c, y_c, w, h = pred[:4]
            class_scores = pred[4:]
            class_id = int(np.argmax(class_scores))
            confidence = float(class_scores[class_id])

            if confidence < self.confidence_threshold:
                continue

            class_name = HIXRAY_CLASSES.get(class_id, f"class_{class_id}")

            # Normalizar coordenadas para [0,1]
            x1 = (x_c - w / 2) / orig_width
            y1 = (y_c - h / 2) / orig_height
            x2 = (x_c + w / 2) / orig_width
            y2 = (y_c + h / 2) / orig_height

            detections.append(Detection(
                class_name=class_name,
                confidence=confidence,
                bbox=[
                    max(0.0, x1), max(0.0, y1),
                    min(1.0, x2), min(1.0, y2),
                ],
            ))

        return detections

    def predict(self, image_path: str) -> tuple[Decision, list[Detection]]:
        if self._session is None:
            # Modo sem modelo (desenvolvimento)
            return Decision.INCONCLUSIVO, []

        image = Image.open(image_path)
        orig_w, orig_h = image.size

        input_tensor = self._preprocess(image)
        outputs = self._session.run(None, {self._input_name: input_tensor})
        detections = self._postprocess(outputs, orig_w, orig_h)

        return apply_rules(detections, self.confidence_threshold)
