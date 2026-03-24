import time
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import get_db
from models.scan import Scan
from schemas.scan import ScanResult, FeedbackRequest
from core.settings import settings
from routes.websocket import broadcast

router = APIRouter()


@router.post("/", response_model=ScanResult)
async def process_scan(
    request: Request,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Recebe uma imagem (chamado pelo watcher apos Xport depositar o arquivo)
    e executa a deteccao.
    """
    archive_dir = Path(settings.scan_archive_dir)
    archive_dir.mkdir(parents=True, exist_ok=True)
    image_path = archive_dir / file.filename

    content = await file.read()
    image_path.write_bytes(content)

    start = time.monotonic()
    decision, detections = request.app.state.detector.predict(str(image_path))
    elapsed_ms = (time.monotonic() - start) * 1000

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

    result = ScanResult.model_validate(scan)
    await broadcast(result.model_dump(mode="json"))

    return result


@router.post("/{scan_id}/feedback")
async def submit_feedback(
    scan_id: str,
    body: FeedbackRequest,
    db: AsyncSession = Depends(get_db),
):
    scan = await db.get(Scan, scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan nao encontrado")

    scan.operator_id = body.operator_id
    scan.operator_feedback = body.feedback
    scan.feedback_at = datetime.utcnow()
    await db.commit()

    return {"status": "ok"}
