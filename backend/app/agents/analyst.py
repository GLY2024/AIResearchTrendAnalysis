"""Analyst Agent - trend analysis with AI interpretation."""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import event_bus
from app.db.models import AnalysisRun, Paper
from app.services.ai_service import ai_service

logger = logging.getLogger(__name__)


class AnalystAgent:
    """Performs bibliometric analysis and generates AI interpretations."""

    async def run_analysis(
        self,
        db: AsyncSession,
        analysis_run: AnalysisRun,
    ):
        """Execute an analysis run."""
        analysis_run.status = "running"
        await db.commit()

        # Fetch papers for this session
        result = await db.execute(
            select(Paper)
            .where(Paper.session_id == analysis_run.session_id)
            .where(Paper.is_included == True)
        )
        papers = result.scalars().all()

        if not papers:
            analysis_run.status = "failed"
            analysis_run.results = {"error": "No papers to analyze"}
            await db.commit()
            return

        analysis_type = analysis_run.analysis_type

        await event_bus.emit("analysis_progress", {
            "run_id": analysis_run.id,
            "step": "computing",
            "progress": 0.2,
        })

        # Compute metrics based on type
        if analysis_type == "bibliometrics":
            results, charts = self._bibliometrics(papers)
        elif analysis_type == "trend":
            results, charts = self._trend_analysis(papers)
        elif analysis_type == "network":
            results, charts = self._network_analysis(papers)
        else:
            results, charts = self._bibliometrics(papers)

        await event_bus.emit("analysis_progress", {
            "run_id": analysis_run.id,
            "step": "ai_interpretation",
            "progress": 0.7,
        })

        # AI interpretation
        interpretation = await self._interpret(analysis_type, results, papers)

        analysis_run.results = results
        analysis_run.chart_configs = charts
        analysis_run.ai_interpretation = interpretation
        analysis_run.status = "completed"
        await db.commit()

        await event_bus.emit("analysis_progress", {
            "run_id": analysis_run.id,
            "step": "completed",
            "progress": 1.0,
        })

    def _bibliometrics(self, papers) -> tuple[dict, list]:
        """Basic bibliometric analysis."""
        total = len(papers)
        years = [p.year for p in papers if p.year]
        citations = [p.citation_count for p in papers]

        # Year distribution
        year_dist = {}
        for y in years:
            year_dist[y] = year_dist.get(y, 0) + 1

        # Top cited
        sorted_papers = sorted(papers, key=lambda p: p.citation_count, reverse=True)
        top_cited = [
            {"title": p.title[:100], "citations": p.citation_count, "year": p.year}
            for p in sorted_papers[:20]
        ]

        # Author frequency
        author_freq = {}
        for p in papers:
            for a in (p.authors or []):
                name = a.get("name", "")
                if name:
                    author_freq[name] = author_freq.get(name, 0) + 1
        top_authors = sorted(author_freq.items(), key=lambda x: x[1], reverse=True)[:20]

        # Journal frequency
        journal_freq = {}
        for p in papers:
            if p.journal:
                journal_freq[p.journal] = journal_freq.get(p.journal, 0) + 1
        top_journals = sorted(journal_freq.items(), key=lambda x: x[1], reverse=True)[:15]

        results = {
            "total_papers": total,
            "year_range": [min(years) if years else 0, max(years) if years else 0],
            "total_citations": sum(citations),
            "avg_citations": round(sum(citations) / total, 2) if total else 0,
            "top_cited": top_cited,
            "top_authors": [{"name": n, "count": c} for n, c in top_authors],
            "top_journals": [{"name": n, "count": c} for n, c in top_journals],
            "year_distribution": year_dist,
        }

        # ECharts configs
        charts = [
            {
                "id": "year_trend",
                "title": "Publication Trend by Year",
                "type": "bar",
                "option": {
                    "xAxis": {"type": "category", "data": sorted(year_dist.keys())},
                    "yAxis": {"type": "value", "name": "Papers"},
                    "series": [{"type": "bar", "data": [year_dist[y] for y in sorted(year_dist.keys())]}],
                    "tooltip": {"trigger": "axis"},
                },
            },
            {
                "id": "top_authors",
                "title": "Top Authors by Publication Count",
                "type": "bar",
                "option": {
                    "xAxis": {"type": "value"},
                    "yAxis": {"type": "category", "data": [n for n, _ in top_authors[:10]]},
                    "series": [{"type": "bar", "data": [c for _, c in top_authors[:10]]}],
                    "tooltip": {"trigger": "axis"},
                },
            },
        ]

        return results, charts

    def _trend_analysis(self, papers) -> tuple[dict, list]:
        """Citation trend and growth analysis."""
        year_data = {}
        for p in papers:
            y = p.year
            if not y:
                continue
            if y not in year_data:
                year_data[y] = {"count": 0, "citations": 0}
            year_data[y]["count"] += 1
            year_data[y]["citations"] += p.citation_count

        sorted_years = sorted(year_data.keys())
        results = {
            "yearly_data": {str(y): year_data[y] for y in sorted_years},
        }

        charts = [
            {
                "id": "citation_trend",
                "title": "Citation Trend Over Time",
                "type": "line",
                "option": {
                    "xAxis": {"type": "category", "data": [str(y) for y in sorted_years]},
                    "yAxis": [
                        {"type": "value", "name": "Papers"},
                        {"type": "value", "name": "Citations"},
                    ],
                    "series": [
                        {"type": "bar", "data": [year_data[y]["count"] for y in sorted_years], "name": "Papers"},
                        {"type": "line", "yAxisIndex": 1, "data": [year_data[y]["citations"] for y in sorted_years], "name": "Citations"},
                    ],
                    "tooltip": {"trigger": "axis"},
                    "legend": {},
                },
            }
        ]

        return results, charts

    def _network_analysis(self, papers) -> tuple[dict, list]:
        """Keyword co-occurrence network."""
        keyword_freq = {}
        co_occur = {}
        for p in papers:
            kws = (p.keywords or [])[:10]
            for kw in kws:
                keyword_freq[kw] = keyword_freq.get(kw, 0) + 1
            for i, kw1 in enumerate(kws):
                for kw2 in kws[i + 1:]:
                    pair = tuple(sorted([kw1, kw2]))
                    co_occur[pair] = co_occur.get(pair, 0) + 1

        # Top keywords as nodes
        top_kws = sorted(keyword_freq.items(), key=lambda x: x[1], reverse=True)[:30]
        top_kw_set = {kw for kw, _ in top_kws}

        nodes = [{"name": kw, "value": cnt, "symbolSize": min(cnt * 3, 50)} for kw, cnt in top_kws]
        links = [
            {"source": pair[0], "target": pair[1], "value": cnt}
            for pair, cnt in co_occur.items()
            if pair[0] in top_kw_set and pair[1] in top_kw_set and cnt >= 2
        ]

        results = {"keyword_freq": dict(top_kws), "co_occurrences": len(links)}

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
                        "force": {"repulsion": 200, "edgeLength": [50, 200]},
                        "label": {"show": True, "fontSize": 10},
                        "lineStyle": {"curveness": 0.3},
                    }],
                    "tooltip": {},
                },
            }
        ]

        return results, charts

    async def _interpret(self, analysis_type: str, results: dict, papers) -> str:
        """Generate AI interpretation of analysis results."""
        summary = f"Analysis type: {analysis_type}\n"
        summary += f"Total papers: {len(papers)}\n"
        summary += f"Key metrics: {str(results)[:2000]}"

        messages = [
            {
                "role": "system",
                "content": "You are an expert research analyst. Provide a concise interpretation of bibliometric analysis results. Highlight key trends, notable findings, and potential research gaps. Write in clear academic prose.",
            },
            {"role": "user", "content": f"Please interpret these analysis results:\n\n{summary}"},
        ]

        try:
            return await ai_service.chat(messages, role="analyst", temperature=0.5)
        except Exception as e:
            logger.error(f"AI interpretation failed: {e}")
            return "AI interpretation unavailable."


analyst_agent = AnalystAgent()
