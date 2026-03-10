"""Search plan and execution routes."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.common import SearchPlanAction, SearchPlanResponse
from app.db.engine import async_session, get_session
from app.db.models import SearchPlan
from app.core.events import event_bus
from app.core.task_manager import task_manager
from app.agents.executor import executor_agent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/search", tags=["search"])


def _disable_snowball(plan_data: dict | None) -> dict | None:
    if not isinstance(plan_data, dict):
        return plan_data
    next_plan = dict(plan_data)
    snowball = dict(next_plan.get("snowball_config") or {})
    snowball["enabled"] = False
    next_plan["snowball_config"] = snowball
    return next_plan


async def _run_search_pipeline(plan_id: int):
    """Background task: execute search plan."""
    async with async_session() as db:
        plan = await db.get(SearchPlan, plan_id)
        if not plan:
            return

        try:
            total = await executor_agent.execute_plan(plan, db)
            logger.info(f"Search plan {plan_id} completed: {total} papers")

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
        plan.plan_data = _disable_snowball(plan.plan_data)
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
        plan.plan_data = _disable_snowball(body.plan_data)
        plan.status = "draft"
        await db.commit()
        await event_bus.emit("search_plan_modified", {"plan_id": plan_id}, session_id=str(plan.session_id))
    else:
        raise HTTPException(400, f"Unknown action: {body.action}")

    await db.refresh(plan)
    return SearchPlanResponse.model_validate(plan)


@router.get("/snowball-runs", include_in_schema=False)
async def list_snowball_runs(session_id: int, db: AsyncSession = Depends(get_session)):
    return []


@router.get("/snowball-runs/{run_id}", include_in_schema=False)
async def get_snowball_run(run_id: int, db: AsyncSession = Depends(get_session)):
    raise HTTPException(410, "Snowball is disabled")


@router.get("/snowball-runs/{run_id}/candidates", include_in_schema=False)
async def list_snowball_candidates(run_id: int, db: AsyncSession = Depends(get_session)):
    return []


@router.post("/snowball-runs/{run_id}/action", include_in_schema=False)
async def snowball_action(run_id: int, db: AsyncSession = Depends(get_session)):
    raise HTTPException(410, "Snowball is disabled")
