"""Paper CRUD routes."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.common import PaperResponse, PaperUpdate
from app.db.engine import get_session
from app.db.models import Paper

router = APIRouter(prefix="/papers", tags=["papers"])


@router.get("", response_model=list[PaperResponse])
async def list_papers(
    session_id: int,
    included_only: bool = False,
    year_from: int | None = None,
    year_to: int | None = None,
    source: str | None = None,
    sort_by: str = "citation_count",
    limit: int = Query(default=100, le=500),
    offset: int = 0,
    db: AsyncSession = Depends(get_session),
):
    stmt = select(Paper).where(Paper.session_id == session_id)
    if included_only:
        stmt = stmt.where(Paper.is_included == True)
    if year_from:
        stmt = stmt.where(Paper.year >= year_from)
    if year_to:
        stmt = stmt.where(Paper.year <= year_to)
    if source:
        stmt = stmt.where(Paper.source == source)

    sort_col = getattr(Paper, sort_by, Paper.citation_count)
    stmt = stmt.order_by(sort_col.desc()).offset(offset).limit(limit)

    result = await db.execute(stmt)
    return [PaperResponse.model_validate(p) for p in result.scalars().all()]


@router.get("/count")
async def count_papers(session_id: int, db: AsyncSession = Depends(get_session)):
    result = await db.execute(
        select(func.count()).where(Paper.session_id == session_id)
    )
    return {"count": result.scalar() or 0}


@router.get("/{paper_id}", response_model=PaperResponse)
async def get_paper(paper_id: int, db: AsyncSession = Depends(get_session)):
    paper = await db.get(Paper, paper_id)
    if not paper:
        raise HTTPException(404, "Paper not found")
    return PaperResponse.model_validate(paper)


@router.patch("/{paper_id}", response_model=PaperResponse)
async def update_paper(paper_id: int, body: PaperUpdate, db: AsyncSession = Depends(get_session)):
    paper = await db.get(Paper, paper_id)
    if not paper:
        raise HTTPException(404, "Paper not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(paper, field, value)
    await db.commit()
    await db.refresh(paper)
    return PaperResponse.model_validate(paper)


@router.delete("/{paper_id}", status_code=204)
async def delete_paper(paper_id: int, db: AsyncSession = Depends(get_session)):
    paper = await db.get(Paper, paper_id)
    if not paper:
        raise HTTPException(404, "Paper not found")
    await db.delete(paper)
    await db.commit()
