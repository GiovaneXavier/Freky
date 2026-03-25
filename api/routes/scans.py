import io
import logging
import time
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Request
from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import get_db
from models.scan import Scan
from schemas.scan import ScanResult, FeedbackRequest
from core.settings import settings
from core.auth import get_current_user
from core.cache import cache_delete_pattern
from core.metrics import scans_total, inference_duration, detections_total
from routes.websocket import broadcast

log = logging.getLogger(__name__)
router = APIRouter()


@router.post("/", response_model=ScanResult)
async def process_scan(
    request: Request,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """
    Recebe uma imagem (chamado pelo watcher apos Xport depositar o arquivo)
    e executa a deteccao.
    """
    archive_dir = Path(settings.scan_archive_dir)
    archive_dir.mkdir(parents=True, exist_ok=True)
    image_path = archive_dir / file.filename

    content = await file.read()

    # Valida tamanho
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"Arquivo muito grande. Máximo permitido: {settings.max_upload_bytes // (1024*1024)} MB.",
        )

    # Valida formato de imagem
    try:
        img = Image.open(io.BytesIO(content))
        img.verify()
    except Exception:
        raise HTTPException(status_code=422, detail="Arquivo não é uma imagem válida.")

    image_path.write_bytes(content)

    start = time.monotonic()
    decision, detections = request.app.state.detector.predict(str(image_path))
    elapsed_ms = (time.monotonic() - start) * 1000

    # Métricas Prometheus
    inference_duration.observe(elapsed_ms / 1000)
    scans_total.labels(decision=decision.value).inc()
    for d in detections:
        detections_total.labels(class_name=d.class_name).inc()

    scan = Scan(
        filename=file.filename,
        image_path=str(image_path),
        decision=decision.value,
        detections=[
            {"class_name": d.class_name, "confidence": d.confidence, "bbox": d.bbox}
            for d in detections
        ],
        processing_time_ms=elapsed_ms,
    )
    db.add(scan)
    await db.commit()
    await db.refresh(scan)

    await cache_delete_pattern("audit:*")
    result = ScanResult.model_validate(scan)
    log.info(
        "Scan concluído: file=%s decision=%s detections=%d elapsed_ms=%.1f",
        file.filename,
        decision.value,
        len(detections),
        elapsed_ms,
    )
    await broadcast(result.model_dump(mode="json"))

    return result


@router.post("/{scan_id}/feedback")
async def submit_feedback(
    scan_id: str,
    body: FeedbackRequest,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    scan = await db.get(Scan, scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan nao encontrado")

    scan.operator_id = body.operator_id
    scan.operator_feedback = body.feedback
    scan.feedback_at = datetime.utcnow()
    await db.commit()

    return {"status": "ok"}
