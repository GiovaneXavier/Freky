from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from routes import scans, websocket, audit
from core.detector import Detector
from core.settings import settings
from models.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    app.state.detector = Detector(
        model_path=settings.model_path,
        confidence_threshold=settings.confidence_threshold,
        high_confidence_threshold=settings.high_confidence_threshold,
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

app.include_router(scans.router, prefix="/scans", tags=["scans"])
app.include_router(audit.router, prefix="/audit", tags=["audit"])
app.include_router(websocket.router, tags=["websocket"])


@app.get("/health")
async def health():
    return {"status": "ok"}
