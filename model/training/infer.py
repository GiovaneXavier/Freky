"""
Inferencia rapida para validacao visual do modelo treinado.

Processa uma imagem ou pasta inteira e grava o resultado anotado em disco.
Util para validar visualmente se o modelo esta detectando corretamente
antes de subir o ONNX para producao.

Usage:
    # Imagem unica
    python infer.py --weights model/runs/freky-v1/weights/best.pt \
                    --source scans/incoming/scan_001.jpg

    # Pasta inteira
    python infer.py --weights model/runs/freky-v1/weights/best.pt \
                    --source scans/incoming/ \
                    --output-dir scans/annotated/

    # Com threshold customizado
    python infer.py --weights model/runs/freky-v1/weights/best.pt \
                    --source scans/incoming/ \
                    --conf 0.5 --show-conf
"""
import argparse
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HIXRAY_CLASSES = [
    "portable_charger_1",
    "portable_charger_2",
    "mobile_phone",
    "laptop",
    "tablet",
    "cosmetic",
    "water",
    "nonmetallic_lighter",
]

RESTRICTED = {"portable_charger_1", "portable_charger_2", "mobile_phone", "laptop", "tablet"}

# Cor por classe: vermelho para restritos, verde para permitidos
CLASS_COLORS = {
    cls: (220, 50, 50) if cls in RESTRICTED else (50, 200, 50)
    for cls in HIXRAY_CLASSES
}

LABEL_PT = {
    "portable_charger_1": "Powerbank",
    "portable_charger_2": "Powerbank",
    "mobile_phone": "Celular",
    "laptop": "Notebook",
    "tablet": "Tablet",
    "cosmetic": "Cosmetico",
    "water": "Agua",
    "nonmetallic_lighter": "Isqueiro",
}


def draw_detections(image: Image.Image, results) -> Image.Image:
    draw = ImageDraw.Draw(image)
    w, h = image.size

    for box in results[0].boxes:
        cls_id = int(box.cls[0])
        conf = float(box.conf[0])
        x1, y1, x2, y2 = [float(v) for v in box.xyxy[0]]

        cls_name = HIXRAY_CLASSES[cls_id] if cls_id < len(HIXRAY_CLASSES) else f"class_{cls_id}"
        color = CLASS_COLORS.get(cls_name, (200, 200, 50))
        label = f"{LABEL_PT.get(cls_name, cls_name)} {conf:.0%}"

        # Caixa
        lw = max(2, int(min(w, h) / 200))
        draw.rectangle([x1, y1, x2, y2], outline=color, width=lw)

        # Label background
        text_h = 16
        draw.rectangle([x1, y1 - text_h - 2, x1 + len(label) * 7 + 4, y1], fill=color)
        draw.text((x1 + 2, y1 - text_h), label, fill=(255, 255, 255))

    return image


def get_decision_banner(decision: str) -> tuple[tuple[int, int, int], str]:
    if decision == "LIBERADO":
        return (30, 160, 30), "LIBERADO"
    elif decision == "VERIFICAR":
        return (200, 30, 30), "VERIFICAR"
    return (180, 140, 0), "INCONCLUSIVO"


def process_image(model, img_path: Path, output_dir: Path, conf: float) -> dict:
    from ultralytics import YOLO
    from core.rules import apply_rules, Detection

    results = model(str(img_path), conf=conf, verbose=False)

    # Monta detections para regras
    detections = []
    for box in results[0].boxes:
        cls_id = int(box.cls[0])
        confidence = float(box.conf[0])
        cls_name = HIXRAY_CLASSES[cls_id] if cls_id < len(HIXRAY_CLASSES) else f"class_{cls_id}"
        detections.append(Detection(
            class_name=cls_name,
            confidence=confidence,
            bbox=[float(v) for v in box.xyxyn[0]],
        ))

    decision, flagged = apply_rules(detections, conf)

    # Imagem anotada
    image = Image.open(img_path).convert("RGB")
    image = draw_detections(image, results)

    # Banner de decisao na parte inferior
    banner_h = 40
    banner = Image.new("RGB", (image.width, banner_h), get_decision_banner(decision.value)[0])
    draw = ImageDraw.Draw(banner)
    text = get_decision_banner(decision.value)[1]
    draw.text((image.width // 2 - len(text) * 6, 10), text, fill=(255, 255, 255))

    final = Image.new("RGB", (image.width, image.height + banner_h))
    final.paste(image, (0, 0))
    final.paste(banner, (0, image.height))

    out_path = output_dir / f"annotated_{img_path.name}"
    final.save(out_path)

    return {
        "file": img_path.name,
        "decision": decision.value,
        "detections": len(detections),
        "output": out_path,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--weights", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True,
                        help="Imagem ou pasta de imagens")
    parser.add_argument("--output-dir", type=Path, default=Path("scans/annotated"))
    parser.add_argument("--conf", type=float, default=0.60)
    args = parser.parse_args()

    from ultralytics import YOLO
    model = YOLO(str(args.weights))

    args.output_dir.mkdir(parents=True, exist_ok=True)
    exts = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}

    sources = (
        [args.source]
        if args.source.is_file()
        else sorted(p for p in args.source.iterdir() if p.suffix.lower() in exts)
    )

    if not sources:
        print(f"Nenhuma imagem encontrada em {args.source}")
        return

    print(f"\nProcessando {len(sources)} imagem(ns)...")
    stats = {"LIBERADO": 0, "VERIFICAR": 0, "INCONCLUSIVO": 0}

    for img_path in sources:
        result = process_image(model, img_path, args.output_dir, args.conf)
        stats[result["decision"]] += 1
        icon = {"LIBERADO": "✓", "VERIFICAR": "!", "INCONCLUSIVO": "?"}.get(result["decision"], "?")
        print(f"  [{icon}] {result['file']:<40s} {result['decision']}  ({result['detections']} det.)")

    total = len(sources)
    print(f"\n{'='*50}")
    print(f"  Total: {total}")
    print(f"  LIBERADO:     {stats['LIBERADO']:>4}  ({stats['LIBERADO']/total*100:.0f}%)")
    print(f"  VERIFICAR:    {stats['VERIFICAR']:>4}  ({stats['VERIFICAR']/total*100:.0f}%)")
    print(f"  INCONCLUSIVO: {stats['INCONCLUSIVO']:>4}  ({stats['INCONCLUSIVO']/total*100:.0f}%)")
    print(f"\nImagens anotadas em: {args.output_dir}")


if __name__ == "__main__":
    main()
