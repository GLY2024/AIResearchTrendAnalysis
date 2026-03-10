"""Search plan and execution routes."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.common import SearchPlanAction, SearchPlanResponse
from app.db.engine import async_session, get_session
from app.db.models import SearchPlan, SnowballCandidate, SnowballRun
from app.core.events import event_bus
from app.core.task_manager import task_manager
from app.agents.executor import executor_agent
from app.agents.snowball import snowball_agent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/search", tags=["search"])


async def _run_search_pipeline(plan_id: int):
    """Background task: execute search plan + optional snowball."""
    async with async_session() as db:
        plan = await db.get(SearchPlan, plan_id)
        if not plan:
            return

        try:
            total = await executor_agent.execute_plan(plan, db)
            logger.info(f"Search plan {plan_id} completed: {total} papers")

            # Create a snowball proposal after the main search completes.
            if total > 0:
                proposal = await snowball_agent.create_proposal(db, plan)
                if proposal:
                    logger.info(f"Snowball proposal created for plan {plan_id}: run {proposal.id}")

        except Exception as e:
            logger.error(f"Search pipeline failed for plan {plan_id}: {e}")
            plan.status = "failed"
            await db.commit()
            await event_bus.emit("error", {
                "message": f"Search failed: {e}", "plan_id": plan_id,
            }, session_id=str(plan.session_id))


@router.get("/plans", response_model=list[SearchPlanResponse])
async def list_plans(session_id: int, db: AsyncSession = Depends(get_session)):
    result = await db.execute(
        select(SearchPlan)
        .where(SearchPlan.session_id == session_id)
        .order_by(SearchPlan.created_at.desc())
    )
    return [SearchPlanResponse.model_validate(p) for p in result.scalars().all()]


@router.get("/plans/{plan_id}", response_model=SearchPlanResponse)
async def get_plan(plan_id: int, db: AsyncSession = Depends(get_session)):
    plan = await db.get(SearchPlan, plan_id)
    if not plan:
        raise HTTPException(404, "Search plan not found")
    return SearchPlanResponse.model_validate(plan)


@router.post("/plans/{plan_id}/action", response_model=SearchPlanResponse)
async def plan_action(plan_id: int, body: SearchPlanAction, db: AsyncSession = Depends(get_session)):
    plan = await db.get(SearchPlan, plan_id)
    if not plan:
        raise HTTPException(404, "Search plan not found")

    if body.action == "approve":
        plan.status = "approved"
        await db.commit()
        task_manager.submit(_run_search_pipeline(plan_id), task_id=f"search-{plan_id}")
        await event_bus.emit("search_plan_approved", {"plan_id": plan_id})
    elif body.action == "reject":
        plan.status = "rejected"
        await db.commit()
        await event_bus.emit("search_plan_rejected", {"plan_id": plan_id}, session_id=str(plan.session_id))
    elif body.action == "modify":
        if body.plan_data is None:
            raise HTTPException(400, "plan_data is required for modify")
        plan.plan_data = body.plan_data
        plan.status = "draft"
        await db.commit()
        await event_bus.emit("search_plan_modified", {"plan_id": plan_id}, session_id=str(plan.session_id))
    else:
        raise HTTPException(400, f"Unknown action: {body.action}")

    await db.refresh(plan)
    return SearchPlanResponse.model_validate(plan)


class SnowballRunResponse(BaseModel):
    id: int
    session_id: int
    plan_id: int
    status: str
    config: dict
    proposal_summary: dict
    stats: dict
    created_at: str
    updated_at: str


class SnowballCandidateResponse(BaseModel):
    id: int
    run_id: int
    seed_paper_id: int | None
    direction: str
    hop: int
    title: str
    year: int | None
    citation_count: int
    source_name: str
    relevance_score: float | None
    relevance_reason: str
    verification_status: str
    verification_sources: list
    status: str


class SnowballActionRequest(BaseModel):
    action: str
    config: dict | None = None
    candidate_ids: list[int] | None = None


def _serialize_snowball_run(run: SnowballRun) -> SnowballRunResponse:
    return SnowballRunResponse(
        id=run.id,
        session_id=run.session_id,
        plan_id=run.plan_id,
        status=run.status,
        config=run.config or {},
        proposal_summary=run.proposal_summary or {},
        stats=run.stats or {},
        created_at=run.created_at.isoformat(),
        updated_at=run.updated_at.isoformat(),
    )


def _serialize_snowball_candidate(candidate: SnowballCandidate) -> SnowballCandidateResponse:
    return SnowballCandidateResponse(
        id=candidate.id,
        run_id=candidate.run_id,
        seed_paper_id=candidate.seed_paper_id,
        direction=candidate.direction,
        hop=candidate.hop,
        title=candidate.title,
        year=candidate.year,
        citation_count=candidate.citation_count,
        source_name=candidate.source_name,
        relevance_score=candidate.relevance_score,
        relevance_reason=candidate.relevance_reason,
        verification_status=candidate.verification_status,
        verification_sources=candidate.verification_sources or [],
        status=candidate.status,
    )


@router.get("/snowball-runs", response_model=list[SnowballRunResponse])
async def list_snowball_runs(session_id: int, db: AsyncSession = Depends(get_session)):
    result = await db.execute(
        select(SnowballRun)
        .where(SnowballRun.session_id == session_id)
        .order_by(SnowballRun.created_at.desc())
    )
    return [_serialize_snowball_run(run) for run in result.scalars().all()]


@router.get("/snowball-runs/{run_id}", response_model=SnowballRunResponse)
async def get_snowball_run(run_id: int, db: AsyncSession = Depends(get_session)):
    run = await db.get(SnowballRun, run_id)
    if not run:
        raise HTTPException(404, "Snowball run not found")
    return _serialize_snowball_run(run)


@router.get("/snowball-runs/{run_id}/candidates", response_model=list[SnowballCandidateResponse])
async def list_snowball_candidates(
    run_id: int,
    status: str | None = Query(default=None),
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    db: AsyncSession = Depends(get_session),
):
    stmt = select(SnowballCandidate).where(SnowballCandidate.run_id == run_id)
    if status:
        stmt = stmt.where(SnowballCandidate.status == status)
    stmt = stmt.order_by(
        SnowballCandidate.relevance_score.desc().nullslast(),
        SnowballCandidate.citation_count.desc(),
    ).offset(offset).limit(limit)
    result = await db.execute(stmt)
    return [_serialize_snowball_candidate(candidate) for candidate in result.scalars().all()]


async def _run_snowball_action(run_id: int, action: str, config: dict | None, candidate_ids: list[int] | None):
    async with async_session() as db:
        run = await db.get(SnowballRun, run_id)
        if not run:
            return
        try:
            await snowball_agent.apply_action(db, run, action, config_updates=config, candidate_ids=candidate_ids)
        except Exception as exc:
            logger.error(f"Snowball action failed for run {run_id}: {exc}")
            run.status = "failed"
            await db.commit()
            await event_bus.emit("error", {
                "message": f"Snowball failed: {exc}",
                "run_id": run_id,
            }, session_id=str(run.session_id))


@router.post("/snowball-runs/{run_id}/action", response_model=SnowballRunResponse)
async def snowball_action(run_id: int, body: SnowballActionRequest, db: AsyncSession = Depends(get_session)):
    run = await db.get(SnowballRun, run_id)
    if not run:
        raise HTTPException(404, "Snowball run not found")

    if body.action == "reject":
        updated = await snowball_agent.apply_action(db, run, body.action, body.config, body.candidate_ids)
        await db.refresh(updated)
        return _serialize_snowball_run(updated)

    task_manager.submit(
        _run_snowball_action(run_id, body.action, body.config, body.candidate_ids),
        task_id=f"snowball-{run_id}-{body.action}",
    )
    return _serialize_snowball_run(run)
