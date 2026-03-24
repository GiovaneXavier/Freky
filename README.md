# Freky — X-Ray Item Detection

![CI](https://github.com/giovanexavier/freky/actions/workflows/ci.yml/badge.svg)
![Docker](https://github.com/giovanexavier/freky/actions/workflows/docker.yml/badge.svg)
![Python](https://img.shields.io/badge/python-3.12-blue)
![License](https://img.shields.io/badge/license-MIT-green)

Sistema de detecção de itens em imagens de raio-X de bagagens, baseado em YOLOv8 + ONNX Runtime, com API REST, watcher de pastas e dashboard de auditoria em tempo real.

---

## Visão geral

```
┌─────────────┐    ┌───────────────┐    ┌──────────────────┐
│  Scanner    │───▶│    Watcher    │───▶│       API        │
│ (HI-SCAN)   │    │  (pasta rede) │    │  FastAPI + ONNX  │
└─────────────┘    └───────────────┘    └────────┬─────────┘
                                                  │
                                        ┌─────────▼─────────┐
                                        │    Dashboard      │
                                        │  React + Recharts │
                                        └───────────────────┘
```

| Componente   | Stack                              | Porta |
|--------------|------------------------------------|-------|
| **API**      | FastAPI, SQLAlchemy, ONNX Runtime  | 8000  |
| **Watcher**  | Python, Watchdog, HTTPX            | —     |
| **Dashboard**| React, Vite, Recharts, Tailwind     | 3000  |
| **DB**       | PostgreSQL 16                      | 5432  |
| **Cache**    | Redis 7                            | 6379  |

---

## Requisitos

- Docker ≥ 24 e Docker Compose ≥ 2.20
- (Opcional) GPU NVIDIA + CUDA 12 para inferência acelerada
- (Opcional) Python 3.12 + GPU para treino local

---

## Início rápido

```bash
# 1. Clone e configure variáveis de ambiente
git clone https://github.com/giovanexavier/freky.git
cd freky
cp .env.example .env          # edite conforme necessário

# 2. Coloque o modelo exportado em:
#    model/weights/freky.onnx

# 3. Suba a stack
make up

# API:       http://localhost:8000
# Dashboard: http://localhost:3000
# Docs:      http://localhost:8000/docs
```

---

## Desenvolvimento

```bash
# Stack com hot-reload (API recarrega ao salvar, dashboard via Vite HMR)
make dev

# Testes da API
make test

# Lint
make lint

# Gerar scans sintéticos para teste manual
make mock-scans
```

---

## Pipeline do modelo

### 1. Converter dataset HiXray para YOLO

```bash
make convert-dataset HIXRAY_DIR=/caminho/para/HiXray
```

### 2. (Opcional) Validar e aumentar dataset

```bash
make validate-dataset
make augment
```

### 3. Treinar

```bash
# Local (requer GPU)
make train

# Ou com dataset aumentado
make train-augmented

# Ou via Docker com GPU
make train-docker
```

### 4. Avaliar

```bash
make evaluate WEIGHTS=model/runs/freky-v1/weights/best.pt
```

### 5. Exportar para ONNX

```bash
make export WEIGHTS=model/runs/freky-v1/weights/best.pt
# Gera: model/weights/freky.onnx
```

### 6. Inferência manual

```bash
make infer WEIGHTS=model/weights/freky.onnx SOURCE=scans/incoming/
```

---

## Classes detectadas

| ID | Classe               | Restrito |
|----|----------------------|----------|
| 0  | portable_charger_1   | Sim      |
| 1  | portable_charger_2   | Sim      |
| 2  | mobile_phone         | Sim      |
| 3  | laptop               | Sim      |
| 4  | tablet               | Sim      |
| 5  | cosmetic             | Não      |
| 6  | water                | Não      |
| 7  | nonmetallic_lighter  | Não      |

Decisões possíveis: **LIBERADO** · **VERIFICAR** · **INCONCLUSIVO**

---

## CI/CD

| Workflow        | Disparo                          | O que faz                                      |
|-----------------|----------------------------------|------------------------------------------------|
| `ci.yml`        | Push / PR em `main`              | Lint (ruff) + testes API + testes Watcher      |
| `docker.yml`    | Push em `main` ou tag `v*`       | Build e push das imagens para GHCR             |
| `model-eval.yml`| Manual ou schedule (seg. 06h UTC)| Avalia modelo e salva artefatos de métricas    |

Imagens publicadas em `ghcr.io/giovanexavier/freky-{api,watcher,dashboard}`.

---

## Estrutura do projeto

```
freky/
├── api/                  # FastAPI — inferência, auditoria, WebSocket
│   ├── core/             # Detector ONNX, regras, configurações
│   ├── models/           # SQLAlchemy ORM
│   ├── routes/           # Endpoints REST
│   └── tests/
├── watcher/              # Watcher de pasta — envia scans para a API
│   └── tests/
├── dashboard/            # Frontend React
├── model/
│   ├── data/             # Scripts de conversão, augmentação e validação
│   ├── export/           # Export ONNX
│   ├── training/         # Treino, avaliação e inferência
│   └── weights/          # Modelos exportados (.onnx) — não versionados
├── docker/               # Dockerfiles e nginx.conf
├── .github/workflows/    # CI/CD
├── docker-compose.yml
├── docker-compose.dev.yml
├── Makefile
└── .env.example
```

---

## Licença

MIT
