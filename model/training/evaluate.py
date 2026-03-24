"""
Avalia o modelo treinado no conjunto de validacao.

Calcula mAP@0.5, mAP@0.5:0.95, precision e recall por classe.
Tambem imprime a matriz de confusao de decisoes (LIBERADO/VERIFICAR/INCONCLUSIVO).

Usage:
    python evaluate.py --weights runs/freky/weights/best.pt \
                       --data /data/hixray_yolo/dataset.yaml
"""
import argparse
from pathlib import Path

from ultralytics import YOLO


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


def evaluate(weights: Path, data: str, split: str = "val", conf: float = 0.60):
    model = YOLO(str(weights))

    metrics = model.val(
        data=data,
        split=split,
        conf=conf,
        iou=0.5,
        save_json=True,
        plots=True,
    )

    print("\n" + "=" * 60)
    print("  RESULTADOS DE AVALIACAO")
    print("=" * 60)
    print(f"  mAP@0.5:       {metrics.box.map50:.4f}")
    print(f"  mAP@0.5:0.95:  {metrics.box.map:.4f}")
    print(f"  Precision:     {metrics.box.mp:.4f}")
    print(f"  Recall:        {metrics.box.mr:.4f}")
    print()
    print("  Por classe:")
    for i, cls in enumerate(HIXRAY_CLASSES):
        if i < len(metrics.box.ap_class_index):
            ap = metrics.box.ap50[i]
            print(f"    {cls:<30s} AP@0.5: {ap:.4f}")

    print("=" * 60)
    print(f"\nRelatorios salvos em: {model.predictor.save_dir if hasattr(model, 'predictor') else 'runs/'}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--weights", type=Path, required=True)
    parser.add_argument("--data", type=str, required=True)
    parser.add_argument("--split", choices=["val", "test"], default="val")
    parser.add_argument("--conf", type=float, default=0.60)
    args = parser.parse_args()

    evaluate(args.weights, args.data, args.split, args.conf)
