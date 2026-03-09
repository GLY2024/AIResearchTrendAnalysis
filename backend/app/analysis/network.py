"""Network analysis: co-citation, co-authorship, keyword co-occurrence."""

import logging
from collections import Counter, defaultdict

logger = logging.getLogger(__name__)


def run_keyword_network(papers: list) -> tuple[dict, list]:
    """Keyword co-occurrence network analysis.

    Returns (results_dict, chart_configs_list).
    """
    logger.info(f"Running keyword network on {len(papers)} papers")

    keyword_freq: Counter = Counter()
    co_occur: Counter = Counter()

    for p in papers:
        kws = (p.keywords or [])[:10]
        for kw in kws:
            keyword_freq[kw] += 1
        for i, kw1 in enumerate(kws):
            for kw2 in kws[i + 1:]:
                pair = tuple(sorted([kw1, kw2]))
                co_occur[pair] += 1

    # Top keywords as nodes
    top_kws = keyword_freq.most_common(30)
    top_kw_set = {kw for kw, _ in top_kws}

    nodes = [
        {"name": kw, "value": cnt, "symbolSize": min(cnt * 3 + 10, 60)}
        for kw, cnt in top_kws
    ]
    links = [
        {"source": pair[0], "target": pair[1], "value": cnt}
        for pair, cnt in co_occur.items()
        if pair[0] in top_kw_set and pair[1] in top_kw_set and cnt >= 2
    ]

    results = {
        "keyword_freq": dict(top_kws),
        "co_occurrences": len(links),
        "total_unique_keywords": len(keyword_freq),
    }

    charts = [
        {
            "id": "keyword_network",
            "title": "Keyword Co-occurrence Network",
            "type": "graph",
            "option": {
                "series": [{
                    "type": "graph",
                    "layout": "force",
                    "data": nodes,
                    "links": links,
                    "force": {"repulsion": 300, "edgeLength": [50, 200], "gravity": 0.1},
                    "label": {"show": True, "fontSize": 10},
                    "lineStyle": {"curveness": 0.3, "opacity": 0.6},
                    "emphasis": {"focus": "adjacency", "lineStyle": {"width": 3}},
                    "roam": True,
                    "draggable": True,
                }],
                "tooltip": {},
            },
        },
    ]

    return results, charts


def run_coauthor_network(papers: list) -> tuple[dict, list]:
    """Co-authorship network analysis.

    Returns (results_dict, chart_configs_list).
    """
    logger.info(f"Running co-authorship network on {len(papers)} papers")

    author_freq: Counter = Counter()
    coauthor_pairs: Counter = Counter()

    for p in papers:
        authors = [a.get("name", "") for a in (p.authors or []) if a.get("name")]
        for name in authors:
            author_freq[name] += 1
        # Count co-authorship pairs
        for i, a1 in enumerate(authors):
            for a2 in authors[i + 1:]:
                pair = tuple(sorted([a1, a2]))
                coauthor_pairs[pair] += 1

    top_authors = author_freq.most_common(40)
    top_author_set = {name for name, _ in top_authors}

    nodes = [
        {"name": name, "value": cnt, "symbolSize": min(cnt * 5 + 8, 50)}
        for name, cnt in top_authors
    ]
    links = [
        {"source": pair[0], "target": pair[1], "value": cnt}
        for pair, cnt in coauthor_pairs.items()
        if pair[0] in top_author_set and pair[1] in top_author_set and cnt >= 1
    ]

    results = {
        "top_authors": [{"name": n, "count": c} for n, c in top_authors],
        "collaboration_links": len(links),
    }

    charts = [
        {
            "id": "coauthor_network",
            "title": "Co-authorship Network",
            "type": "graph",
            "option": {
                "series": [{
                    "type": "graph",
                    "layout": "force",
                    "data": nodes,
                    "links": links,
                    "force": {"repulsion": 400, "edgeLength": [80, 250], "gravity": 0.1},
                    "label": {"show": True, "fontSize": 9},
                    "lineStyle": {"curveness": 0.2, "opacity": 0.5},
                    "emphasis": {"focus": "adjacency"},
                    "roam": True,
                    "draggable": True,
                }],
                "tooltip": {},
            },
        },
    ]

    return results, charts
