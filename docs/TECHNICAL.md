# Freky — Documentação Técnica

**Sistema de Detecção de Itens Eletrônicos em Imagens X-Ray**
Versão 1.0 — Março 2026

---

## Índice

1. [Visão Geral do Sistema](#1-visão-geral-do-sistema)
2. [Arquitetura](#2-arquitetura)
3. [Componentes](#3-componentes)
   - 3.1 [API (Backend)](#31-api-backend)
   - 3.2 [Watcher Service](#32-watcher-service)
   - 3.3 [Dashboard (Frontend)](#33-dashboard-frontend)
   - 3.4 [Modelo de Detecção](#34-modelo-de-detecção)
4. [Banco de Dados](#4-banco-de-dados)
5. [Autenticação e Segurança](#5-autenticação-e-segurança)
6. [Observabilidade](#6-observabilidade)
7. [Pipeline de Treinamento](#7-pipeline-de-treinamento)
8. [Infraestrutura Docker](#8-infraestrutura-docker)
9. [CI/CD](#9-cicd)
10. [Configuração de Ambiente](#10-configuração-de-ambiente)
11. [Endpoints da API](#11-endpoints-da-api)
12. [Fluxo de Processamento](#12-fluxo-de-processamento)

---

## 1. Visão Geral do Sistema

O **Freky** é um sistema de visão computacional em tempo real para detecção automática de itens eletrônicos em imagens geradas pelo scanner de bagagem **HI-SCAN 6040i** (Smiths Detection). O sistema integra inferência com modelo ONNX, banco de dados relacional, cache Redis, dashboard React e rastreabilidade completa com feedback de operadores.

### Casos de uso principais

| Caso de uso | Descrição |
|---|---|
| Detecção automática | Imagem X-Ray → inferência ONNX → decisão em < 2s |
| Monitoramento em tempo real | Operador acompanha cada scan via WebSocket |
| Auditoria | Histórico completo com filtros e exportação CSV |
| Feedback | Operador sinaliza falsos positivos/negativos |
| Métricas | Dashboard Grafana com KPIs operacionais |

### Decisões possíveis

| Decisão | Significado |
|---|---|
| `LIBERADO` | Nenhum item restrito detectado com alta confiança |
| `VERIFICAR` | Item restrito detectado — requer inspeção manual |
| `INCONCLUSIVO` | Confiança insuficiente — requer revisão |

---

## 2. Arquitetura

```
┌──────────────────────────────────────────────────────────┐
│                  HI-SCAN 6040i Scanner                   │
│          (deposita .jpg/.tiff em pasta de rede)          │
└──────────────────────────────────────────────────────────┘
                          │
                          ▼
        ┌─────────────────────────────────┐
        │        Watcher Service          │
        │  • watchdog.Observer            │
        │  • Aguarda estabilização        │
        │  • Retry exponencial (4x)       │
        └─────────────────────────────────┘
                          │  POST /scans/
                          ▼
        ┌─────────────────────────────────┐
        │    FastAPI REST Server :8000    │
        │  • ONNX Runtime (YOLOv8)        │
        │  • JWT Auth + Rate Limiting     │
        │  • Prometheus /metrics          │
        │  • WebSocket /ws                │
        └─────────────────────────────────┘
               │                │
               ▼                ▼
   ┌─────────────────┐  ┌──────────────────┐
   │   SQL Server    │  │      Redis       │
   │  Tabela: scans  │  │  Cache: audit:*  │
   │  (persistência) │  │  (TTL 300s)      │
   └─────────────────┘  └──────────────────┘
               │
               ▼
   ┌─────────────────────────────────────┐
   │       React Dashboard :3000         │
   │  • Login JWT                        │
   │  • Visão do Operador (WS)           │
   │  • Auditoria + Filtros              │
   │  • Estatísticas (Recharts)          │
   └─────────────────────────────────────┘

   ┌─────────────────────────────────────┐
   │      Observabilidade (opcional)     │
   │  Prometheus :9090                   │
   │  Grafana :3001                      │
   │  Redis Exporter :9121               │
   └─────────────────────────────────────┘
```

---

## 3. Componentes

### 3.1 API (Backend)

**Localização:** `api/`
**Stack:** Python 3.11, FastAPI 0.115, Uvicorn, SQLAlchemy 2.0 (async)

#### Estrutura de diretórios

```
api/
├── main.py                  # Inicialização da app, middlewares, routers
├── requirements.txt
├── requirements-dev.txt
├── core/
│   ├── auth.py              # JWT, bcrypt, dependências FastAPI
│   ├── cache.py             # Wrapper async Redis
│   ├── detector.py          # ONNX Runtime + pré/pós-processamento
│   ├── limiter.py           # Rate limiting (slowapi)
│   ├── metrics.py           # Contadores/histogramas Prometheus
│   ├── rules.py             # Lógica de decisão (LIBERADO/VERIFICAR/INCONCLUSIVO)
│   └── settings.py          # Pydantic Settings (carrega .env)
├── models/
│   ├── database.py          # Engine async, session factory, init_db()
│   └── scan.py              # ORM SQLAlchemy (tabela scans)
├── routes/
│   ├── auth.py              # POST /auth/login
│   ├── audit.py             # GET /audit/*, export CSV
│   ├── scans.py             # POST /scans/, POST /scans/{id}/feedback
│   └── websocket.py         # WS /ws
└── tests/
    ├── test_auth.py
    ├── test_detector.py
    ├── test_improvements.py
    └── test_websocket.py
```

#### Módulo Detector (`core/detector.py`)

```python
class Detector:
    def predict(image_path) -> (Decision, List[Detection])
    def _preprocess(image, target_size=640) -> np.ndarray  # CHW, normalizado
    def _postprocess(outputs, orig_w, orig_h) -> List[Detection]
    def _load_model(model_path) -> ort.InferenceSession
```

- Entrada: imagem PIL (qualquer tamanho)
- Redimensionamento: letterbox para 640×640
- Formato tensor: `float32[1, 3, 640, 640]`, normalizado [0,1]
- Saída ONNX: `float32[1, 8, 8400]` (colunas: 4 bbox + 8 classes)
- Providers: `CUDAExecutionProvider` → fallback `CPUExecutionProvider`

#### Módulo de Regras (`core/rules.py`)

```
Sem detecções              → LIBERADO
Confiança < threshold      → INCONCLUSIVO
Item restrito detectado    → VERIFICAR
Apenas itens permitidos    → LIBERADO
```

**Itens restritos:** mobile_phone, tablet, laptop, portable_charger_1/2, kindle, e_reader, headphones

#### Métricas Prometheus (`core/metrics.py`)

| Métrica | Tipo | Labels |
|---|---|---|
| `freky_scans_total` | Counter | decision |
| `freky_inference_duration_seconds` | Histogram | — |
| `freky_detections_total` | Counter | class_name |
| `freky_websocket_connections_active` | Gauge | — |

---

### 3.2 Watcher Service

**Localização:** `watcher/watcher.py`
**Stack:** Python 3.11, watchdog 5.0, httpx 0.27

Monitora a pasta `SCAN_INPUT_DIR` com `watchdog.Observer`. Ao detectar um novo arquivo:

1. Filtra por extensão suportada (`.jpg`, `.jpeg`, `.tif`, `.tiff`)
2. Aguarda estabilização do arquivo (polling a cada 200ms por até 10s)
3. Envia para `POST /scans/` com retry exponencial

#### Política de retry

| Tentativa | Delay |
|---|---|
| 1ª | imediata |
| 2ª | 2s |
| 3ª | 4s |
| 4ª | 8s |
| 5ª | 16s |

Erros 4xx não são retentados (falha de validação). Erros 5xx e falhas de rede são retentados.

---

### 3.3 Dashboard (Frontend)

**Localização:** `dashboard/`
**Stack:** React 18, TypeScript, Vite, Tailwind CSS, Recharts

#### Páginas

| Página | Rota | Descrição |
|---|---|---|
| Login | `/login` | Formulário JWT, token em localStorage |
| Visão do Operador | `/` | Scan atual em tempo real via WebSocket |
| Auditoria | `/audit` | Lista paginada, filtros, feedback |
| Estatísticas | `/stats` | Gráficos de barras, pizza, cards KPI |

#### Hooks principais

| Hook | Função |
|---|---|
| `useAuth()` | login/logout, contexto de usuário |
| `useScans()` | WebSocket, scan atual, histórico (50 items) |
| `useAudit(filters)` | Lista paginada de scans com filtros |
| `useAuditStats()` | Totais por decisão |
| `useDailyStats(days)` | Séries temporais diárias |

#### Autenticação WebSocket

Token JWT passado como query param:
```
ws://host:8000/ws?token=<jwt>
```

---

### 3.4 Modelo de Detecção

**Arquitetura:** YOLOv8 (fine-tuning sobre pesos COCO)
**Dataset:** HiXray (8 classes de itens eletrônicos)
**Input:** 640×640 RGB
**Output:** bounding boxes + confidence scores por classe

#### Classes do modelo

| ID | Classe | Tipo |
|---|---|---|
| 0 | portable_charger_1 | Restrito |
| 1 | portable_charger_2 | Restrito |
| 2 | mobile_phone | Restrito |
| 3 | laptop | Restrito |
| 4 | tablet | Restrito |
| 5 | cosmetic | Permitido |
| 6 | water | Permitido |
| 7 | nonmetallic_lighter | Monitorado |

#### Thresholds

| Parâmetro | Valor padrão |
|---|---|
| `CONFIDENCE_THRESHOLD` | 0.60 |
| `HIGH_CONFIDENCE_THRESHOLD` | 0.85 |

Thresholds por classe podem ser definidos individualmente via `CLASS_CONFIDENCE_THRESHOLDS`.

---

## 4. Banco de Dados

**Engine:** Microsoft SQL Server 2022 (Express)
**ORM:** SQLAlchemy 2.0 async (`aioodbc`)

### Tabela `scans`

| Coluna | Tipo | Descrição |
|---|---|---|
| `id` | VARCHAR (PK) | UUID gerado automaticamente |
| `created_at` | DATETIME | Timestamp UTC, indexado |
| `filename` | VARCHAR | Nome original do arquivo |
| `image_path` | VARCHAR | Caminho da imagem arquivada |
| `annotated_image_path` | VARCHAR (null) | Imagem com bboxes |
| `decision` | ENUM | LIBERADO / VERIFICAR / INCONCLUSIVO |
| `detections` | JSON | Lista de detecções com classe, confiança, bbox |
| `processing_time_ms` | FLOAT (null) | Tempo de inferência |
| `operator_id` | VARCHAR (null) | ID do operador que revisou |
| `operator_feedback` | VARCHAR (null) | confirmed / false_positive / false_negative |
| `feedback_at` | DATETIME (null) | Timestamp do feedback |

### Índices

```sql
CREATE INDEX ix_scans_created_at ON scans (created_at);
CREATE INDEX ix_scans_decision ON scans (decision);
CREATE INDEX ix_scans_created_at_decision ON scans (created_at, decision);
```

---

## 5. Autenticação e Segurança

### JWT

- Algoritmo: HS256
- Expiração: 480 minutos (8h), configurável via `JWT_EXPIRE_MINUTES`
- Payload: `{sub, role, exp}`
- Validação: mínimo 32 caracteres, bloqueio do valor padrão em produção

### Usuários

Configurados via variável `FREKY_USERS` (JSON):

```json
[
  {"username": "admin", "password": "$2b$12$HASH", "role": "admin"},
  {"username": "op1",   "password": "$2b$12$HASH", "role": "operator"}
]
```

- **admin:** acesso total
- **operator:** leitura + envio de feedback

### Rate Limiting

`POST /auth/login` → 10 requisições/minuto por IP (slowapi).

### Upload Validation

- Tamanho máximo: 50 MB (configurável via `MAX_UPLOAD_BYTES`)
- Validação de formato: `PIL.Image.verify()` antes de persistir

### CORS

Origens permitidas configuradas via `ALLOWED_ORIGINS` (lista separada por vírgula).

---

## 6. Observabilidade

### Prometheus

Exposto em `GET /metrics`. Configuração em `docker/prometheus.yml`.

Retenção: 30 dias.

### Grafana

- Porta: 3001
- Dashboard provisionado: `docker/grafana/dashboards/freky.json`
- Datasource provisionado: Prometheus

### Redis Exporter

- Porta: 9121
- Exporta métricas do Redis para Prometheus

### Health Checks

| Endpoint | Tipo | Verifica |
|---|---|---|
| `GET /health` | Liveness | Sempre retorna `{status: "ok"}` |
| `GET /health/ready` | Readiness | Banco + Redis + Modelo ONNX |

```json
// GET /health/ready — OK
{"status": "ready", "database": "ok", "redis": "ok", "model": "ok"}

// GET /health/ready — Degradado
{"status": "degraded", "database": "ok", "redis": "error", "model": "ok"}
```

### Logging

Middleware HTTP com request-id, latência e status em cada request.

---

## 7. Pipeline de Treinamento

**Localização:** `model/`

### Fluxo completo

```
1. Dataset HiXray
       ↓
2. model/data/scripts/convert_hixray_to_yolo.py
   (converte anotações para formato YOLO)
       ↓
3. model/data/scripts/validate_dataset.py
   (valida integridade das anotações)
       ↓
4. model/data/scripts/augment_xray.py
   (aumentação específica para X-ray: sem flip, sem cor, rotação ±10°)
       ↓
5. model/training/train.py
   (YOLOv8 fine-tuning, 50 épocas, imgsz=640)
       ↓  best.pt
6. model/training/evaluate.py
   (mAP@0.5, mAP@0.5:0.95, precision, recall)
       ↓  aprovado
7. model/export/export_onnx.py
   (exporta para ONNX opset=17, simplify=True)
       ↓  freky.onnx
8. Copiar para model/weights/freky.onnx
   (montado no container como :ro)
```

### Hiperparâmetros principais (`hyperparams.yaml`)

| Parâmetro | Valor | Motivo |
|---|---|---|
| `lr0` | 0.001 | Fine-tuning (não do zero) |
| `epochs` | 50 | Early stopping patience=15 |
| `imgsz` | 640 | Padrão YOLOv8 |
| `flipud/fliplr` | 0.0 | X-ray tem semântica direcional |
| `hsv_h/s` | 0.0 | Cor é semântica em X-ray |
| `hsv_v` | 0.3 | Simula variações kV/mA do scanner |
| `mosaic` | 0.8 | Reduzido para preservar padrões |
| `iou` | 0.7 | NMS mais rigoroso |

### Avaliação

```bash
python model/training/evaluate.py \
  --weights model/weights/best.pt \
  --data model/data/hixray_yolo/dataset.yaml \
  --conf 0.60
```

Saídas: `results.csv`, `confusion_matrix.png`, `PR_curve.png`

---

## 8. Infraestrutura Docker

### Serviços (`docker-compose.yml`)

| Serviço | Imagem base | Porta | Volumes |
|---|---|---|---|
| `api` | python:3.11-slim | 8000 | ./scans, ./model/weights (ro) |
| `watcher` | python:3.11-slim | — | ./scans |
| `dashboard` | node:20 → nginx | 3000 | — |
| `sqlserver` | mssql/server:2022 | 1433 | sqlserver_data |
| `redis` | redis:7-alpine | 6379 | redis_data |
| `redis-exporter` | oliver006/redis_exporter | 9121 | — |
| `prometheus` | prom/prometheus:v2.54.1 | 9090 | prometheus_data |
| `grafana` | grafana/grafana:11.2.0 | 3001 | grafana_data |

### Healthchecks

- **sqlserver:** `sqlcmd -Q "SELECT 1"` a cada 10s
- **redis:** `redis-cli ping` a cada 5s
- **api:** depende de sqlserver e redis estarem healthy

### Volumes persistentes

```
sqlserver_data   → dados do banco SQL Server
redis_data       → dados do Redis
prometheus_data  → séries temporais (30 dias)
grafana_data     → dashboards e configurações
```

### Variantes de compose

| Arquivo | Uso |
|---|---|
| `docker-compose.yml` | Produção |
| `docker-compose.dev.yml` | Desenvolvimento (hot-reload, portas expostas) |
| `docker-compose.staging.yml` | Homologação |

---

## 9. CI/CD

### GitHub Actions

| Workflow | Trigger | Jobs |
|---|---|---|
| `ci.yml` | Push main/claude/*, PR→main | lint, test-api, test-watcher |
| `docker.yml` | Push main, tags v*.*.* | build-api, build-watcher, build-dashboard |
| `model-eval.yml` | Manual / Seg 06:00 UTC | evaluate |

### Workflow CI (`ci.yml`)

```
lint (ruff check api watcher)
    ├── test-api
    │   ├── Serviços: PostgreSQL 16, Redis 7
    │   ├── FREKY_ENV=test, MODEL_PATH=""
    │   └── pytest --cov → coverage.xml
    └── test-watcher
        └── pytest --cov
```

### Workflow Docker (`docker.yml`)

1. Build da imagem
2. Push para `ghcr.io`
3. Trivy scan (CRITICAL + HIGH)
4. Upload SARIF → GitHub Security tab

### Workflow de Avaliação (`model-eval.yml`)

- Baixa pesos `.pt` da última release do GitHub
- Executa `evaluate.py` com dataset HiXray
- Publica artefatos (métricas, confusion matrix, PR curve) com retenção de 30 dias

---

## 10. Configuração de Ambiente

Arquivo `.env` na raiz do projeto:

```env
# Ambiente
FREKY_ENV=production        # dev | test | production
DEBUG=false

# Banco de dados
MSSQL_SA_PASSWORD=YourStrong!Passw0rd
DATABASE_URL=mssql://sa:YourStrong!Passw0rd@sqlserver:1433/freky?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes

# Redis
REDIS_URL=redis://redis:6379/0

# Modelo
MODEL_PATH=/app/model/weights/freky.onnx
CONFIDENCE_THRESHOLD=0.60
HIGH_CONFIDENCE_THRESHOLD=0.85

# Watcher
SCAN_INPUT_DIR=/scans/incoming
SCAN_ARCHIVE_DIR=/scans/archive

# Auth
JWT_SECRET_KEY=<string-aleatória-32+-chars>
JWT_EXPIRE_MINUTES=480

# Usuários (JSON)
FREKY_USERS='[{"username":"admin","password":"$2b$12$HASH","role":"admin"}]'

# CORS
ALLOWED_ORIGINS=http://localhost:3000,http://dashboard

# Frontend (build-time)
VITE_API_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000
```

---

## 11. Endpoints da API

### Autenticação

| Método | Rota | Auth | Descrição |
|---|---|---|---|
| POST | `/auth/login` | — | Login, retorna JWT |

### Scans

| Método | Rota | Auth | Descrição |
|---|---|---|---|
| POST | `/scans/` | Bearer | Upload de imagem, retorna decisão |
| POST | `/scans/{id}/feedback` | Bearer | Feedback do operador |

### Auditoria

| Método | Rota | Auth | Descrição |
|---|---|---|---|
| GET | `/audit/` | Bearer | Lista paginada (filtros: page, page_size, date_from, date_to, decision) |
| GET | `/audit/stats` | Bearer | Totais por decisão (cache 5min) |
| GET | `/audit/daily` | Bearer | Série diária — parâmetro: days (padrão 14) |
| GET | `/audit/export` | Bearer | Download CSV com filtros |

### Sistema

| Método | Rota | Auth | Descrição |
|---|---|---|---|
| GET | `/health` | — | Liveness check |
| GET | `/health/ready` | — | Readiness check (DB + Redis + Model) |
| GET | `/metrics` | — | Métricas Prometheus |
| WS | `/ws` | ?token= | Stream de resultados em tempo real |

---

## 12. Fluxo de Processamento

```
[Scanner HI-SCAN 6040i]
  │
  │  deposita imagem em /scans/incoming/
  ▼
[Watcher]
  │  watchdog detecta arquivo novo
  │  aguarda estabilização do arquivo
  │  POST /scans/ multipart/form-data
  ▼
[API — POST /scans/]
  │  valida tamanho (≤50MB) e formato (PIL.verify)
  │  copia para /scans/archive/
  │  Detector.predict(image_path)
  │    ├── _preprocess: PIL → tensor [1,3,640,640]
  │    ├── ort.InferenceSession.run()
  │    └── _postprocess: output → List[Detection]
  │  apply_rules(detections, threshold)
  │    └── → Decision (LIBERADO|VERIFICAR|INCONCLUSIVO)
  │  INSERT INTO scans (...)
  │  cache_delete_pattern("audit:*")
  │  broadcast via WebSocket
  │  increment Prometheus counters
  ▼
[SQL Server]           [Redis]           [WebSocket]
  salva scan record      invalida cache    notifica dashboard

[Dashboard — Operador]
  │  recebe {type: "scan_result", data: {...}}
  │  atualiza painel em tempo real
  │  operador visualiza imagem + decisão + itens detectados
  ▼
[Feedback (opcional)]
  │  POST /scans/{id}/feedback
  │    body: {operator_id, feedback: "confirmed"|"false_positive"|"false_negative"}
  └── UPDATE scans SET operator_feedback=...
```

---

*Documento gerado automaticamente a partir do código-fonte do projeto Freky.*
*Última atualização: Março 2026*
