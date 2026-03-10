"""arXiv data source implementation."""

import logging
import arxiv

from app.sources.base import BaseDataSource, UnifiedPaper

logger = logging.getLogger(__name__)


class ArxivSource(BaseDataSource):
    name = "arxiv"
    requires_auth = False

    async def search(
        self,
        query: str,
        max_results: int = 100,
        year_from: int | None = None,
        year_to: int | None = None,
    ) -> list[UnifiedPaper]:
        import asyncio

        def _sync_search():
            client = arxiv.Client()
            search = arxiv.Search(
                query=query,
                max_results=max_results,
                sort_by=arxiv.SortCriterion.Relevance,
            )
            results = []
            for r in client.results(search):
                year = r.published.year if r.published else None
                if year_from and year and year < year_from:
                    continue
                if year_to and year and year > year_to:
                    continue
                results.append(self._parse_result(r))
            return results

        return await asyncio.get_event_loop().run_in_executor(None, _sync_search)

    async def get_paper_by_id(self, paper_id: str) -> UnifiedPaper | None:
        import asyncio

        def _sync_get():
            client = arxiv.Client()
            search = arxiv.Search(id_list=[paper_id])
            results = list(client.results(search))
            return self._parse_result(results[0]) if results else None

        return await asyncio.get_event_loop().run_in_executor(None, _sync_get)

    async def is_available(self) -> bool:
        return True  # arXiv API is always available

    def _parse_result(self, r) -> UnifiedPaper:
        arxiv_id = r.entry_id.split("/abs/")[-1] if r.entry_id else ""
        categories = list(getattr(r, "categories", []) or [])
        return UnifiedPaper(
            title=r.title or "",
            abstract=r.summary or "",
            authors=[{"name": a.name, "affiliation": "", "orcid": ""} for a in r.authors],
            journal=r.journal_ref or "",
            year=r.published.year if r.published else None,
            publication_date=r.published.strftime("%Y-%m-%d") if r.published else "",
            doi=r.doi or "",
            arxiv_id=arxiv_id,
            url=r.entry_id or "",
            pdf_url=r.pdf_url or "",
            citation_count=0,  # arXiv doesn't provide citation counts
            keywords=[str(category) for category in categories],
            fields=[r.primary_category] if r.primary_category else [],
            paper_type="preprint",
            source_name="arxiv",
        )
