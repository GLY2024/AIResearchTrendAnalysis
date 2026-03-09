"""Analysis routes."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.common import AnalysisRequest, AnalysisResponse
from app.db.engine import async_session, get_session
from app.db.models import AnalysisRun
from app.core.task_manager import task_manager
from app.agents.analyst import analyst_agent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analysis", tags=["analysis"])


async def _run_analysis(run_id: int):
    """Background task: run analysis."""
    async with async_session() as db:
        run = await db.get(AnalysisRun, run_id)
        if not run:
            return
        try:
            await analyst_agent.run_analysis(db, run)
            logger.info(f"Analysis {run_id} completed")
        except Exception as e:
            logger.error(f"Analysis {run_id} failed: {e}")
            run.status = "failed"
            run.results = {"error": str(e)}
            await db.commit()


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
    task_manager.submit(_run_analysis(run.id), task_id=f"analysis-{run.id}")
    return AnalysisResponse.model_validate(run)


@router.get("/{run_id}", response_model=AnalysisResponse)
async def get_analysis(run_id: int, db: AsyncSession = Depends(get_session)):
    run = await db.get(AnalysisRun, run_id)
    if not run:
        raise HTTPException(404, "Analysis run not found")
    return AnalysisResponse.model_validate(run)
