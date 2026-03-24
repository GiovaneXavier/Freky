from datetime import date, datetime, timedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, String, cast
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import get_db
from models.scan import Scan
from schemas.scan import ScanListItem

router = APIRouter()


@router.get("/", response_model=list[ScanListItem])
async def list_scans(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    date_from: date | None = None,
    date_to: date | None = None,
    decision: str | None = None,
    db: AsyncSession = Depends(get_db),
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
async def stats(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Scan.decision, func.count(Scan.id))
        .group_by(Scan.decision)
    )
    counts = {row[0]: row[1] for row in result.all()}
    total = sum(counts.values())

    return {
        "total": total,
        "by_decision": counts,
    }


@router.get("/daily")
async def daily_stats(
    days: int = Query(14, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
):
    """
    Retorna contagem de scans por dia e por decisao para os ultimos N dias.
    Formato: [{ date: "2026-03-10", LIBERADO: 30, VERIFICAR: 5, INCONCLUSIVO: 2 }, ...]

    Usa func.date() para truncar o datetime para data, compativel com SQLite e PostgreSQL.
    O resultado e coercido para String para evitar problemas de type mapping no SQLite.
    """
    since = datetime.utcnow().date() - timedelta(days=days - 1)

    result = await db.execute(
        select(
            cast(func.date(Scan.created_at), String).label("day"),
            Scan.decision,
            func.count(Scan.id).label("count"),
        )
        .where(Scan.created_at >= since)
        .group_by("day", Scan.decision)
        .order_by("day")
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

    return list(data.values())
