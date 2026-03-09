"""Scraper data source using Scrapling for web scraping academic pages.

This source is used as a fallback when structured APIs don't have a paper,
or to extract additional metadata (full text, supplementary info) from publisher pages.
"""

import logging
import re

from app.sources.base import BaseDataSource, UnifiedPaper

logger = logging.getLogger(__name__)


class ScraperSource(BaseDataSource):
    """Web scraper for extracting paper metadata from publisher pages."""

    name = "scraper"
    requires_auth = False

    def __init__(self):
        self._available = False
        try:
            import scrapling
            self._available = True
        except ImportError:
            logger.info("Scrapling not installed, scraper source disabled")

    async def search(
        self,
        query: str,
        max_results: int = 100,
        year_from: int | None = None,
        year_to: int | None = None,
    ) -> list[UnifiedPaper]:
        # Scraper doesn't support search - it's for fetching specific URLs
        return []

    async def get_paper_by_id(self, paper_id: str) -> UnifiedPaper | None:
        """Scrape paper metadata from a URL or DOI."""
        if not self._available:
            return None

        url = paper_id
        if not url.startswith("http"):
            url = f"https://doi.org/{paper_id}"

        try:
            return await self._scrape_paper(url)
        except Exception as e:
            logger.error(f"Scraper error for {url}: {e}")
            return None

    async def scrape_metadata(self, url: str) -> dict:
        """Scrape metadata from a paper URL. Returns raw dict."""
        if not self._available:
            return {}

        import asyncio
        return await asyncio.get_event_loop().run_in_executor(
            None, self._sync_scrape_metadata, url,
        )

    def _sync_scrape_metadata(self, url: str) -> dict:
        """Synchronous scraping of paper metadata using Scrapling."""
        try:
            from scrapling import Fetcher

            fetcher = Fetcher(auto_match=True)
            page = fetcher.get(url)

            metadata = {}

            # Extract from meta tags (standard academic metadata)
            for meta in page.css("meta"):
                name = meta.attrib.get("name", "") or meta.attrib.get("property", "")
                content = meta.attrib.get("content", "")
                if not name or not content:
                    continue

                # Dublin Core / Highwire Press tags
                if name in ("citation_title", "dc.title", "og:title"):
                    metadata.setdefault("title", content)
                elif name in ("citation_author", "dc.creator"):
                    metadata.setdefault("authors", [])
                    metadata["authors"].append(content)
                elif name in ("citation_publication_date", "dc.date"):
                    metadata.setdefault("date", content)
                elif name in ("citation_journal_title", "dc.publisher"):
                    metadata.setdefault("journal", content)
                elif name in ("citation_doi", "dc.identifier"):
                    if "doi" in content.lower() or re.match(r'10\.\d+/', content):
                        metadata.setdefault("doi", content.replace("doi:", "").strip())
                elif name == "citation_abstract":
                    metadata.setdefault("abstract", content)
                elif name == "citation_keywords":
                    metadata.setdefault("keywords", [])
                    metadata["keywords"].extend(
                        k.strip() for k in content.split(",") if k.strip()
                    )

            # Fallback: try page title
            if "title" not in metadata:
                title_el = page.css_first("h1")
                if title_el:
                    metadata["title"] = title_el.text.strip()

            return metadata

        except Exception as e:
            logger.error(f"Scrapling error for {url}: {e}")
            return {}

    async def _scrape_paper(self, url: str) -> UnifiedPaper | None:
        """Scrape and parse paper metadata into UnifiedPaper."""
        import asyncio
        metadata = await asyncio.get_event_loop().run_in_executor(
            None, self._sync_scrape_metadata, url,
        )

        if not metadata.get("title"):
            return None

        # Parse year from date
        year = None
        date_str = metadata.get("date", "")
        if date_str:
            year_match = re.search(r'(\d{4})', date_str)
            if year_match:
                year = int(year_match.group(1))

        authors = [
            {"name": name, "affiliation": "", "orcid": ""}
            for name in metadata.get("authors", [])
        ]

        return UnifiedPaper(
            title=metadata["title"],
            abstract=metadata.get("abstract", ""),
            authors=authors,
            journal=metadata.get("journal", ""),
            year=year,
            doi=metadata.get("doi", ""),
            keywords=metadata.get("keywords", []),
            url=url,
            source_name="scraper",
        )

    async def is_available(self) -> bool:
        return self._available
