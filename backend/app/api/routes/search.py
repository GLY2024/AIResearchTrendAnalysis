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

            # Run snowball if configured
            snowball_config = plan.plan_data.get("snowball_config", {})
            if snowball_config.get("enabled", False) and total > 0:
                from app.db.models import Paper
                result = await db.execute(
                    select(Paper.id)
                    .where(Paper.session_id == plan.session_id)
                    .order_by(Paper.citation_count.desc())
                    .limit(10)
                )
                seed_ids = [r[0] for r in result.all()]
                if seed_ids:
                    new_papers = await snowball_agent.snowball(
                        db, plan.session_id, seed_ids,
                        max_hops=snowball_config.get("max_hops", 2),
                        directions=snowball_config.get("directions", ["forward", "backward"]),
                        min_citation_threshold=snowball_config.get("min_citation_threshold", 5),
                    )
                    logger.info(f"Snowball for plan {plan_id}: {new_papers} new papers")

        except Exception as e:
            logger.error(f"Search pipeline failed for plan {plan_id}: {e}")
            plan.status = "failed"
            await db.commit()
            await event_bus.emit("error", {
                "message": f"Search failed: {e}", "plan_id": plan_id,
            })


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
    else:
        raise HTTPException(400, f"Unknown action: {body.action}")

    await db.refresh(plan)
    return SearchPlanResponse.model_validate(plan)
