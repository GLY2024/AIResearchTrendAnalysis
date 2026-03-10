"""Paper CRUD routes."""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.common import PaperListResponse, PaperResponse, PaperUpdate
from app.db.engine import get_session
from app.db.models import Paper

router = APIRouter(prefix="/papers", tags=["papers"])


def _build_paper_stmt(
    session_id: int,
    included_only: bool = False,
    year_from: int | None = None,
    year_to: int | None = None,
    source: str | None = None,
    search: str | None = None,
    discovery_method: str | None = None,
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
    if discovery_method:
        stmt = stmt.where(Paper.discovery_method == discovery_method)
    if search:
        pattern = f"%{search}%"
        stmt = stmt.where(
            or_(
                Paper.title.ilike(pattern),
                Paper.abstract.ilike(pattern),
                Paper.journal.ilike(pattern),
            )
        )
    return stmt


@router.get("", response_model=PaperListResponse)
async def list_papers(
    session_id: int,
    included_only: bool = False,
    year_from: int | None = None,
    year_to: int | None = None,
    source: str | None = None,
    search: str | None = None,
    discovery_method: str | None = None,
    sort_by: str = "citation_count",
    sort_asc: bool = False,
    limit: int = Query(default=20, ge=1, le=1000),
    offset: int = 0,
    db: AsyncSession = Depends(get_session),
):
    base_stmt = _build_paper_stmt(
        session_id=session_id,
        included_only=included_only,
        year_from=year_from,
        year_to=year_to,
        source=source,
        search=search,
        discovery_method=discovery_method,
    )

    total_result = await db.execute(
        select(func.count()).select_from(base_stmt.subquery())
    )
    total = total_result.scalar() or 0

    stmt = base_stmt
    sort_col = getattr(Paper, sort_by, Paper.citation_count)
    if sort_asc:
        stmt = stmt.order_by(sort_col.asc())
    else:
        stmt = stmt.order_by(sort_col.desc())
    stmt = stmt.offset(offset).limit(limit)

    result = await db.execute(stmt)
    return PaperListResponse(
        items=[PaperResponse.model_validate(p) for p in result.scalars().all()],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/count")
async def count_papers(
    session_id: int,
    included_only: bool = False,
    year_from: int | None = None,
    year_to: int | None = None,
    source: str | None = None,
    search: str | None = None,
    discovery_method: str | None = None,
    db: AsyncSession = Depends(get_session),
):
    stmt = _build_paper_stmt(
        session_id=session_id,
        included_only=included_only,
        year_from=year_from,
        year_to=year_to,
        source=source,
        search=search,
        discovery_method=discovery_method,
    )
    result = await db.execute(
        select(func.count()).select_from(stmt.subquery())
    )
    return {"count": result.scalar() or 0}


@router.get("/sources")
async def list_sources(session_id: int, db: AsyncSession = Depends(get_session)):
    """List distinct sources and discovery methods for filter dropdowns."""
    sources_result = await db.execute(
        select(Paper.source).where(Paper.session_id == session_id).distinct()
    )
    methods_result = await db.execute(
        select(Paper.discovery_method).where(Paper.session_id == session_id).distinct()
    )
    return {
        "sources": [r[0] for r in sources_result.all() if r[0]],
        "discovery_methods": [r[0] for r in methods_result.all() if r[0]],
    }


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


class BatchUpdateRequest(BaseModel):
    paper_ids: list[int]
    is_included: bool | None = None
    notes: str | None = None


class BatchDeleteRequest(BaseModel):
    paper_ids: list[int]


@router.post("/batch-update")
async def batch_update_papers(body: BatchUpdateRequest, db: AsyncSession = Depends(get_session)):
    """Batch update multiple papers at once."""
    updated = 0
    for pid in body.paper_ids:
        paper = await db.get(Paper, pid)
        if paper:
            if body.is_included is not None:
                paper.is_included = body.is_included
            if body.notes is not None:
                paper.notes = body.notes
            updated += 1
    await db.commit()
    return {"updated": updated}


@router.post("/batch-delete")
async def batch_delete_papers(body: BatchDeleteRequest, db: AsyncSession = Depends(get_session)):
    """Batch delete multiple papers."""
    deleted = 0
    for pid in body.paper_ids:
        paper = await db.get(Paper, pid)
        if paper:
            await db.delete(paper)
            deleted += 1
    await db.commit()
    return {"deleted": deleted}


@router.delete("/{paper_id}", status_code=204)
async def delete_paper(paper_id: int, db: AsyncSession = Depends(get_session)):
    paper = await db.get(Paper, paper_id)
    if not paper:
        raise HTTPException(404, "Paper not found")
    await db.delete(paper)
    await db.commit()
