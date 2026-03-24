"""
Fine-tuning do YOLOv8 no dataset HiXray com logging opcional via W&B.

Fluxo recomendado:
    1. make convert-dataset HIXRAY_DIR=/path/to/HiXray
    2. python validate_dataset.py --dataset-dir model/data/hixray_yolo --fix
    3. python augment_xray.py --input-dir model/data/hixray_yolo/train \
                              --output-dir model/data/hixray_augmented/train
    4. python train.py --data model/data/hixray_yolo/dataset.yaml

Usage:
    # Treinamento basico
    python train.py --data model/data/hixray_yolo/dataset.yaml

    # Com dataset aumentado
    python train.py --data model/data/hixray_augmented/dataset.yaml --epochs 80

    # Com Weights & Biases
    python train.py --data model/data/hixray_yolo/dataset.yaml --wandb
"""
import argparse
import os
from pathlib import Path

from ultralytics import YOLO

HYPERPARAMS = Path(__file__).parent / "hyperparams.yaml"

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


def setup_wandb(project: str, run_name: str):
    try:
        import wandb
        wandb.init(project=project, name=run_name, tags=["xray", "yolov8", "freky"])
        return True
    except ImportError:
        print("[AVISO] wandb nao instalado. Treinamento sem logging remoto.")
        print("        Para instalar: pip install wandb")
        return False


def train(
    data: str,
    epochs: int,
    model_size: str,
    batch: int,
    output_dir: Path,
    resume: bool,
    use_wandb: bool,
    run_name: str,
):
    if use_wandb:
        setup_wandb(project="freky-xray", run_name=run_name)

    model = YOLO(f"yolov8{model_size}.pt")

    print(f"\n{'='*60}")
    print(f"  Iniciando treinamento Freky")
    print(f"  Modelo:  YOLOv8{model_size.upper()}")
    print(f"  Epochs:  {epochs}")
    print(f"  Batch:   {batch}")
    print(f"  Data:    {data}")
    print(f"  Output:  {output_dir}")
    print(f"  W&B:     {'sim' if use_wandb else 'nao'}")
    print(f"{'='*60}\n")

    results = model.train(
        data=data,
        epochs=epochs,
        imgsz=640,
        batch=batch,
        device=0,
        project=str(output_dir),
        name=run_name,

        # Hyperparametros customizados para raio-X
        cfg=str(HYPERPARAMS),

        # Early stopping
        patience=15,

        # Checkpoints
        save=True,
        save_period=10,      # salva checkpoint a cada 10 epochs

        # Validacao
        val=True,

        # Reproducibilidade
        seed=42,
        deterministic=True,

        # Logging
        plots=True,
        verbose=True,

        # Retomar treinamento interrompido
        resume=resume,
    )

    best_weights = Path(results.save_dir) / "weights" / "best.pt"
    print(f"\nTreinamento concluido!")
    print(f"Melhor checkpoint: {best_weights}")
    print(f"mAP@0.5: {results.results_dict.get('metrics/mAP50(B)', 'N/A')}")
    print(f"\nProximo passo — exportar para ONNX:")
    print(f"  make export WEIGHTS={best_weights}")

    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=str, required=True,
                        help="Caminho para dataset.yaml")
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--model-size", choices=["n", "s", "m", "l", "x"], default="m",
                        help="n=nano(3.2M) s=small(11M) m=medium(25M) l=large(43M) x=xlarge(68M)")
    parser.add_argument("--batch", type=int, default=16,
                        help="Batch size (-1 para autobatch)")
    parser.add_argument("--output-dir", type=Path, default=Path("model/runs"))
    parser.add_argument("--resume", action="store_true",
                        help="Retoma treinamento a partir do ultimo checkpoint")
    parser.add_argument("--wandb", action="store_true",
                        help="Habilita logging no Weights & Biases")
    parser.add_argument("--run-name", type=str, default="freky-v1",
                        help="Nome do experimento")
    args = parser.parse_args()

    train(
        data=args.data,
        epochs=args.epochs,
        model_size=args.model_size,
        batch=args.batch,
        output_dir=args.output_dir,
        resume=args.resume,
        use_wandb=args.wandb,
        run_name=args.run_name,
    )


if __name__ == "__main__":
    main()
