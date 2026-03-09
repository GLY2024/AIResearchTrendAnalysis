"""Paper service - CRUD and deduplication."""

import logging

from sqlalchemy import select, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Paper
from app.sources.base import UnifiedPaper

logger = logging.getLogger(__name__)


class PaperService:
    """Paper management with deduplication."""

    async def save_papers(
        self,
        db: AsyncSession,
        session_id: int,
        papers: list[UnifiedPaper],
        discovery_method: str = "search",
    ) -> int:
        """Save papers with deduplication. Returns number of new papers saved."""
        saved = 0
        for up in papers:
            if await self._is_duplicate(db, session_id, up):
                continue

            paper = Paper(
                session_id=session_id,
                doi=up.doi or None,
                arxiv_id=up.arxiv_id or None,
                openalex_id=up.openalex_id or None,
                scopus_id=up.scopus_id or None,
                title=up.title,
                abstract=up.abstract,
                authors=up.authors,
                journal=up.journal,
                year=up.year,
                publication_date=up.publication_date,
                volume=up.volume,
                issue=up.issue,
                pages=up.pages,
                url=up.url,
                pdf_url=up.pdf_url,
                citation_count=up.citation_count,
                reference_count=up.reference_count,
                keywords=up.keywords,
                fields=up.fields,
                paper_type=up.paper_type,
                source=up.source_name,
                discovery_method=discovery_method,
            )
            db.add(paper)
            saved += 1

        if saved:
            await db.commit()
        return saved

    async def _is_duplicate(
        self,
        db: AsyncSession,
        session_id: int,
        paper: UnifiedPaper,
    ) -> bool:
        """Check for duplicates using DOI → arXiv ID → OpenAlex ID → fuzzy title."""
        conditions = []

        # Exact ID matches
        if paper.doi:
            conditions.append(and_(Paper.session_id == session_id, Paper.doi == paper.doi))
        if paper.arxiv_id:
            conditions.append(and_(Paper.session_id == session_id, Paper.arxiv_id == paper.arxiv_id))
        if paper.openalex_id:
            conditions.append(and_(Paper.session_id == session_id, Paper.openalex_id == paper.openalex_id))

        if conditions:
            result = await db.execute(select(Paper.id).where(or_(*conditions)).limit(1))
            if result.first():
                return True

        # Fuzzy title match (exact match for SQLite - Levenshtein would need extension)
        if paper.title and paper.year:
            result = await db.execute(
                select(Paper.id).where(
                    and_(
                        Paper.session_id == session_id,
                        func.lower(Paper.title) == paper.title.lower(),
                        Paper.year == paper.year,
                    )
                ).limit(1)
            )
            if result.first():
                return True

        return False


paper_service = PaperService()
