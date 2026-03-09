"""Scopus data source implementation using pybliometrics."""

import logging
import os
from typing import Optional

import httpx

from app.sources.base import BaseDataSource, UnifiedPaper

logger = logging.getLogger(__name__)

SCOPUS_API = "https://api.elsevier.com/content"


class ScopusSource(BaseDataSource):
    """Scopus data source using the Elsevier API directly via httpx."""

    name = "scopus"
    requires_auth = True

    def __init__(self):
        self._api_key: str = ""
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        api_key = os.environ.get("SCOPUS_API_KEY", self._api_key)
        if not api_key:
            raise RuntimeError("Scopus API key not configured")
        if self._client is None or self._api_key != api_key:
            self._api_key = api_key
            self._client = httpx.AsyncClient(
                base_url=SCOPUS_API,
                timeout=30.0,
                headers={
                    "X-ELS-APIKey": api_key,
                    "Accept": "application/json",
                },
            )
        return self._client

    async def search(
        self,
        query: str,
        max_results: int = 100,
        year_from: int | None = None,
        year_to: int | None = None,
    ) -> list[UnifiedPaper]:
        client = self._get_client()
        papers = []
        start = 0
        count = min(max_results, 25)  # Scopus max per page is 25

        # Build search query with year filters
        scopus_query = query
        if year_from:
            scopus_query += f" AND PUBYEAR > {year_from - 1}"
        if year_to:
            scopus_query += f" AND PUBYEAR < {year_to + 1}"

        while len(papers) < max_results:
            params = {
                "query": scopus_query,
                "start": start,
                "count": count,
                "sort": "citedby-count",
                "field": "dc:identifier,dc:title,dc:creator,prism:coverDate,"
                         "prism:publicationName,citedby-count,prism:doi,"
                         "dc:description,authkeywords,subtypeDescription,"
                         "prism:volume,prism:issueIdentifier,prism:pageRange,"
                         "eid,author",
            }

            try:
                resp = await client.get("/search/scopus", params=params)
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                logger.error(f"Scopus search error: {e}")
                break

            search_results = data.get("search-results", {})
            entries = search_results.get("entry", [])

            if not entries or (len(entries) == 1 and "error" in entries[0]):
                break

            for entry in entries:
                paper = self._parse_entry(entry)
                if paper:
                    papers.append(paper)

            total_results = int(search_results.get("opensearch:totalResults", 0))
            start += count
            if start >= total_results or start >= max_results:
                break

        return papers[:max_results]

    async def get_paper_by_id(self, paper_id: str) -> UnifiedPaper | None:
        """Get paper by Scopus EID or DOI."""
        client = self._get_client()
        try:
            # Try as Scopus ID first
            if paper_id.startswith("2-s2.0-"):
                resp = await client.get(f"/abstract/scopus_id/{paper_id}")
            else:
                resp = await client.get(f"/abstract/doi/{paper_id}")
            resp.raise_for_status()
            data = resp.json()
            core = data.get("abstracts-retrieval-response", {}).get("coredata", {})
            if core:
                return self._parse_abstract_response(core)
        except Exception as e:
            logger.error(f"Scopus get_paper error: {e}")
        return None

    async def get_citations(self, paper_id: str) -> list[UnifiedPaper]:
        """Forward snowball: papers citing this paper."""
        client = self._get_client()
        try:
            # Use scopus search with refeid filter
            eid = paper_id if paper_id.startswith("2-s2.0-") else None
            if not eid:
                return []

            params = {
                "query": f"REF({eid})",
                "count": 100,
                "sort": "citedby-count",
                "field": "dc:identifier,dc:title,dc:creator,prism:coverDate,"
                         "prism:publicationName,citedby-count,prism:doi,eid",
            }
            resp = await client.get("/search/scopus", params=params)
            resp.raise_for_status()
            entries = resp.json().get("search-results", {}).get("entry", [])
            return [p for e in entries if (p := self._parse_entry(e))]
        except Exception as e:
            logger.error(f"Scopus citations error: {e}")
            return []

    async def get_references(self, paper_id: str) -> list[UnifiedPaper]:
        """Backward snowball: papers this paper cites."""
        client = self._get_client()
        try:
            if paper_id.startswith("2-s2.0-"):
                resp = await client.get(
                    f"/abstract/scopus_id/{paper_id}",
                    params={"view": "REF"},
                )
            else:
                resp = await client.get(
                    f"/abstract/doi/{paper_id}",
                    params={"view": "REF"},
                )
            resp.raise_for_status()
            data = resp.json()
            refs = (data.get("abstracts-retrieval-response", {})
                       .get("references", {})
                       .get("reference", []))
            papers = []
            for ref in refs[:100]:
                title = ref.get("ref-title", {}).get("ref-titletext", "")
                if title:
                    papers.append(UnifiedPaper(
                        title=title,
                        authors=[{"name": ref.get("ref-authors", {}).get("author", [{}])[0].get("ce:indexed-name", ""),
                                  "affiliation": "", "orcid": ""}] if ref.get("ref-authors") else [],
                        journal=ref.get("ref-sourcetitle", ""),
                        year=int(ref["ref-publicationyear"]["@first"]) if ref.get("ref-publicationyear") else None,
                        scopus_id=ref.get("scopus-eid", ""),
                        source_name="scopus",
                    ))
            return papers
        except Exception as e:
            logger.error(f"Scopus references error: {e}")
            return []

    async def is_available(self) -> bool:
        try:
            api_key = os.environ.get("SCOPUS_API_KEY", "")
            return bool(api_key)
        except Exception:
            return False

    def _parse_entry(self, entry: dict) -> UnifiedPaper | None:
        """Parse a Scopus search result entry."""
        title = entry.get("dc:title", "")
        if not title or "error" in entry:
            return None

        # Parse authors
        authors = []
        author_data = entry.get("author", [])
        if isinstance(author_data, list):
            for a in author_data:
                authors.append({
                    "name": a.get("authname", a.get("preferred-name", {}).get("ce:indexed-name", "")),
                    "affiliation": "",
                    "orcid": "",
                })
        elif entry.get("dc:creator"):
            authors.append({"name": entry["dc:creator"], "affiliation": "", "orcid": ""})

        # Parse date/year
        cover_date = entry.get("prism:coverDate", "")
        year = int(cover_date[:4]) if cover_date and len(cover_date) >= 4 else None

        # Parse keywords
        keywords = []
        kw_str = entry.get("authkeywords", "")
        if kw_str:
            keywords = [k.strip() for k in kw_str.split("|") if k.strip()]

        doi = entry.get("prism:doi", "")
        scopus_id = entry.get("eid", "")
        citation_count = int(entry.get("citedby-count", 0))

        return UnifiedPaper(
            title=title,
            authors=authors,
            journal=entry.get("prism:publicationName", ""),
            year=year,
            publication_date=cover_date,
            doi=doi,
            scopus_id=scopus_id,
            citation_count=citation_count,
            keywords=keywords,
            paper_type=entry.get("subtypeDescription", ""),
            volume=entry.get("prism:volume", ""),
            issue=entry.get("prism:issueIdentifier", ""),
            pages=entry.get("prism:pageRange", ""),
            source_name="scopus",
        )

    def _parse_abstract_response(self, core: dict) -> UnifiedPaper:
        """Parse a Scopus abstract retrieval response."""
        return UnifiedPaper(
            title=core.get("dc:title", ""),
            abstract=core.get("dc:description", ""),
            journal=core.get("prism:publicationName", ""),
            doi=core.get("prism:doi", ""),
            scopus_id=core.get("eid", ""),
            citation_count=int(core.get("citedby-count", 0)),
            year=int(core.get("prism:coverDate", "")[:4]) if core.get("prism:coverDate") else None,
            source_name="scopus",
        )
