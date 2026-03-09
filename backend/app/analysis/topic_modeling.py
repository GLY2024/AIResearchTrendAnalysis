"""Topic modeling: BERTopic-based or LLM-fallback topic clustering."""

import logging
from collections import Counter

logger = logging.getLogger(__name__)

# BERTopic is optional - heavy dependency
_BERTOPIC_AVAILABLE = False
try:
    from bertopic import BERTopic
    _BERTOPIC_AVAILABLE = True
except ImportError:
    pass


async def run_topic_modeling(papers: list, use_bertopic: bool = True) -> tuple[dict, list]:
    """Topic modeling using BERTopic or keyword-frequency fallback.

    Returns (results_dict, chart_configs_list).
    """
    logger.info(f"Running topic modeling on {len(papers)} papers (BERTopic: {_BERTOPIC_AVAILABLE and use_bertopic})")

    if _BERTOPIC_AVAILABLE and use_bertopic and len(papers) >= 10:
        return await _run_bertopic(papers)
    else:
        return _run_keyword_clustering(papers)


async def _run_bertopic(papers: list) -> tuple[dict, list]:
    """Run BERTopic on paper abstracts."""
    import asyncio

    def _sync_bertopic():
        docs = [p.abstract or p.title for p in papers if (p.abstract or p.title)]
        if len(docs) < 10:
            return _run_keyword_clustering(papers)

        try:
            model = BERTopic(
                nr_topics="auto",
                min_topic_size=max(3, len(docs) // 20),
                verbose=False,
            )
            topics, probs = model.fit_transform(docs)
            topic_info = model.get_topic_info()

            # Build results
            topic_list = []
            for _, row in topic_info.iterrows():
                if row["Topic"] == -1:
                    continue  # skip outlier topic
                topic_list.append({
                    "id": int(row["Topic"]),
                    "name": row.get("Name", f"Topic {row['Topic']}"),
                    "count": int(row["Count"]),
                    "words": [w for w, _ in model.get_topic(row["Topic"])[:10]] if row["Topic"] >= 0 else [],
                })

            results = {
                "method": "bertopic",
                "num_topics": len(topic_list),
                "topics": topic_list,
                "outlier_count": int(topic_info[topic_info["Topic"] == -1]["Count"].sum()) if -1 in topic_info["Topic"].values else 0,
            }

            # Chart: topic sizes
            charts = [
                {
                    "id": "topic_distribution",
                    "title": "Topic Distribution",
                    "type": "bar",
                    "option": {
                        "xAxis": {"type": "value"},
                        "yAxis": {
                            "type": "category",
                            "data": [t["name"][:40] for t in topic_list[:15]],
                            "inverse": True,
                        },
                        "series": [{"type": "bar", "data": [t["count"] for t in topic_list[:15]]}],
                        "tooltip": {"trigger": "axis"},
                        "grid": {"left": "35%"},
                    },
                },
            ]

            return results, charts

        except Exception as e:
            logger.error(f"BERTopic failed: {e}")
            return _run_keyword_clustering(papers)

    return await asyncio.get_event_loop().run_in_executor(None, _sync_bertopic)


def _run_keyword_clustering(papers: list) -> tuple[dict, list]:
    """Fallback: cluster papers by keyword frequency analysis."""
    logger.info("Using keyword-frequency fallback for topic modeling")

    # Group papers by their most frequent keywords
    keyword_freq = Counter()
    paper_keywords: dict[str, list[str]] = {}
    for p in papers:
        kws = p.keywords or []
        for kw in kws[:5]:
            keyword_freq[kw] += 1
        if kws:
            paper_keywords[str(p.id)] = kws[:5]

    # Top keywords as "topics"
    top_keywords = keyword_freq.most_common(15)

    # Group papers by their primary keyword
    topic_groups: dict[str, int] = {}
    for kw, _ in top_keywords:
        count = sum(1 for p in papers if kw in (p.keywords or []))
        topic_groups[kw] = count

    results = {
        "method": "keyword_frequency",
        "num_topics": len(top_keywords),
        "topics": [
            {"id": i, "name": kw, "count": cnt, "words": [kw]}
            for i, (kw, cnt) in enumerate(top_keywords)
        ],
    }

    charts = [
        {
            "id": "topic_keywords",
            "title": "Top Research Topics (by keyword frequency)",
            "type": "bar",
            "option": {
                "xAxis": {"type": "value"},
                "yAxis": {
                    "type": "category",
                    "data": [kw for kw, _ in top_keywords],
                    "inverse": True,
                },
                "series": [{"type": "bar", "data": [cnt for _, cnt in top_keywords]}],
                "tooltip": {"trigger": "axis"},
                "grid": {"left": "30%"},
            },
        },
    ]

    return results, charts
