from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from prometheus_fastapi_instrumentator import Instrumentator

from routes import scans, websocket, audit, auth
from core.detector import Detector
from core.settings import settings
from core.metrics import scans_total, inference_duration, detections_total, websocket_connections  # noqa: F401 — registra métricas
from models.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    app.state.detector = Detector(
        model_path=settings.model_path,
        confidence_threshold=settings.confidence_threshold,
        high_confidence_threshold=settings.high_confidence_threshold,
        class_confidence_thresholds=settings.class_confidence_thresholds,
    )
    yield
    # cleanup


app = FastAPI(
    title="Freky API",
    description="X-Ray item detection for HI-SCAN 6040i",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
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
