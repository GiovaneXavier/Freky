# Container de treinamento com suporte a GPU NVIDIA
# Uso:
#   docker build -f docker/train.Dockerfile -t freky-train .
#   docker run --gpus all --rm \
#     -v $(pwd)/model:/workspace/model \
#     -v /caminho/para/HiXray:/data/HiXray \
#     freky-train \
#     python model/training/train.py \
#       --data model/data/hixray_yolo/dataset.yaml \
#       --epochs 50

FROM pytorch/pytorch:2.4.1-cuda12.4-cudnn9-runtime

WORKDIR /workspace

# Dependencias do sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY model/training/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt \
    && pip install --no-cache-dir albumentations==1.4.18 wandb==0.18.3

# Copia apenas os scripts de treinamento (dados ficam em volumes)
COPY model/ model/

ENV PYTHONPATH=/workspace

# Ponto de entrada flexivel — pode ser substituido pelo docker run
ENTRYPOINT ["python"]
CMD ["model/training/train.py", "--help"]
