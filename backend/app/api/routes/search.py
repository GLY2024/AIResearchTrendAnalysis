"""Search plan and execution routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.common import SearchPlanAction, SearchPlanResponse
from app.db.engine import get_session
from app.db.models import SearchPlan
from app.core.events import event_bus
from app.core.task_manager import task_manager

router = APIRouter(prefix="/search", tags=["search"])


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
        # TODO: Trigger executor agent via task_manager
        await event_bus.emit("search_plan_approved", {"plan_id": plan_id})
    elif body.action == "reject":
        plan.status = "rejected"
        await db.commit()
    else:
        raise HTTPException(400, f"Unknown action: {body.action}")

    await db.refresh(plan)
    return SearchPlanResponse.model_validate(plan)
