"""
Fine-tuning do YOLOv8 no dataset HiXray.

Usage:
    python train.py --data /data/hixray_yolo/dataset.yaml --epochs 50
"""
import argparse
from pathlib import Path
from ultralytics import YOLO


def train(data: str, epochs: int, model_size: str, output_dir: Path):
    model = YOLO(f"yolov8{model_size}.pt")

    results = model.train(
        data=data,
        epochs=epochs,
        imgsz=640,
        batch=16,
        device=0,           # GPU 0
        project=str(output_dir),
        name="freky",
        patience=10,        # early stopping
        save=True,
        plots=True,
    )

    print(f"\nTreinamento concluido. Pesos salvos em: {results.save_dir}")
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=str, required=True, help="Caminho para dataset.yaml")
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--model-size", choices=["n", "s", "m", "l", "x"], default="m",
                        help="Tamanho do modelo: n=nano, s=small, m=medium, l=large, x=xlarge")
    parser.add_argument("--output-dir", type=Path, default=Path("runs"))
    args = parser.parse_args()

    train(args.data, args.epochs, args.model_size, args.output_dir)
