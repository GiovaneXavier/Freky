import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from prometheus_fastapi_instrumentator import Instrumentator

from routes import scans, websocket, audit, auth
from core.detector import Detector
from core.limiter import limiter
from core.settings import settings
from core.metrics import scans_total, inference_duration, detections_total, websocket_connections  # noqa: F401 — registra métricas
from models.database import init_db

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
log = logging.getLogger("freky.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Iniciando Freky API...")
    await init_db()
    app.state.detector = Detector(
        model_path=settings.model_path,
        confidence_threshold=settings.confidence_threshold,
        high_confidence_threshold=settings.high_confidence_threshold,
        class_confidence_thresholds=settings.class_confidence_thresholds,
    )
    log.info("Detector carregado. Modelo: %s", settings.model_path)
    yield
    log.info("Encerrando Freky API.")


app = FastAPI(
    title="Freky API",
    description="X-Ray item detection for HI-SCAN 6040i",
    version="0.1.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.middleware("http")
async def request_logging(request: Request, call_next):
    request_id = str(uuid.uuid4())[:8]
    request.state.request_id = request_id
    start = time.monotonic()
    log.info(
        "→ %s %s [%s]",
        request.method,
        request.url.path,
        request_id,
    )
    response = await call_next(request)
    elapsed_ms = (time.monotonic() - start) * 1000
    log.info(
        "← %s %s %d (%.1fms) [%s]",
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
        request_id,
    )
    return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.allowed_origins.split(",") if o.strip()],
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

# Instrumentação automática: latência, contagem e status HTTP em /metrics
Instrumentator(
    should_group_status_codes=True,
    excluded_handlers=["/metrics", "/health"],
).instrument(app).expose(app, include_in_schema=False)

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(scans.router, prefix="/scans", tags=["scans"])
app.include_router(audit.router, prefix="/audit", tags=["audit"])
app.include_router(websocket.router, tags=["websocket"])


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/health/ready")
async def health_ready(request: Request):
    """
    Readiness check — verifica banco, modelo e Redis.
    Retorna 200 se tudo OK, 503 se algum componente falhar.
    """
    from sqlalchemy import text
    from models.database import SessionLocal
    from core.cache import get_redis

    checks: dict[str, str] = {}
    healthy = True

    # Banco de dados
    try:
        async with SessionLocal() as session:
            await session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:
        checks["database"] = f"error: {exc}"
        healthy = False

    # Redis
    try:
        await get_redis().ping()
        checks["redis"] = "ok"
    except Exception as exc:
        checks["redis"] = f"error: {exc}"
        healthy = False

    # Modelo ONNX
    detector = getattr(request.app.state, "detector", None)
    if detector is not None and getattr(detector, "_session", None) is not None:
        checks["model"] = "ok"
    else:
        checks["model"] = "not loaded"
        healthy = False

    status_code = 200 if healthy else 503
    return JSONResponse(
        status_code=status_code,
        content={"status": "ready" if healthy else "degraded", "checks": checks},
    )
