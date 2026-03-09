"""Analysis routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.common import AnalysisRequest, AnalysisResponse
from app.db.engine import get_session
from app.db.models import AnalysisRun

router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.get("", response_model=list[AnalysisResponse])
async def list_analyses(session_id: int, db: AsyncSession = Depends(get_session)):
    result = await db.execute(
        select(AnalysisRun)
        .where(AnalysisRun.session_id == session_id)
        .order_by(AnalysisRun.created_at.desc())
    )
    return [AnalysisResponse.model_validate(a) for a in result.scalars().all()]


@router.post("", response_model=AnalysisResponse, status_code=201)
async def create_analysis(body: AnalysisRequest, db: AsyncSession = Depends(get_session)):
    run = AnalysisRun(
        session_id=body.session_id,
        analysis_type=body.analysis_type,
        params=body.params,
        status="pending",
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)
    # TODO: Trigger analysis via task_manager
    return AnalysisResponse.model_validate(run)


@router.get("/{run_id}", response_model=AnalysisResponse)
async def get_analysis(run_id: int, db: AsyncSession = Depends(get_session)):
    run = await db.get(AnalysisRun, run_id)
    if not run:
        raise HTTPException(404, "Analysis run not found")
    return AnalysisResponse.model_validate(run)
