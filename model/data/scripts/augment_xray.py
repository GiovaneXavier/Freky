"""
Pipeline de augmentacao especifico para imagens de raio-X bagagem.

Principios aplicados:
  - SEM flip horizontal/vertical: objetos de raio-X tem orientacao semantica
    (ex: powerbank de cabeca para baixo ainda e powerbank, mas nao invertemos
     para nao confundir o modelo com orientacoes nao realistas)
  - SIM rotacao leve: bagagens chegam em angulos variados na esteira
  - SIM brilho/contraste: simula variacoes de kV/mA do scanner
  - SIM ruido gaussiano: simula diferentes tempos de exposicao
  - SIM zoom/crop: simula diferentes distancias dos objetos ao detector
  - SIM RandomShadow: simula sobreposicao de outros objetos (efeito real em raio-X)
  - NAO saturacao/hue: raio-X usa cor como canal semantico (nao pode alterar)

Uso standalone (gera dataset aumentado em disco):
    python augment_xray.py \
        --input-dir model/data/hixray_yolo/train \
        --output-dir model/data/hixray_augmented/train \
        --factor 3
"""
import argparse
import random
import shutil
from pathlib import Path

import cv2
import numpy as np
from PIL import Image


def get_augmentation_pipeline(severity: str = "medium"):
    """
    Retorna uma funcao de augmentacao.
    severity: 'light' | 'medium' | 'heavy'
    """
    try:
        import albumentations as A
    except ImportError:
        raise ImportError("Instale albumentations: pip install albumentations")

    if severity == "light":
        transforms = [
            A.RandomBrightnessContrast(brightness_limit=0.1, contrast_limit=0.1, p=0.5),
            A.GaussNoise(var_limit=(5, 20), p=0.3),
            A.Rotate(limit=5, p=0.4),
        ]
    elif severity == "heavy":
        transforms = [
            A.RandomBrightnessContrast(brightness_limit=0.3, contrast_limit=0.3, p=0.8),
            A.GaussNoise(var_limit=(10, 50), p=0.5),
            A.Rotate(limit=15, p=0.6),
            A.RandomScale(scale_limit=0.2, p=0.5),
            A.Blur(blur_limit=3, p=0.3),
            A.CLAHE(clip_limit=4.0, p=0.4),
            A.RandomGamma(gamma_limit=(80, 120), p=0.4),
        ]
    else:  # medium (padrao para treinamento)
        transforms = [
            A.RandomBrightnessContrast(brightness_limit=0.2, contrast_limit=0.2, p=0.7),
            A.GaussNoise(var_limit=(5, 30), p=0.4),
            A.Rotate(limit=10, p=0.5),
            A.RandomScale(scale_limit=0.1, p=0.4),
            A.Blur(blur_limit=3, p=0.2),
            A.CLAHE(clip_limit=3.0, p=0.3),
            A.RandomGamma(gamma_limit=(85, 115), p=0.3),
        ]

    return A.Compose(
        transforms,
        bbox_params=A.BboxParams(
            format="yolo",
            label_fields=["class_labels"],
            min_visibility=0.3,
        ),
    )


def read_yolo_labels(label_path: Path) -> tuple[list[int], list[list[float]]]:
    """Retorna (class_ids, bboxes) onde bbox = [cx, cy, w, h] normalizado."""
    if not label_path.exists():
        return [], []

    class_ids, bboxes = [], []
    for line in label_path.read_text().strip().splitlines():
        parts = line.strip().split()
        if len(parts) == 5:
            class_ids.append(int(parts[0]))
            bboxes.append([float(x) for x in parts[1:]])
    return class_ids, bboxes


def write_yolo_labels(label_path: Path, class_ids: list[int], bboxes: list):
    lines = [f"{cls} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}"
             for cls, (cx, cy, w, h) in zip(class_ids, bboxes)]
    label_path.write_text("\n".join(lines))


def augment_dataset(input_dir: Path, output_dir: Path, factor: int, severity: str):
    img_in = input_dir / "images"
    lbl_in = input_dir / "labels"
    img_out = output_dir / "images"
    lbl_out = output_dir / "labels"

    img_out.mkdir(parents=True, exist_ok=True)
    lbl_out.mkdir(parents=True, exist_ok=True)

    pipeline = get_augmentation_pipeline(severity)

    images = sorted(img_in.glob("*"))
    print(f"Augmentando {len(images)} imagens com fator {factor}x ({severity})...")

    copied = 0
    generated = 0

    for img_path in images:
        if img_path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".tif", ".tiff"}:
            continue

        lbl_path = lbl_in / f"{img_path.stem}.txt"
        class_ids, bboxes = read_yolo_labels(lbl_path)

        # Copia original sem alteracao
        shutil.copy(img_path, img_out / img_path.name)
        shutil.copy(lbl_path, lbl_out / lbl_path.name) if lbl_path.exists() else \
            (lbl_out / f"{img_path.stem}.txt").write_text("")
        copied += 1

        # Gera versoes aumentadas
        img_np = np.array(Image.open(img_path).convert("RGB"))

        for i in range(factor - 1):
            try:
                result = pipeline(
                    image=img_np,
                    bboxes=bboxes if bboxes else [],
                    class_labels=class_ids if class_ids else [],
                )
            except Exception:
                continue

            aug_name = f"{img_path.stem}_aug{i:02d}{img_path.suffix}"
            Image.fromarray(result["image"]).save(img_out / aug_name, quality=90)
            write_yolo_labels(
                lbl_out / f"{img_path.stem}_aug{i:02d}.txt",
                result["class_labels"],
                result["bboxes"],
            )
            generated += 1

    total = copied + generated
    print(f"Pronto: {copied} originais + {generated} aumentadas = {total} total")
    print(f"Salvo em: {output_dir}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, required=True,
                        help="Diretorio do split (ex: model/data/hixray_yolo/train)")
    parser.add_argument("--output-dir", type=Path, required=True,
                        help="Destino do dataset aumentado")
    parser.add_argument("--factor", type=int, default=3,
                        help="Multiplicador do dataset (3 = 2 augmentadas por original)")
    parser.add_argument("--severity", choices=["light", "medium", "heavy"], default="medium")
    args = parser.parse_args()

    augment_dataset(args.input_dir, args.output_dir, args.factor, args.severity)


if __name__ == "__main__":
    main()
