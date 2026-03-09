"""Executor Agent - executes search plans using function calling."""

import logging
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import event_bus
from app.db.models import Paper, SearchExecution, SearchPlan
from app.services.paper_service import paper_service
from app.sources.registry import source_registry

logger = logging.getLogger(__name__)


class ExecutorAgent:
    """Executes approved search plans against data sources."""

    async def execute_plan(self, plan: SearchPlan, db: AsyncSession):
        """Execute all queries in a search plan."""
        plan_data = plan.plan_data
        queries = plan_data.get("queries", [])
        year_from = plan_data.get("year_range", {}).get("from")
        year_to = plan_data.get("year_range", {}).get("to")
        max_results = plan_data.get("max_results_per_query", 100)

        plan.status = "executing"
        await db.commit()

        total_found = 0
        for i, q in enumerate(queries):
            query_str = q.get("query", "")
            source_name = q.get("source", "openalex")
            source = source_registry.get(source_name)

            if not source:
                logger.warning(f"Source {source_name} not found, skipping")
                continue

            # Create execution record
            execution = SearchExecution(
                plan_id=plan.id,
                source_name=source_name,
                query=query_str,
                params={"year_from": year_from, "year_to": year_to, "max_results": max_results},
                status="running",
                started_at=datetime.utcnow(),
            )
            db.add(execution)
            await db.commit()

            await event_bus.emit("search_progress", {
                "plan_id": plan.id,
                "query_index": i,
                "total_queries": len(queries),
                "source": source_name,
                "query": query_str,
                "status": "running",
            })

            try:
                results = await source.search(
                    query=query_str,
                    max_results=max_results,
                    year_from=year_from,
                    year_to=year_to,
                )

                # Save papers with deduplication
                saved = await paper_service.save_papers(
                    db, plan.session_id, results, discovery_method="search"
                )

                execution.results_count = saved
                execution.status = "completed"
                execution.completed_at = datetime.utcnow()
                total_found += saved

            except Exception as e:
                logger.error(f"Search execution failed: {e}")
                execution.status = "failed"
                execution.error_message = str(e)
                execution.completed_at = datetime.utcnow()

            await db.commit()

            await event_bus.emit("search_progress", {
                "plan_id": plan.id,
                "query_index": i,
                "total_queries": len(queries),
                "source": source_name,
                "query": query_str,
                "status": execution.status,
                "results_count": execution.results_count,
                "total_found": total_found,
            })

        plan.status = "completed"
        await db.commit()

        await event_bus.emit("search_complete", {
            "plan_id": plan.id,
            "total_papers": total_found,
        })

        return total_found


executor_agent = ExecutorAgent()
