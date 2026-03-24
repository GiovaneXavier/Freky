from datetime import date
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
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
        query = query.where(Scan.created_at <= date_to)
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
