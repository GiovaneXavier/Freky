import pytest
from core.rules import apply_rules, Decision, Detection, RESTRICTED_ITEMS


def det(class_name: str, confidence: float = 0.90) -> Detection:
    return Detection(class_name=class_name, confidence=confidence, bbox=[0.1, 0.1, 0.5, 0.5])


THRESHOLD = 0.60


class TestApplyRules:
    def test_sem_deteccoes_retorna_liberado(self):
        decision, flagged = apply_rules([], THRESHOLD)
        assert decision == Decision.LIBERADO
        assert flagged == []

    def test_item_permitido_retorna_liberado(self):
        decision, _ = apply_rules([det("key"), det("coin")], THRESHOLD)
        assert decision == Decision.LIBERADO

    def test_item_restrito_retorna_verificar(self):
        for item in RESTRICTED_ITEMS:
            decision, flagged = apply_rules([det(item)], THRESHOLD)
            assert decision == Decision.VERIFICAR, f"Esperava VERIFICAR para {item}"
            assert len(flagged) == 1

    def test_multiplos_restritos_retorna_verificar(self):
        detections = [det("mobile_phone"), det("tablet"), det("key")]
        decision, flagged = apply_rules(detections, THRESHOLD)
        assert decision == Decision.VERIFICAR
        assert len(flagged) == 2  # apenas os restritos

    def test_baixa_confianca_retorna_inconclusivo(self):
        decision, _ = apply_rules([det("mobile_phone", confidence=0.45)], THRESHOLD)
        assert decision == Decision.INCONCLUSIVO

    def test_confianca_exatamente_no_limiar_passa(self):
        decision, _ = apply_rules([det("key", confidence=THRESHOLD)], THRESHOLD)
        assert decision == Decision.LIBERADO

    def test_confianca_abaixo_do_limiar_inconclusivo(self):
        decision, _ = apply_rules([det("key", confidence=THRESHOLD - 0.01)], THRESHOLD)
        assert decision == Decision.INCONCLUSIVO

    def test_item_restrito_com_confianca_baixa_inconclusivo(self):
        # Mesmo sendo item restrito, se confianca e baixa o resultado e INCONCLUSIVO
        decision, _ = apply_rules([det("laptop", confidence=0.30)], THRESHOLD)
        assert decision == Decision.INCONCLUSIVO
