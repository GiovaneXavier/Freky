"""
Exporta o modelo treinado (.pt) para ONNX para deploy em producao.

Usage:
    python export_onnx.py --weights runs/freky/weights/best.pt
"""
import argparse
from pathlib import Path
from ultralytics import YOLO


def export(weights: Path, output_dir: Path):
    model = YOLO(str(weights))
    exported = model.export(
        format="onnx",
        imgsz=640,
        dynamic=False,
        simplify=True,
        opset=17,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    dest = output_dir / "freky.onnx"
    Path(exported).rename(dest)
    print(f"Modelo exportado: {dest}")
    print(f"Tamanho: {dest.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--weights", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("../weights"))
    args = parser.parse_args()
    export(args.weights, args.output_dir)
