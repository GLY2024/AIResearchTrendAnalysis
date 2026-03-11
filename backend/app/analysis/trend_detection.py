"""Trend detection: time-series analysis, emerging topic identification."""

import logging
from collections import Counter, defaultdict

logger = logging.getLogger(__name__)


def run_trend_analysis(papers: list) -> tuple[dict, list]:
    """Citation and publication trend analysis.

    Returns (results_dict, chart_configs_list).
    """
    logger.info(f"Running trend analysis on {len(papers)} papers")

    year_data: dict[int, dict] = {}
    for p in papers:
        y = p.year
        if not y:
            continue
        if y not in year_data:
            year_data[y] = {"count": 0, "citations": 0, "keywords": Counter()}
        year_data[y]["count"] += 1
        year_data[y]["citations"] += p.citation_count
        for kw in (p.keywords or [])[:5]:
            year_data[y]["keywords"][kw] += 1

    sorted_years = sorted(year_data.keys())
    if len(sorted_years) < 2:
        return {
            "yearly_data": {
                str(y): {"count": year_data[y]["count"], "citations": year_data[y]["citations"]}
                for y in sorted_years
            },
            "growth_trend": "insufficient_data",
            "early_avg_papers_per_year": 0.0,
            "late_avg_papers_per_year": 0.0,
            "emerging_keywords": [],
        }, []

    # Compute cumulative counts and moving averages
    cumulative = []
    total = 0
    for y in sorted_years:
        total += year_data[y]["count"]
        cumulative.append(total)

    # Simple growth detection: compare recent vs earlier halves
    mid = len(sorted_years) // 2
    early_avg = sum(year_data[y]["count"] for y in sorted_years[:mid]) / max(mid, 1)
    late_avg = sum(year_data[y]["count"] for y in sorted_years[mid:]) / max(len(sorted_years) - mid, 1)
    growth_label = "growing" if late_avg > early_avg * 1.2 else "stable" if late_avg > early_avg * 0.8 else "declining"

    # Emerging keywords: keywords that appear mostly in recent years
    recent_years = set(sorted_years[-3:]) if len(sorted_years) >= 3 else set(sorted_years)
    all_kw_freq = Counter()
    recent_kw_freq = Counter()
    for y in sorted_years:
        for kw, cnt in year_data[y]["keywords"].items():
            all_kw_freq[kw] += cnt
            if y in recent_years:
                recent_kw_freq[kw] += cnt

    emerging_keywords = []
    for kw, recent_cnt in recent_kw_freq.most_common(30):
        total_cnt = all_kw_freq[kw]
        if total_cnt >= 3:
            recency_ratio = recent_cnt / total_cnt
            if recency_ratio > 0.6:
                emerging_keywords.append({
                    "keyword": kw,
                    "recent_count": recent_cnt,
                    "total_count": total_cnt,
                    "recency_ratio": round(recency_ratio, 2),
                })

    results = {
        "yearly_data": {
            str(y): {"count": year_data[y]["count"], "citations": year_data[y]["citations"]}
            for y in sorted_years
        },
        "growth_trend": growth_label,
        "early_avg_papers_per_year": round(early_avg, 1),
        "late_avg_papers_per_year": round(late_avg, 1),
        "emerging_keywords": emerging_keywords[:10],
    }

    charts = [
        {
            "id": "citation_trend",
            "title": "Publication & Citation Trend Over Time",
            "type": "line",
            "option": {
                "xAxis": {"type": "category", "data": [str(y) for y in sorted_years]},
                "yAxis": [
                    {"type": "value", "name": "Papers"},
                    {"type": "value", "name": "Citations"},
                ],
                "series": [
                    {
                        "type": "bar",
                        "data": [year_data[y]["count"] for y in sorted_years],
                        "name": "Papers",
                        "itemStyle": {"borderRadius": [4, 4, 0, 0]},
                    },
                    {
                        "type": "line",
                        "yAxisIndex": 1,
                        "data": [year_data[y]["citations"] for y in sorted_years],
                        "name": "Citations",
                        "smooth": True,
                    },
                ],
                "tooltip": {"trigger": "axis"},
                "legend": {},
            },
        },
        {
            "id": "cumulative_growth",
            "title": "Cumulative Paper Count",
            "type": "line",
            "option": {
                "xAxis": {"type": "category", "data": [str(y) for y in sorted_years]},
                "yAxis": {"type": "value", "name": "Total Papers"},
                "series": [{
                    "type": "line",
                    "data": cumulative,
                    "areaStyle": {"opacity": 0.15},
                    "smooth": True,
                }],
                "tooltip": {"trigger": "axis"},
            },
        },
    ]

    return results, charts
