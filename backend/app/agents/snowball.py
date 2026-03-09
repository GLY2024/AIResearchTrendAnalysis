"""Snowball Agent - citation chain discovery."""

import logging

from sqlalchemy import select
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
        visited_openalex_ids: set[str] = set()

        # Get seed papers from DB
        current_papers: list[Paper] = []
        for pid in seed_paper_ids:
            paper = await db.get(Paper, pid)
            if paper and paper.openalex_id:
                current_papers.append(paper)

        source = source_registry.get("openalex")
        if not source:
            logger.warning("OpenAlex source not available for snowball")
            return 0

        for hop in range(max_hops):
            next_papers: list[Paper] = []

            for paper in current_papers:
                if paper.openalex_id in visited_openalex_ids:
                    continue
                visited_openalex_ids.add(paper.openalex_id)

                for direction in directions:
                    try:
                        if direction == "forward":
                            related = await source.get_citations(paper.openalex_id)
                        else:
                            related = await source.get_references(paper.openalex_id)
                    except Exception as e:
                        logger.error(f"Snowball {direction} error for {paper.openalex_id}: {e}")
                        continue

                    # Filter by citation threshold (forward only)
                    if direction == "forward":
                        related = [r for r in related if r.citation_count >= min_citation_threshold]

                    # Save new papers
                    saved_count = await paper_service.save_papers(
                        db, session_id, related,
                        discovery_method=f"{direction}_snowball",
                    )
                    total_new += saved_count

                    # Record citation relationships
                    await self._record_citations(
                        db, paper, related, direction, session_id,
                    )

                    # Collect newly saved papers for next hop
                    if hop < max_hops - 1:
                        for up in related:
                            if up.openalex_id and up.openalex_id not in visited_openalex_ids:
                                # Find the DB paper we just saved
                                result = await db.execute(
                                    select(Paper).where(
                                        Paper.session_id == session_id,
                                        Paper.openalex_id == up.openalex_id,
                                    ).limit(1)
                                )
                                db_paper = result.scalar_one_or_none()
                                if db_paper:
                                    next_papers.append(db_paper)

                    await event_bus.emit("snowball_progress", {
                        "session_id": session_id,
                        "hop": hop + 1,
                        "max_hops": max_hops,
                        "direction": direction,
                        "paper_title": paper.title[:80],
                        "new_found": saved_count,
                        "total_new": total_new,
                    })

            current_papers = next_papers
            if not current_papers:
                break

        await event_bus.emit("snowball_complete", {
            "session_id": session_id,
            "total_new": total_new,
        })

        return total_new

    async def _record_citations(
        self,
        db: AsyncSession,
        source_paper: Paper,
        related_papers: list,
        direction: str,
        session_id: int,
    ):
        """Record citation relationships in the paper_citations table."""
        for up in related_papers:
            # Find the related paper in DB by identifier
            related_db = None
            if up.openalex_id:
                result = await db.execute(
                    select(Paper).where(
                        Paper.session_id == session_id,
                        Paper.openalex_id == up.openalex_id,
                    ).limit(1)
                )
                related_db = result.scalar_one_or_none()

            if not related_db:
                continue

            # Determine citing/cited direction
            if direction == "forward":
                # related paper cites source paper
                citing_id = related_db.id
                cited_id = source_paper.id
            else:
                # source paper cites related paper
                citing_id = source_paper.id
                cited_id = related_db.id

            # Check if citation already exists
            existing = await db.execute(
                select(PaperCitation).where(
                    PaperCitation.citing_paper_id == citing_id,
                    PaperCitation.cited_paper_id == cited_id,
                ).limit(1)
            )
            if existing.scalar_one_or_none():
                continue

            citation = PaperCitation(
                citing_paper_id=citing_id,
                cited_paper_id=cited_id,
            )
            db.add(citation)

        try:
            await db.commit()
        except Exception as e:
            logger.warning(f"Citation recording error: {e}")
            await db.rollback()


snowball_agent = SnowballAgent()
