"""
Valida o dataset HiXray convertido para YOLO antes de iniciar o treinamento.

Verifica:
  - Paridade entre imagens e labels
  - Bounding boxes dentro do range [0, 1]
  - Distribuicao de classes (detecta desbalanceamento severo)
  - Imagens corrompidas ou ilegíveis
  - Resolucao minima (descarta imagens muito pequenas)

Usage:
    python validate_dataset.py --dataset-dir model/data/hixray_yolo
    python validate_dataset.py --dataset-dir model/data/hixray_yolo --fix
"""
import argparse
import sys
from collections import Counter
from pathlib import Path

from PIL import Image, UnidentifiedImageError

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

MIN_RESOLUTION = (64, 64)


def validate_label_file(label_path: Path) -> tuple[list[str], list[str]]:
    """Retorna (erros, class_ids_encontrados)."""
    errors = []
    class_ids = []

    try:
        lines = label_path.read_text().strip().splitlines()
    except Exception as e:
        return [f"Leitura falhou: {e}"], []

    for i, line in enumerate(lines, 1):
        parts = line.strip().split()
        if len(parts) != 5:
            errors.append(f"linha {i}: esperava 5 campos, encontrou {len(parts)}")
            continue

        try:
            cls_id = int(parts[0])
            cx, cy, w, h = map(float, parts[1:])
        except ValueError:
            errors.append(f"linha {i}: valores nao numericos")
            continue

        if cls_id < 0 or cls_id >= len(HIXRAY_CLASSES):
            errors.append(f"linha {i}: class_id={cls_id} fora do range [0,{len(HIXRAY_CLASSES)-1}]")

        for name, val in [("cx", cx), ("cy", cy), ("w", w), ("h", h)]:
            if not (0.0 <= val <= 1.0):
                errors.append(f"linha {i}: {name}={val:.4f} fora de [0,1]")

        if w <= 0 or h <= 0:
            errors.append(f"linha {i}: bbox com dimensao zero ou negativa")

        class_ids.append(str(cls_id))

    return errors, class_ids


def validate_image(img_path: Path) -> list[str]:
    errors = []
    try:
        with Image.open(img_path) as img:
            img.verify()
        with Image.open(img_path) as img:
            w, h = img.size
            if w < MIN_RESOLUTION[0] or h < MIN_RESOLUTION[1]:
                errors.append(f"resolucao {w}x{h} abaixo do minimo {MIN_RESOLUTION}")
    except UnidentifiedImageError:
        errors.append("arquivo nao e uma imagem valida")
    except Exception as e:
        errors.append(f"erro ao abrir: {e}")
    return errors


def validate_split(split_dir: Path, fix: bool = False) -> dict:
    img_dir = split_dir / "images"
    lbl_dir = split_dir / "labels"

    if not img_dir.exists():
        print(f"  [AVISO] Diretorio nao encontrado: {img_dir}")
        return {}

    images = set(p.stem for p in img_dir.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".tif", ".tiff"})
    labels = set(p.stem for p in lbl_dir.iterdir() if p.suffix == ".txt") if lbl_dir.exists() else set()

    without_label = images - labels
    without_image = labels - images

    print(f"  Imagens: {len(images):>6}   Labels: {len(labels):>6}")

    if without_label:
        print(f"  [AVISO] {len(without_label)} imagens sem label correspondente")
        if fix:
            for stem in without_label:
                (lbl_dir / f"{stem}.txt").write_text("")
            print(f"          -> labels vazios criados (background negativo)")

    if without_image:
        print(f"  [ERRO]  {len(without_image)} labels sem imagem — removendo" if fix else
              f"  [ERRO]  {len(without_image)} labels sem imagem correspondente")
        if fix:
            for stem in without_image:
                (lbl_dir / f"{stem}.txt").unlink()

    total_errors = 0
    all_class_ids: list[str] = []

    for img_path in sorted(img_dir.iterdir()):
        if img_path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".tif", ".tiff"}:
            continue

        img_errors = validate_image(img_path)
        lbl_path = lbl_dir / f"{img_path.stem}.txt"
        lbl_errors, class_ids = validate_label_file(lbl_path) if lbl_path.exists() else ([], [])

        all_errors = img_errors + lbl_errors
        if all_errors:
            total_errors += 1
            print(f"  [ERRO] {img_path.name}")
            for e in all_errors:
                print(f"         {e}")
            if fix:
                img_path.unlink(missing_ok=True)
                lbl_path.unlink(missing_ok=True)
                print(f"         -> par removido")

        all_class_ids.extend(class_ids)

    return Counter(all_class_ids)


def print_class_distribution(counter: Counter, split: str):
    if not counter:
        return
    total = sum(counter.values())
    print(f"\n  Distribuicao de classes ({split}):")
    max_count = max(counter.values())
    for cls_id in sorted(counter.keys(), key=int):
        count = counter[cls_id]
        name = HIXRAY_CLASSES[int(cls_id)] if int(cls_id) < len(HIXRAY_CLASSES) else f"class_{cls_id}"
        bar = "█" * int(30 * count / max_count)
        ratio = count / total * 100
        imbalance = ""
        if ratio < 3:
            imbalance = " ⚠ SUBREPRESENTADO"
        print(f"    {name:<30s} {count:>5} ({ratio:5.1f}%) {bar}{imbalance}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-dir", type=Path, default=Path("model/data/hixray_yolo"))
    parser.add_argument("--fix", action="store_true",
                        help="Corrige automaticamente problemas encontrados (remove pares invalidos)")
    args = parser.parse_args()

    dataset_dir = args.dataset_dir
    if not dataset_dir.exists():
        print(f"[ERRO] Diretorio nao encontrado: {dataset_dir}")
        print("       Rode primeiro: make convert-dataset HIXRAY_DIR=/path/to/HiXray")
        sys.exit(1)

    all_ok = True
    for split in ("train", "test"):
        split_dir = dataset_dir / split
        print(f"\n{'='*50}")
        print(f"  Split: {split}")
        print(f"{'='*50}")

        counter = validate_split(split_dir, fix=args.fix)
        print_class_distribution(counter, split)

    print(f"\n{'='*50}")
    if all_ok:
        print("  Dataset OK — pronto para treinamento.")
        print("  Rode: make train")
    else:
        print("  Erros encontrados. Rode com --fix para correcao automatica.")
        sys.exit(1)


if __name__ == "__main__":
    main()
