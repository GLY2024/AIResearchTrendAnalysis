"""Base data source abstraction and unified paper model."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class UnifiedPaper:
    """Normalized paper representation across all sources."""

    title: str
    abstract: str = ""
    authors: list[dict] = field(default_factory=list)  # [{name, affiliation, orcid}]
    journal: str = ""
    year: int | None = None
    publication_date: str = ""
    doi: str = ""
    arxiv_id: str = ""
    openalex_id: str = ""
    scopus_id: str = ""
    url: str = ""
    pdf_url: str = ""
    citation_count: int = 0
    reference_count: int = 0
    keywords: list[str] = field(default_factory=list)
    fields: list[str] = field(default_factory=list)
    paper_type: str = ""
    volume: str = ""
    issue: str = ""
    pages: str = ""
    source_name: str = ""  # which data source provided this


class BaseDataSource(ABC):
    """Abstract base class for all data sources."""

    name: str = ""
    requires_auth: bool = False

    @abstractmethod
    async def search(
        self,
        query: str,
        max_results: int = 100,
        year_from: int | None = None,
        year_to: int | None = None,
    ) -> list[UnifiedPaper]:
        ...

    @abstractmethod
    async def get_paper_by_id(self, paper_id: str) -> UnifiedPaper | None:
        ...

    async def get_citations(self, paper_id: str) -> list[UnifiedPaper]:
        """Forward citation expansion: papers that cite this paper."""
        return []

    async def get_references(self, paper_id: str) -> list[UnifiedPaper]:
        """Backward citation expansion: papers this paper cites."""
        return []

    async def is_available(self) -> bool:
        """Check if this source is configured and reachable."""
        return True
