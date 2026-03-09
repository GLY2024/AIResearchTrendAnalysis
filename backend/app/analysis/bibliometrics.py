"""Bibliometric analysis: h-index, AGR, citation distribution, productivity metrics."""

import logging
import math
from collections import Counter
from datetime import datetime

logger = logging.getLogger(__name__)


def compute_h_index(citation_counts: list[int]) -> int:
    """Compute h-index from a list of citation counts."""
    sorted_counts = sorted(citation_counts, reverse=True)
    h = 0
    for i, c in enumerate(sorted_counts):
        if c >= i + 1:
            h = i + 1
        else:
            break
    return h


def compute_agr(year_counts: dict[int, int], window: int = 5) -> float:
    """Compute Annual Growth Rate over the last `window` years.

    AGR = ((count_recent - count_old) / count_old) * 100
    """
    if not year_counts:
        return 0.0
    current_year = max(year_counts.keys())
    old_year = current_year - window
    recent = sum(c for y, c in year_counts.items() if y > current_year - window)
    old = sum(c for y, c in year_counts.items() if old_year - window < y <= old_year)
    if old == 0:
        return 100.0 if recent > 0 else 0.0
    return round(((recent - old) / old) * 100, 2)


def run_bibliometrics(papers: list) -> tuple[dict, list]:
    """Full bibliometric analysis on a list of Paper ORM objects.

    Returns (results_dict, chart_configs_list).
    """
    logger.info(f"Running bibliometrics on {len(papers)} papers")

    total = len(papers)
    years = [p.year for p in papers if p.year]
    citations = [p.citation_count for p in papers]

    # Year distribution
    year_dist = Counter(years)

    # H-index
    h_index = compute_h_index(citations)

    # AGR
    agr = compute_agr(dict(year_dist))

    # Top cited papers
    sorted_papers = sorted(papers, key=lambda p: p.citation_count, reverse=True)
    top_cited = [
        {"title": p.title[:100], "citations": p.citation_count, "year": p.year, "doi": p.doi or ""}
        for p in sorted_papers[:20]
    ]

    # Author frequency
    author_freq: Counter = Counter()
    author_citations: dict[str, int] = {}
    for p in papers:
        for a in (p.authors or []):
            name = a.get("name", "")
            if name:
                author_freq[name] += 1
                author_citations[name] = author_citations.get(name, 0) + p.citation_count
    top_authors = author_freq.most_common(20)

    # Journal frequency
    journal_freq: Counter = Counter()
    for p in papers:
        if p.journal:
            journal_freq[p.journal] += 1
    top_journals = journal_freq.most_common(15)

    # Citation distribution buckets
    citation_buckets = {"0": 0, "1-5": 0, "6-20": 0, "21-50": 0, "51-100": 0, "100+": 0}
    for c in citations:
        if c == 0:
            citation_buckets["0"] += 1
        elif c <= 5:
            citation_buckets["1-5"] += 1
        elif c <= 20:
            citation_buckets["6-20"] += 1
        elif c <= 50:
            citation_buckets["21-50"] += 1
        elif c <= 100:
            citation_buckets["51-100"] += 1
        else:
            citation_buckets["100+"] += 1

    # Paper type distribution
    type_dist = Counter(p.paper_type for p in papers if p.paper_type)

    results = {
        "total_papers": total,
        "year_range": [min(years) if years else 0, max(years) if years else 0],
        "total_citations": sum(citations),
        "avg_citations": round(sum(citations) / total, 2) if total else 0,
        "median_citations": sorted(citations)[total // 2] if total else 0,
        "h_index": h_index,
        "annual_growth_rate": agr,
        "top_cited": top_cited,
        "top_authors": [
            {"name": n, "count": c, "total_citations": author_citations.get(n, 0)}
            for n, c in top_authors
        ],
        "top_journals": [{"name": n, "count": c} for n, c in top_journals],
        "year_distribution": dict(year_dist),
        "citation_distribution": citation_buckets,
        "paper_types": dict(type_dist),
    }

    # ECharts configs
    sorted_years = sorted(year_dist.keys())
    charts = [
        {
            "id": "year_trend",
            "title": "Publication Trend by Year",
            "type": "bar",
            "option": {
                "xAxis": {"type": "category", "data": [str(y) for y in sorted_years]},
                "yAxis": {"type": "value", "name": "Papers"},
                "series": [{"type": "bar", "data": [year_dist[y] for y in sorted_years],
                            "itemStyle": {"borderRadius": [4, 4, 0, 0]}}],
                "tooltip": {"trigger": "axis"},
            },
        },
        {
            "id": "top_authors",
            "title": "Top Authors by Publication Count",
            "type": "bar",
            "option": {
                "xAxis": {"type": "value"},
                "yAxis": {"type": "category", "data": [n for n, _ in top_authors[:10]],
                          "inverse": True},
                "series": [{"type": "bar", "data": [c for _, c in top_authors[:10]]}],
                "tooltip": {"trigger": "axis"},
                "grid": {"left": "30%"},
            },
        },
        {
            "id": "citation_distribution",
            "title": "Citation Distribution",
            "type": "pie",
            "option": {
                "series": [{
                    "type": "pie",
                    "radius": ["40%", "70%"],
                    "data": [{"name": k, "value": v} for k, v in citation_buckets.items() if v > 0],
                    "label": {"show": True, "formatter": "{b}: {c}"},
                }],
                "tooltip": {"trigger": "item"},
            },
        },
    ]

    return results, charts
