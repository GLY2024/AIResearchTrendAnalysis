"""Paper service - CRUD and deduplication."""

import logging
import re

from sqlalchemy import select, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Paper
from app.sources.base import UnifiedPaper

logger = logging.getLogger(__name__)


def _normalize_title(title: str) -> str:
    """Normalize a title for comparison: lowercase, strip punctuation, collapse whitespace."""
    title = title.lower().strip()
    title = re.sub(r'[^\w\s]', '', title)
    title = re.sub(r'\s+', ' ', title)
    return title


def _levenshtein_ratio(s1: str, s2: str) -> float:
    """Compute Levenshtein similarity ratio between two strings (0.0 to 1.0)."""
    if s1 == s2:
        return 1.0
    len1, len2 = len(s1), len(s2)
    if not len1 or not len2:
        return 0.0

    # Quick length-based rejection
    max_len = max(len1, len2)
    if abs(len1 - len2) / max_len > 0.15:
        return 0.0

    # Dynamic programming Levenshtein distance
    if len1 > len2:
        s1, s2 = s2, s1
        len1, len2 = len2, len1

    prev_row = list(range(len2 + 1))
    for i in range(1, len1 + 1):
        curr_row = [i]
        for j in range(1, len2 + 1):
            cost = 0 if s1[i - 1] == s2[j - 1] else 1
            curr_row.append(min(
                curr_row[j - 1] + 1,
                prev_row[j] + 1,
                prev_row[j - 1] + cost,
            ))
        prev_row = curr_row

    distance = prev_row[len2]
    return 1.0 - distance / max_len


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
        """Check for duplicates: DOI -> arXiv ID -> OpenAlex ID -> Scopus ID -> fuzzy title+year."""
        conditions = []

        # Exact ID matches
        if paper.doi:
            conditions.append(and_(Paper.session_id == session_id, Paper.doi == paper.doi))
        if paper.arxiv_id:
            conditions.append(and_(Paper.session_id == session_id, Paper.arxiv_id == paper.arxiv_id))
        if paper.openalex_id:
            conditions.append(and_(Paper.session_id == session_id, Paper.openalex_id == paper.openalex_id))
        if paper.scopus_id:
            conditions.append(and_(Paper.session_id == session_id, Paper.scopus_id == paper.scopus_id))

        if conditions:
            result = await db.execute(select(Paper.id).where(or_(*conditions)).limit(1))
            if result.first():
                return True

        # Fuzzy title match: exact case-insensitive first (fast DB query)
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

        # Fuzzy title match: Levenshtein for near-duplicates
        if paper.title and len(paper.title) > 20:
            normalized_new = _normalize_title(paper.title)

            # Get candidate papers with same year (or year +/- 1) for comparison
            year_cond = Paper.session_id == session_id
            if paper.year:
                year_cond = and_(
                    Paper.session_id == session_id,
                    Paper.year.between(paper.year - 1, paper.year + 1),
                )

            result = await db.execute(
                select(Paper.title, Paper.year).where(year_cond).limit(500)
            )
            candidates = result.all()

            for (cand_title, cand_year) in candidates:
                normalized_cand = _normalize_title(cand_title)
                ratio = _levenshtein_ratio(normalized_new, normalized_cand)
                if ratio > 0.92:
                    return True

        return False


paper_service = PaperService()
