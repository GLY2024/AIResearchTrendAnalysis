"""Analysis routes."""

import hashlib
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.common import AnalysisRequest, AnalysisResponse
from app.db.engine import async_session, get_session
from app.db.models import AnalysisRun, Paper
from app.core.task_manager import task_manager
from app.agents.analyst import analyst_agent
from app.services.corpus_scope import primary_corpus_clause

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analysis", tags=["analysis"])


async def _compute_corpus_signature(db: AsyncSession, session_id: int) -> tuple[str, int]:
    result = await db.execute(
        select(Paper.id, Paper.updated_at)
        .where(Paper.session_id == session_id)
        .where(Paper.is_included == True)
        .where(primary_corpus_clause())
        .order_by(Paper.id)
    )
    rows = result.all()
    digest = hashlib.sha1()
    for paper_id, updated_at in rows:
        digest.update(f"{paper_id}:{updated_at.isoformat() if updated_at else ''}|".encode("utf-8"))
    return digest.hexdigest(), len(rows)


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
    corpus_signature, corpus_size = await _compute_corpus_signature(db, body.session_id)
    if corpus_size == 0:
        raise HTTPException(400, "No included papers are currently selected for analysis")

    existing_result = await db.execute(
        select(AnalysisRun)
        .where(AnalysisRun.session_id == body.session_id)
        .where(AnalysisRun.analysis_type == body.analysis_type)
        .where(AnalysisRun.status.in_(["pending", "running", "completed"]))
        .order_by(AnalysisRun.created_at.desc())
    )
    existing_runs = existing_result.scalars().all()
    for existing in existing_runs:
        params = existing.params or {}
        if params.get("corpus_signature") == corpus_signature:
            raise HTTPException(
                409,
                detail={
                    "message": "This analysis has already been run for the current paper selection.",
                    "existing_run_id": existing.id,
                    "existing_status": existing.status,
                    "analysis_type": existing.analysis_type,
                },
            )

    params = dict(body.params or {})
    params["corpus_signature"] = corpus_signature
    params["corpus_size"] = corpus_size
    run = AnalysisRun(
        session_id=body.session_id,
        analysis_type=body.analysis_type,
        params=params,
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
