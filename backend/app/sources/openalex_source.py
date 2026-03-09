"""OpenAlex data source implementation (free, no auth required)."""

import logging
from urllib.parse import quote

import httpx

from app.sources.base import BaseDataSource, UnifiedPaper

logger = logging.getLogger(__name__)

OPENALEX_API = "https://api.openalex.org"


class OpenAlexSource(BaseDataSource):
    name = "openalex"
    requires_auth = False

    def __init__(self):
        self._client = httpx.AsyncClient(
            base_url=OPENALEX_API,
            timeout=30.0,
            headers={"User-Agent": "ARTA/0.1 (mailto:arta@research.local)"},
        )

    async def search(
        self,
        query: str,
        max_results: int = 100,
        year_from: int | None = None,
        year_to: int | None = None,
    ) -> list[UnifiedPaper]:
        papers = []
        per_page = min(max_results, 200)
        page = 1
        collected = 0

        while collected < max_results:
            params = {
                "search": query,
                "per_page": per_page,
                "page": page,
                "sort": "cited_by_count:desc",
            }

            # Year filter
            filters = []
            if year_from:
                filters.append(f"publication_year:>{year_from - 1}")
            if year_to:
                filters.append(f"publication_year:<{year_to + 1}")
            if filters:
                params["filter"] = ",".join(filters)

            try:
                resp = await self._client.get("/works", params=params)
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                logger.error(f"OpenAlex search error: {e}")
                break

            results = data.get("results", [])
            if not results:
                break

            for work in results:
                papers.append(self._parse_work(work))
                collected += 1
                if collected >= max_results:
                    break

            page += 1

        return papers

    async def get_paper_by_id(self, paper_id: str) -> UnifiedPaper | None:
        try:
            resp = await self._client.get(f"/works/{paper_id}")
            resp.raise_for_status()
            return self._parse_work(resp.json())
        except Exception as e:
            logger.error(f"OpenAlex get_paper error: {e}")
            return None

    async def get_citations(self, paper_id: str) -> list[UnifiedPaper]:
        """Forward snowball: papers citing this one."""
        try:
            resp = await self._client.get(
                "/works",
                params={
                    "filter": f"cites:{paper_id}",
                    "per_page": 200,
                    "sort": "cited_by_count:desc",
                },
            )
            resp.raise_for_status()
            return [self._parse_work(w) for w in resp.json().get("results", [])]
        except Exception as e:
            logger.error(f"OpenAlex citations error: {e}")
            return []

    async def get_references(self, paper_id: str) -> list[UnifiedPaper]:
        """Backward snowball: papers this one cites."""
        try:
            # First get the work to find referenced_works
            resp = await self._client.get(f"/works/{paper_id}")
            resp.raise_for_status()
            work = resp.json()
            ref_ids = work.get("referenced_works", [])
            if not ref_ids:
                return []

            # Fetch referenced works (batch by pipe-separated IDs)
            batch_filter = "|".join(ref_ids[:50])  # API limit
            resp = await self._client.get(
                "/works",
                params={"filter": f"openalex:{batch_filter}", "per_page": 50},
            )
            resp.raise_for_status()
            return [self._parse_work(w) for w in resp.json().get("results", [])]
        except Exception as e:
            logger.error(f"OpenAlex references error: {e}")
            return []

    async def is_available(self) -> bool:
        try:
            resp = await self._client.get("/works", params={"per_page": 1})
            return resp.status_code == 200
        except Exception:
            return False

    def _parse_work(self, work: dict) -> UnifiedPaper:
        # Extract authors
        authors = []
        for authorship in work.get("authorships", []):
            author = authorship.get("author", {})
            institutions = authorship.get("institutions", [])
            authors.append({
                "name": author.get("display_name", ""),
                "affiliation": institutions[0].get("display_name", "") if institutions else "",
                "orcid": author.get("orcid", ""),
            })

        # Extract identifiers
        ids = work.get("ids", {})
        doi = (ids.get("doi") or work.get("doi") or "").replace("https://doi.org/", "")

        # Extract concepts/keywords
        keywords = [c.get("display_name", "") for c in work.get("concepts", [])[:10]]

        # Extract fields
        primary_topic = work.get("primary_topic", {}) or {}
        fields = []
        if primary_topic.get("field", {}).get("display_name"):
            fields.append(primary_topic["field"]["display_name"])
        if primary_topic.get("subfield", {}).get("display_name"):
            fields.append(primary_topic["subfield"]["display_name"])

        # Publication venue
        source = work.get("primary_location", {}) or {}
        venue = source.get("source", {}) or {}
        journal = venue.get("display_name", "")

        return UnifiedPaper(
            title=work.get("title") or work.get("display_name") or "",
            abstract=self._reconstruct_abstract(work.get("abstract_inverted_index")),
            authors=authors,
            journal=journal,
            year=work.get("publication_year"),
            publication_date=work.get("publication_date", ""),
            doi=doi,
            openalex_id=work.get("id", ""),
            url=work.get("id", ""),
            pdf_url=(source.get("pdf_url") or ""),
            citation_count=work.get("cited_by_count", 0),
            reference_count=len(work.get("referenced_works", [])),
            keywords=keywords,
            fields=fields,
            paper_type=work.get("type", ""),
            source_name="openalex",
        )

    @staticmethod
    def _reconstruct_abstract(inverted_index: dict | None) -> str:
        if not inverted_index:
            return ""
        word_positions = []
        for word, positions in inverted_index.items():
            for pos in positions:
                word_positions.append((pos, word))
        word_positions.sort()
        return " ".join(w for _, w in word_positions)
