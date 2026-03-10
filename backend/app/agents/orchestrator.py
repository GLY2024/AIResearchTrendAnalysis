"""Orchestrator - top-level pipeline coordination."""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.analyst import analyst_agent
from app.agents.executor import executor_agent
from app.agents.planner import planner_agent
from app.agents.publisher import publisher_agent
from app.core.events import event_bus
from app.db.models import AnalysisRun, Report, SearchPlan

logger = logging.getLogger(__name__)


class Orchestrator:
    """Coordinates the full research pipeline."""

    async def run_full_pipeline(
        self,
        db: AsyncSession,
        session_id: int,
        topic: str,
        chat_history: list[dict],
    ):
        """Generate a draft plan for the current session."""
        plan_data = await planner_agent.generate_plan(topic, chat_history)

        plan = SearchPlan(
            session_id=session_id,
            plan_data=plan_data,
            status="draft",
        )
        db.add(plan)
        await db.commit()
        await db.refresh(plan)

        await event_bus.emit("plan_generated", {
            "session_id": session_id,
            "plan_id": plan.id,
            "plan": plan_data,
        })

        return plan

    async def execute_approved_plan(self, db: AsyncSession, plan: SearchPlan):
        """Execute an approved search plan through search, analysis, and report."""
        total = await executor_agent.execute_plan(plan, db)
        logger.info(f"Search complete: {total} papers found")

        for analysis_type in ["bibliometrics", "trend", "network"]:
            run = AnalysisRun(
                session_id=plan.session_id,
                analysis_type=analysis_type,
                status="pending",
            )
            db.add(run)
            await db.commit()
            await db.refresh(run)
            await analyst_agent.run_analysis(db, run)

        report = Report(
            session_id=plan.session_id,
            title="Generating...",
            status="generating",
        )
        db.add(report)
        await db.commit()
        await db.refresh(report)
        await publisher_agent.generate_report(db, report)

        return report


orchestrator = Orchestrator()
