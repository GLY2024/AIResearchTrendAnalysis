"""Export service - Zotero, RIS, BibTeX."""

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Paper
from app.services.corpus_scope import primary_corpus_clause

logger = logging.getLogger(__name__)


class ExportService:
    """Export papers to various formats."""

    async def export_ris(self, db: AsyncSession, session_id: int) -> str:
        """Export papers in RIS format."""
        papers = await self._get_papers(db, session_id)
        lines = []
        for p in papers:
            lines.append("TY  - JOUR")
            lines.append(f"TI  - {p.title}")
            for a in (p.authors or []):
                lines.append(f"AU  - {a.get('name', '')}")
            if p.journal:
                lines.append(f"JO  - {p.journal}")
            if p.year:
                lines.append(f"PY  - {p.year}")
            if p.doi:
                lines.append(f"DO  - {p.doi}")
            if p.abstract:
                lines.append(f"AB  - {p.abstract}")
            if p.url:
                lines.append(f"UR  - {p.url}")
            if p.keywords:
                for kw in p.keywords:
                    lines.append(f"KW  - {kw}")
            if p.volume:
                lines.append(f"VL  - {p.volume}")
            if p.issue:
                lines.append(f"IS  - {p.issue}")
            if p.pages:
                lines.append(f"SP  - {p.pages}")
            lines.append("ER  - ")
            lines.append("")
        return "\n".join(lines)

    async def export_bibtex(self, db: AsyncSession, session_id: int) -> str:
        """Export papers in BibTeX format."""
        papers = await self._get_papers(db, session_id)
        entries = []
        for i, p in enumerate(papers):
            # Generate citation key
            first_author = ""
            if p.authors:
                first_author = p.authors[0].get("name", "").split()[-1].lower()
            key = f"{first_author}{p.year or ''}_{i}"

            entry = f"@article{{{key},\n"
            entry += f"  title = {{{p.title}}},\n"
            if p.authors:
                authors_str = " and ".join(a.get("name", "") for a in p.authors)
                entry += f"  author = {{{authors_str}}},\n"
            if p.journal:
                entry += f"  journal = {{{p.journal}}},\n"
            if p.year:
                entry += f"  year = {{{p.year}}},\n"
            if p.volume:
                entry += f"  volume = {{{p.volume}}},\n"
            if p.doi:
                entry += f"  doi = {{{p.doi}}},\n"
            entry += "}"
            entries.append(entry)
        return "\n\n".join(entries)

    async def export_zotero(
        self,
        db: AsyncSession,
        session_id: int,
        api_key: str,
        library_id: str,
        library_type: str = "user",
    ) -> dict:
        """Export papers to Zotero library."""
        from pyzotero import zotero

        papers = await self._get_papers(db, session_id)
        zot = zotero.Zotero(library_id, library_type, api_key)

        items = []
        for p in papers:
            item = {
                "itemType": "journalArticle",
                "title": p.title,
                "abstractNote": p.abstract or "",
                "DOI": p.doi or "",
                "url": p.url or "",
                "date": str(p.year) if p.year else "",
                "publicationTitle": p.journal or "",
                "volume": p.volume or "",
                "issue": p.issue or "",
                "pages": p.pages or "",
            }
            if p.authors:
                item["creators"] = [
                    {"creatorType": "author", "name": a.get("name", "")}
                    for a in p.authors
                ]
            if p.keywords:
                item["tags"] = [{"tag": kw} for kw in p.keywords]
            items.append(item)

        # Zotero API accepts max 50 items per request
        created = 0
        for i in range(0, len(items), 50):
            batch = items[i:i + 50]
            try:
                result = zot.create_items(batch)
                created += len(result.get("successful", {}))
            except Exception as e:
                logger.error(f"Zotero export error: {e}")

        return {"exported": created, "total": len(papers)}

    async def _get_papers(self, db: AsyncSession, session_id: int) -> list[Paper]:
        result = await db.execute(
            select(Paper)
            .where(Paper.session_id == session_id)
            .where(Paper.is_included == True)
            .where(primary_corpus_clause())
            .order_by(Paper.citation_count.desc())
        )
        return list(result.scalars().all())


export_service = ExportService()
