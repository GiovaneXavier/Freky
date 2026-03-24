#!/usr/bin/env python3
"""
Validação end-to-end do pipeline de inferência do Freky.

Uso:
    # Com modelo real e imagem real:
    python scripts/validate_pipeline.py --model model/weights/freky.onnx --image scan.jpg

    # Modo sintético (sem modelo, gera imagem de teste automaticamente):
    python scripts/validate_pipeline.py --synthetic

    # Pasta com múltiplas imagens:
    python scripts/validate_pipeline.py --model model/weights/freky.onnx --dir scans/

    # Ajustar threshold global:
    python scripts/validate_pipeline.py --model model/weights/freky.onnx --image scan.jpg --conf 0.50
"""

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

# Garante import dos módulos da api/ quando rodado da raiz do projeto
sys.path.insert(0, str(Path(__file__).parent.parent / "api"))

from core.detector import Detector, HIXRAY_CLASSES
from core.rules import Decision


# Thresholds por classe (espelha settings.py para uso standalone)
DEFAULT_CLASS_THRESHOLDS: dict[str, float] = {
    "portable_charger_1": 0.55,
    "portable_charger_2": 0.55,
    "mobile_phone": 0.50,
    "laptop": 0.65,
    "tablet": 0.60,
    "cosmetic": 0.75,
    "water": 0.70,
    "nonmetallic_lighter": 0.55,
}

DECISION_COLORS = {
    Decision.LIBERADO: "\033[92m",      # verde
    Decision.VERIFICAR: "\033[91m",     # vermelho
    Decision.INCONCLUSIVO: "\033[93m",  # amarelo
}
RESET = "\033[0m"


def create_synthetic_image(tmp_path: Path) -> Path:
    """Gera imagem sintética em tons de cinza simulando X-Ray."""
    img = Image.new("RGB", (640, 512), color=(20, 20, 20))
    draw = ImageDraw.Draw(img)

    # Simula fundo de bagagem
    draw.rectangle([50, 50, 590, 460], fill=(35, 35, 35), outline=(60, 60, 60))

    # Simula objeto retangular (laptop-like)
    draw.rectangle([100, 100, 380, 250], fill=(80, 120, 90), outline=(120, 180, 130))
    draw.rectangle([110, 110, 370, 240], fill=(60, 100, 70))

    # Simula objeto pequeno (phone-like)
    draw.rectangle([420, 150, 510, 320], fill=(90, 100, 140), outline=(130, 145, 200))

    # Adiciona ruído
    arr = np.array(img, dtype=np.uint8)
    noise = np.random.randint(-8, 8, arr.shape, dtype=np.int16)
    arr = np.clip(arr.astype(np.int16) + noise, 0, 255).astype(np.uint8)

    out = tmp_path / "synthetic_scan.jpg"
    Image.fromarray(arr).save(out, quality=95)
    return out


def validate_image(
    detector: Detector,
    image_path: Path,
    verbose: bool = False,
) -> dict:
    t0 = time.perf_counter()
    decision, detections = detector.predict(str(image_path))
    elapsed_ms = (time.perf_counter() - t0) * 1000

    color = DECISION_COLORS.get(decision, "")
    print(f"\n{'─' * 60}")
    print(f"  Arquivo : {image_path.name}")
    print(f"  Decisão : {color}{decision.value}{RESET}")
    print(f"  Tempo   : {elapsed_ms:.1f} ms")
    print(f"  Itens   : {len(detections)}")

    if detections:
        print()
        for d in detections:
            print(f"    • {d.class_name:<25} conf={d.confidence:.3f}  bbox={[round(v,3) for v in d.bbox]}")

    if verbose and not detections:
        print("    (nenhuma detecção acima do threshold)")

    return {
        "file": image_path.name,
        "decision": decision.value,
        "elapsed_ms": round(elapsed_ms, 1),
        "detections": [
            {
                "class": d.class_name,
                "confidence": round(d.confidence, 4),
                "bbox": [round(v, 4) for v in d.bbox],
            }
            for d in detections
        ],
    }


