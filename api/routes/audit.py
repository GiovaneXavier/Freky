import csv
import io
from datetime import date, datetime, timedelta
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import get_db
from models.scan import Scan
from schemas.scan import ScanListItem
from core.auth import get_current_user
from core.cache import cache_get, cache_set

router = APIRouter()


@router.get("/", response_model=list[ScanListItem])
async def list_scans(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    date_from: date | None = None,
    date_to: date | None = None,
    decision: str | None = None,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    query = select(Scan).order_by(Scan.created_at.desc())

    if date_from:
        query = query.where(Scan.created_at >= date_from)
    if date_to:
        # Inclui todo o dia: compara com o inicio do dia seguinte
        query = query.where(Scan.created_at < date_to + timedelta(days=1))
    if decision:
        query = query.where(Scan.decision == decision)

    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/stats")
async def stats(db: AsyncSession = Depends(get_db), _user: dict = Depends(get_current_user)):
    cache_key = "audit:stats"
    cached = await cache_get(cache_key)
    if cached is not None:
        return cached

    result = await db.execute(
        select(Scan.decision, func.count(Scan.id))
        .group_by(Scan.decision)
    )
    counts = {row[0]: row[1] for row in result.all()}
    total = sum(counts.values())

    data = {"total": total, "by_decision": counts}
    await cache_set(cache_key, data, ttl_seconds=300)
    return data


@router.get("/daily")
async def daily_stats(
    days: int = Query(14, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """
    Retorna contagem de scans por dia e por decisao para os ultimos N dias.
    Formato: [{ date: "2026-03-10", LIBERADO: 30, VERIFICAR: 5, INCONCLUSIVO: 2 }, ...]

    Usa cast(..., Date) do SQLAlchemy — compativel com SQL Server, PostgreSQL e SQLite.
    """
    cache_key = f"audit:daily:{days}"
    cached = await cache_get(cache_key)
    if cached is not None:
        return cached

    since = datetime.utcnow().date() - timedelta(days=days - 1)

    day_expr = func.date(Scan.created_at)
    result = await db.execute(
        select(
            day_expr.label("day"),
            Scan.decision,
            func.count(Scan.id).label("count"),
        )
        .where(Scan.created_at >= since)
        .group_by(day_expr, Scan.decision)
        .order_by(day_expr)
    )
    rows = result.all()

    decisions = ["LIBERADO", "VERIFICAR", "INCONCLUSIVO"]
    data: dict[str, dict] = {}

    for i in range(days):
        day = (since + timedelta(days=i)).isoformat()
        data[day] = {"date": day, "LIBERADO": 0, "VERIFICAR": 0, "INCONCLUSIVO": 0}

    for row in rows:
        day_str = str(row.day)[:10]  # "2026-03-24" (trunca hora se vier junto)
        if day_str in data and row.decision in decisions:
            data[day_str][row.decision] = row.count

    result_list = list(data.values())
    await cache_set(cache_key, result_list, ttl_seconds=300)
    return result_list


@router.get("/export")
async def export_scans(
    date_from: date | None = None,
    date_to: date | None = None,
    decision: str | None = None,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """Exporta scans filtrados como CSV."""
    query = select(Scan).order_by(Scan.created_at.desc())

    if date_from:
        query = query.where(Scan.created_at >= date_from)
    if date_to:
        query = query.where(Scan.created_at < date_to + timedelta(days=1))
    if decision:
        query = query.where(Scan.decision == decision)

    result = await db.execute(query)
    scans = result.scalars().all()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "id", "created_at", "filename", "decision",
        "processing_time_ms", "operator_id", "operator_feedback", "feedback_at",
    ])
    for s in scans:
        writer.writerow([
            s.id,
            s.created_at.isoformat() if s.created_at else "",
            s.filename,
            s.decision,
            f"{s.processing_time_ms:.1f}" if s.processing_time_ms is not None else "",
            s.operator_id or "",
            s.operator_feedback or "",
            s.feedback_at.isoformat() if s.feedback_at else "",
        ])

    buf.seek(0)
    filename = f"freky_scans_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    return StreamingResponse(
        buf,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
