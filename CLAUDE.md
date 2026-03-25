# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Freky** is an X-Ray item detection system for baggage screening (scanner HI-SCAN 6040i). It detects 8 classes of items (portable chargers, mobile phone, laptop, tablet, cosmetic, water, lighter) and produces decisions: **LIBERADO** (Approved), **VERIFICAR** (Check), **INCONCLUSIVO** (Inconclusive).

## Commands

### Development

```bash
make dev          # Start full dev stack with hot-reload
make up           # Start all services (production mode)
make down         # Stop all services
make logs         # View service logs
```

### Testing

```bash
make test         # Run API tests with coverage (via Docker)

# Run tests locally (from api/ directory):
cd api && pip install -r requirements-dev.txt
pytest -v --cov=. --cov-report=term-missing

# Run a single test file:
cd api && pytest tests/test_audit.py -v

# Run a single test:
cd api && pytest tests/test_auth.py::test_login_success -v
```

### Linting

```bash
make lint         # Run ruff on api/ and watcher/
cd api && ruff check .
```

### Monitoring

```bash
make monitoring-up    # Start Prometheus (9090) and Grafana (3001)
make monitoring-down
```

### Model Pipeline

```bash
make convert-dataset HIXRAY_DIR=/path  # Convert HiXray dataset to YOLO format
make train                              # Local training (requires GPU)
make train-docker                       # Docker training with GPU
make evaluate WEIGHTS=path/to/weights
make export WEIGHTS=path/to/weights     # Export to ONNX
make mock-scans                         # Generate 30 synthetic X-ray scans
```

## Architecture

The system has four main services orchestrated via Docker Compose:

### API (`api/`) — FastAPI, port 8000
- **`main.py`**: App entry point — initializes Detector via lifespan context, mounts routes, enables CORS and Prometheus auto-instrumentation
- **`core/detector.py`**: ONNX-based YOLOv8 inference. Supports CUDA/CPU. Preprocessing: RGB conversion, 640×640 resize, normalization. Per-class confidence thresholds.
- **`core/rules.py`**: Decision logic translating detections into LIBERADO/VERIFICAR/INCONCLUSIVO
- **`core/auth.py`**: JWT authentication with admin/operator roles
- **`core/settings.py`**: Environment-driven config (model path, thresholds, DB/Redis URLs, JWT settings)
- **`routes/`**: `auth.py`, `scans.py`, `audit.py`, `websocket.py`
- **`models/`**: SQLAlchemy ORM with async DB setup. Uses SQL Server in production, PostgreSQL in CI/tests.
- **`tests/conftest.py`**: Pytest fixtures using aiosqlite (in-memory) and mocked Redis/Detector for test isolation

### Watcher (`watcher/`) — Python background service
- Monitors a network folder for incoming X-ray images
- Submits scans to API via HTTP POST, then archives processed files

### Dashboard (`dashboard/`) — React + TypeScript, port 3000
- Real-time audit visualization via WebSocket
- Recharts for decision distribution charts
- Tailwind CSS styling, Vite build tool

### Infrastructure
- **Database**: SQL Server 2022 (port 1433) in production; PostgreSQL 16 in CI
- **Cache**: Redis 7 (port 6379) for sessions, rate limiting, WebSocket pub/sub
- **Monitoring**: Prometheus (9090) + Grafana (3001)

## CI/CD

Three GitHub Actions workflows:
- **`ci.yml`**: Lint (ruff) + test API + test Watcher on push to `main`/`claude/*` branches. CI uses PostgreSQL + Redis as services.
- **`docker.yml`**: Build and push API/Watcher/Dashboard images to GitHub Container Registry on push to `main` or version tags (`v*.*.*`).
- **`model-eval.yml`**: Weekly model evaluation (Mondays 06:00 UTC) or manual dispatch.

## Key Notes

- **onnxruntime**: Production uses `onnxruntime-gpu`; CI swaps it for `onnxruntime` (CPU) automatically in the test workflow.
- **Database compatibility**: The ORM uses `func.date()` for date extraction (SQLite-compatible for tests). Avoid SQL Server-specific functions.
- **Async throughout**: All DB access is async (SQLAlchemy async + aiosqlite for tests). Use `pytest-asyncio` with `asyncio_mode = auto`.
- **Environment**: Copy `.env.example` to `.env` before running locally. Required vars include `DATABASE_URL`, `REDIS_URL`, `SECRET_KEY`, model paths, and per-class thresholds.