def validate_thresholds(detector: Detector) -> None:
    """Exibe tabela de thresholds efetivos por classe."""
    print("\n  Thresholds efetivos por classe:")
    print(f"  {'Classe':<28} {'Threshold':>10}")
    print(f"  {'─' * 28} {'─' * 10}")
    for class_name in HIXRAY_CLASSES.values():
        threshold = detector.class_confidence_thresholds.get(
            class_name, detector.confidence_threshold
        )
        marker = " ← custom" if class_name in detector.class_confidence_thresholds else ""
        print(f"  {class_name:<28} {threshold:>10.2f}{marker}")
    print(f"  {'─' * 28} {'─' * 10}")
    print(f"  {'(global fallback)':<28} {detector.confidence_threshold:>10.2f}")


def main():
    parser = argparse.ArgumentParser(description="Valida pipeline de inferência do Freky")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--image", type=Path, help="Caminho para imagem única")
    group.add_argument("--dir", type=Path, help="Pasta com imagens (.jpg/.jpeg/.tif/.tiff)")
    group.add_argument("--synthetic", action="store_true", help="Usa imagem sintética de teste")

    parser.add_argument("--model", type=Path, default=None, help="Caminho para freky.onnx")
    parser.add_argument("--conf", type=float, default=0.60, help="Threshold global (padrão: 0.60)")
    parser.add_argument("--output", type=Path, default=None, help="Salva resultados em JSON")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    # Detector
    model_path = str(args.model) if args.model else "/app/model/weights/freky.onnx"
    detector = Detector(
        model_path=model_path,
        confidence_threshold=args.conf,
        class_confidence_thresholds=DEFAULT_CLASS_THRESHOLDS,
    )

    print("\n=== Freky — Validação do Pipeline ===")
    if detector._session is None:
        print("  [AVISO] Modelo ONNX não encontrado — rodando em modo sem modelo.")
        print("          As decisões retornarão INCONCLUSIVO até o modelo ser carregado.")
    else:
        print(f"  Modelo  : {model_path}")

    validate_thresholds(detector)

    # Coleta imagens
    images: list[Path] = []
    tmp_dir = None

    if args.synthetic:
        import tempfile
        tmp_dir = Path(tempfile.mkdtemp())
        images.append(create_synthetic_image(tmp_dir))
        print(f"\n  Imagem sintética gerada em: {images[0]}")
    elif args.image:
        if not args.image.exists():
            print(f"\n[ERRO] Arquivo não encontrado: {args.image}", file=sys.stderr)
            sys.exit(1)
        images.append(args.image)
    else:
        exts = {".jpg", ".jpeg", ".tif", ".tiff"}
        images = sorted(p for p in args.dir.iterdir() if p.suffix.lower() in exts)
        if not images:
            print(f"\n[ERRO] Nenhuma imagem encontrada em: {args.dir}", file=sys.stderr)
            sys.exit(1)
        print(f"\n  {len(images)} imagem(ns) encontrada(s) em {args.dir}")

    # Executa validação
    results = []
    for img_path in images:
        results.append(validate_image(detector, img_path, verbose=args.verbose))

    # Resumo
    counts = {d.value: 0 for d in Decision}
    for r in results:
        counts[r["decision"]] += 1

    print(f"\n{'═' * 60}")
    print("  RESUMO")
    print(f"  Total : {len(results)} imagem(ns)")
    for decision, count in counts.items():
        if count:
            color = DECISION_COLORS.get(Decision(decision), "")
            print(f"  {color}{decision:<15}{RESET}: {count}")

    total_ms = sum(r["elapsed_ms"] for r in results)
    avg_ms = total_ms / len(results) if results else 0
    print(f"  Tempo médio : {avg_ms:.1f} ms/imagem")
    print(f"{'═' * 60}\n")

    # JSON opcional
    if args.output:
        args.output.write_text(json.dumps(results, indent=2, ensure_ascii=False))
        print(f"  Resultados salvos em: {args.output}\n")

    # Cleanup
    if tmp_dir:
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)

    # Código de saída: 1 se algum resultado for VERIFICAR
    has_alert = any(r["decision"] == Decision.VERIFICAR.value for r in results)
    sys.exit(1 if has_alert else 0)


if __name__ == "__main__":
    main()
