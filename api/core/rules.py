from enum import Enum
from dataclasses import dataclass


class Decision(str, Enum):
    LIBERADO = "LIBERADO"
    VERIFICAR = "VERIFICAR"
    INCONCLUSIVO = "INCONCLUSIVO"


# Itens que nao precisam de verificacao
ALLOWED_ITEMS = {
    "key",
    "coin",
    "belt",
    "glasses",
    "pen",
    "watch",
    "jewelry",
    "wallet",
}

# Itens que exigem verificacao obrigatoria
RESTRICTED_ITEMS = {
    "mobile_phone",
    "tablet",
    "laptop",
    "portable_charger",   # powerbank
    "portable_charger_1", # powerbank flat (HiXray label)
    "portable_charger_2", # powerbank cylindrical (HiXray label)
    "kindle",
    "e_reader",
    "headphones",         # com bateria
}


@dataclass
class Detection:
    class_name: str
    confidence: float
    bbox: list[float]  # [x1, y1, x2, y2] normalized


def apply_rules(detections: list[Detection], confidence_threshold: float) -> tuple[Decision, list[Detection]]:
    """
    Aplica as regras de negocio sobre as deteccoes e retorna
    a decisao final e os itens que motivaram a decisao.
    """
    if not detections:
        return Decision.LIBERADO, []

    flagged = []

    for det in detections:
        if det.confidence < confidence_threshold:
            return Decision.INCONCLUSIVO, detections

        if det.class_name in RESTRICTED_ITEMS:
            flagged.append(det)

    if flagged:
        return Decision.VERIFICAR, flagged

    return Decision.LIBERADO, detections
