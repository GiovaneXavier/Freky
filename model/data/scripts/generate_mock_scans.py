"""
Gerador de imagens de raio-X sinteticas para testar o pipeline
sem precisar do dataset HiXray.

Cria imagens PNG com retangulos coloridos simulando objetos
e gera anotacoes YOLO correspondentes.

Usage:
    python generate_mock_scans.py --count 100 --output-dir /scans/incoming
    python generate_mock_scans.py --count 50 --output-dir data/mock --with-labels
"""
import argparse
import random
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

# Paleta de cores por categoria (aproxima cores de raio-X)
ITEM_STYLES = {
    "mobile_phone":       {"color": (255, 140, 0),   "w": (0.08, 0.14), "h": (0.15, 0.22)},
    "tablet":             {"color": (255, 80, 0),    "w": (0.14, 0.22), "h": (0.20, 0.30)},
    "laptop":             {"color": (200, 60, 0),    "w": (0.25, 0.40), "h": (0.18, 0.26)},
    "portable_charger_1": {"color": (80, 180, 80),   "w": (0.07, 0.12), "h": (0.10, 0.16)},
    "portable_charger_2": {"color": (60, 160, 60),   "w": (0.04, 0.07), "h": (0.14, 0.20)},
    "key":                {"color": (180, 180, 255),  "w": (0.03, 0.06), "h": (0.05, 0.10)},
    "wallet":             {"color": (150, 100, 50),   "w": (0.07, 0.12), "h": (0.05, 0.09)},
}

CLASS_IDS = {
    "portable_charger_1": 0,
    "portable_charger_2": 1,
    "mobile_phone": 2,
    "laptop": 3,
    "tablet": 4,
    "key": 5,
    "wallet": 6,
}

IMG_W, IMG_H = 640, 480


def make_xray_background() -> Image.Image:
    """Fundo cinza escuro com ruido, simulando a esteira do scanner."""
    noise = np.random.randint(10, 40, (IMG_H, IMG_W, 3), dtype=np.uint8)
    img = Image.fromarray(noise, "RGB")
    return img.filter(ImageFilter.GaussianBlur(radius=1))


def draw_item(draw: ImageDraw.ImageDraw, category: str) -> tuple[float, float, float, float]:
    """Desenha um item e retorna bbox normalizada (cx, cy, w, h)."""
    style = ITEM_STYLES[category]
    bw = random.uniform(*style["w"])
    bh = random.uniform(*style["h"])
    cx = random.uniform(bw / 2 + 0.05, 1 - bw / 2 - 0.05)
    cy = random.uniform(bh / 2 + 0.05, 1 - bh / 2 - 0.05)

    x1 = int((cx - bw / 2) * IMG_W)
    y1 = int((cy - bh / 2) * IMG_H)
    x2 = int((cx + bw / 2) * IMG_W)
    y2 = int((cy + bh / 2) * IMG_H)

    # Corpo do item com alpha simulando transparencia de raio-X
    color = style["color"]
    alpha_color = tuple(int(c * 0.7) for c in color)
    draw.rectangle([x1, y1, x2, y2], fill=alpha_color, outline=color, width=2)

    return cx, cy, bw, bh


def generate_scan(output_dir: Path, idx: int, with_labels: bool = False):
    img = make_xray_background()
    draw = ImageDraw.Draw(img)

    categories = list(ITEM_STYLES.keys())
    num_items = random.randint(0, 3)
    chosen = random.sample(categories, min(num_items, len(categories)))

    yolo_lines = []
    for category in chosen:
        cx, cy, bw, bh = draw_item(draw, category)
        cls_id = CLASS_IDS.get(category, 5)
        yolo_lines.append(f"{cls_id} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}")

    filename = f"mock_{idx:05d}.jpg"
    img_path = output_dir / filename
    img.save(img_path, "JPEG", quality=85)

    if with_labels:
        label_dir = output_dir.parent / "labels"
        label_dir.mkdir(exist_ok=True)
        (label_dir / f"mock_{idx:05d}.txt").write_text("\n".join(yolo_lines))

    return filename, [c for c in chosen]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=20)
    parser.add_argument("--output-dir", type=Path, default=Path("/scans/incoming"))
    parser.add_argument("--with-labels", action="store_true",
                        help="Gera arquivos .txt no formato YOLO junto com as imagens")
    parser.add_argument("--interval", type=float, default=0.0,
                        help="Intervalo entre arquivos em segundos (simula chegada do Xport)")
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Gerando {args.count} scans em {args.output_dir}...")

    for i in range(args.count):
        filename, items = generate_scan(args.output_dir, i, with_labels=args.with_labels)
        label = ", ".join(items) if items else "vazio"
        print(f"  [{i+1:4d}/{args.count}] {filename} — {label}")
        if args.interval > 0:
            time.sleep(args.interval)

    print("Pronto.")


if __name__ == "__main__":
    main()
