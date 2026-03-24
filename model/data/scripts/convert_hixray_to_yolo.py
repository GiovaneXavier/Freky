"""
Converte o dataset HiXray (formato TXT customizado) para YOLO format.

HiXray annotation format:
    image_name, category, x1, y1, x2, y2  (absoluto)

YOLO format (por imagem, arquivo .txt):
    class_id cx cy w h  (normalizado 0-1)

Usage:
    python convert_hixray_to_yolo.py \
        --hixray-dir /data/HiXray \
        --output-dir /data/hixray_yolo
"""
import argparse
import shutil
from pathlib import Path
from PIL import Image


HIXRAY_CLASSES = {
    "Portable_Charger1": 0,
    "Portable_Charger2": 1,
    "Mobile_Phone": 2,
    "Laptop": 3,
    "Tablet": 4,
    "Cosmetic": 5,
    "Water": 6,
    "Nonmetallic_Lighter": 7,
}


def convert(hixray_dir: Path, output_dir: Path):
    for split in ("train", "test"):
        ann_file = hixray_dir / "Annotation" / f"xray_{split}.txt"
        img_dir = hixray_dir / "image" / split

        if not ann_file.exists():
            print(f"[AVISO] Arquivo de anotacao nao encontrado: {ann_file}")
            continue

        out_img_dir = output_dir / split / "images"
        out_lbl_dir = output_dir / split / "labels"
        out_img_dir.mkdir(parents=True, exist_ok=True)
        out_lbl_dir.mkdir(parents=True, exist_ok=True)

        # Agrupa anotacoes por imagem
        annotations: dict[str, list] = {}
        with open(ann_file) as f:
            for line in f:
                parts = line.strip().split(",")
                if len(parts) < 6:
                    continue
                img_name, category, x1, y1, x2, y2 = parts[:6]
                if category not in HIXRAY_CLASSES:
                    continue
                annotations.setdefault(img_name.strip(), []).append(
                    (category.strip(), int(x1), int(y1), int(x2), int(y2))
                )

        for img_name, boxes in annotations.items():
            src_img = img_dir / img_name
            if not src_img.exists():
                continue

            with Image.open(src_img) as im:
                w, h = im.size

            yolo_lines = []
            for category, x1, y1, x2, y2 in boxes:
                cls_id = HIXRAY_CLASSES[category]
                cx = ((x1 + x2) / 2) / w
                cy = ((y1 + y2) / 2) / h
                bw = (x2 - x1) / w
                bh = (y2 - y1) / h
                yolo_lines.append(f"{cls_id} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}")

            shutil.copy(src_img, out_img_dir / img_name)
            (out_lbl_dir / src_img.with_suffix(".txt").name).write_text("\n".join(yolo_lines))

        print(f"[{split}] {len(annotations)} imagens convertidas")

    # Gera dataset.yaml para YOLOv8
    yaml_content = f"""path: {output_dir.resolve()}
train: train/images
val: test/images

nc: {len(HIXRAY_CLASSES)}
names: {list(HIXRAY_CLASSES.keys())}
"""
    (output_dir / "dataset.yaml").write_text(yaml_content)
    print(f"dataset.yaml salvo em {output_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--hixray-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("data/hixray_yolo"))
    args = parser.parse_args()
    convert(args.hixray_dir, args.output_dir)
