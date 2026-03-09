"""Snowball Agent - citation chain discovery."""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import event_bus
from app.db.models import Paper, PaperCitation
from app.services.paper_service import paper_service
from app.sources.registry import source_registry

logger = logging.getLogger(__name__)


class SnowballAgent:
    """Performs forward and backward snowball sampling via citation chains."""

    async def snowball(
        self,
        db: AsyncSession,
        session_id: int,
        seed_paper_ids: list[int],
        max_hops: int = 2,
        directions: list[str] | None = None,
        min_citation_threshold: int = 5,
    ) -> int:
        """Execute snowball sampling from seed papers.

        Returns total number of new papers discovered.
        """
        if directions is None:
            directions = ["forward", "backward"]

        total_new = 0
        visited = set()

        # Get seed papers from DB
        current_papers = []
        for pid in seed_paper_ids:
            paper = await db.get(Paper, pid)
            if paper and paper.openalex_id:
                current_papers.append(paper)

        for hop in range(max_hops):
            next_papers = []

            for paper in current_papers:
                if paper.openalex_id in visited:
                    continue
                visited.add(paper.openalex_id)

                for direction in directions:
                    source = source_registry.get("openalex")
                    if not source:
                        continue

                    try:
                        if direction == "forward":
                            related = await source.get_citations(paper.openalex_id)
                        else:
                            related = await source.get_references(paper.openalex_id)
                    except Exception as e:
                        logger.error(f"Snowball {direction} error: {e}")
                        continue

                    # Filter by citation threshold
                    if direction == "forward":
                        related = [r for r in related if r.citation_count >= min_citation_threshold]

                    # Save new papers
                    saved = await paper_service.save_papers(
                        db, session_id, related,
                        discovery_method=f"{direction}_snowball",
                    )
                    total_new += saved

                    await event_bus.emit("snowball_progress", {
                        "session_id": session_id,
                        "hop": hop + 1,
                        "direction": direction,
                        "paper_title": paper.title[:80],
                        "new_found": saved,
                        "total_new": total_new,
                    })

            # Get newly added papers for next hop
            # (simplified - in production would track exact new additions)
            if hop < max_hops - 1:
                current_papers = next_papers

        return total_new


snowball_agent = SnowballAgent()
