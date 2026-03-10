"""Analyst Agent - trend analysis with AI interpretation."""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis.bibliometrics import run_bibliometrics
from app.analysis.charts import theme_all_charts
from app.analysis.network import run_coauthor_network, run_keyword_network
from app.analysis.trend_detection import run_trend_analysis
from app.core.events import event_bus
from app.db.models import AnalysisRun, AppSetting, Paper
from app.services.ai_service import ai_service
from app.services.corpus_scope import primary_corpus_clause

logger = logging.getLogger(__name__)


class AnalystAgent:
    """Performs bibliometric analysis and generates AI interpretations."""

    @staticmethod
    async def _resolve_output_language(db: AsyncSession) -> str:
        setting = await db.get(AppSetting, "output_language")
        return setting.value if setting and setting.value else "zh-CN"

    async def run_analysis(
        self,
        db: AsyncSession,
        analysis_run: AnalysisRun,
    ):
        """Execute an analysis run."""
        logger.info(f"Starting analysis {analysis_run.id}: {analysis_run.analysis_type}")
        analysis_run.status = "running"
        await db.commit()

        # Fetch papers for this session
        result = await db.execute(
            select(Paper)
            .where(Paper.session_id == analysis_run.session_id)
            .where(Paper.is_included == True)
            .where(primary_corpus_clause())
        )
        papers = result.scalars().all()

        if not papers:
            analysis_run.status = "failed"
            analysis_run.results = {"error": "No papers to analyze"}
            await db.commit()
            logger.warning(f"Analysis {analysis_run.id}: no papers")
            return

        analysis_type = analysis_run.analysis_type
        output_language = await self._resolve_output_language(db)

        await event_bus.emit("analysis_progress", {
            "run_id": analysis_run.id,
            "step": "computing",
            "progress": 0.2,
            "analysis_type": analysis_type,
        }, session_id=str(analysis_run.session_id))

        # Compute metrics based on type
        if analysis_type == "bibliometrics":
            results, charts = run_bibliometrics(papers)
        elif analysis_type == "trend":
            results, charts = run_trend_analysis(papers)
        elif analysis_type == "network":
            results, charts = run_keyword_network(papers)
        elif analysis_type == "coauthor":
            results, charts = run_coauthor_network(papers)
        elif analysis_type == "topic_modeling":
            from app.analysis.topic_modeling import run_topic_modeling
            results, charts = await run_topic_modeling(papers)
        else:
            logger.warning(f"Unknown analysis type: {analysis_type}, falling back to bibliometrics")
            results, charts = run_bibliometrics(papers)

        # Apply chart theming
        charts = theme_all_charts(charts)

        await event_bus.emit("analysis_progress", {
            "run_id": analysis_run.id,
            "step": "ai_interpretation",
            "progress": 0.7,
            "analysis_type": analysis_type,
        }, session_id=str(analysis_run.session_id))

        # AI interpretation
        interpretation = await self._interpret(analysis_type, results, papers, output_language)

        analysis_run.results = results
        analysis_run.chart_configs = charts
        analysis_run.ai_interpretation = interpretation
        analysis_run.status = "completed"
        await db.commit()

        logger.info(f"Analysis {analysis_run.id} completed")

        await event_bus.emit("analysis_progress", {
            "run_id": analysis_run.id,
            "step": "completed",
            "progress": 1.0,
            "analysis_type": analysis_type,
        }, session_id=str(analysis_run.session_id))

    async def _interpret(self, analysis_type: str, results: dict, papers, output_language: str) -> str:
        """Generate AI interpretation of analysis results."""
        summary = f"Analysis type: {analysis_type}\n"
        summary += f"Total papers: {len(papers)}\n"
        # Truncate results to avoid token limits
        results_str = str(results)
        if len(results_str) > 3000:
            results_str = results_str[:3000] + "..."
        summary += f"Key metrics: {results_str}"
        language_instruction = "Write the interpretation in Simplified Chinese." if output_language.startswith("zh") else "Write the interpretation in English."

        messages = [
            {
                "role": "system",
                "content": (
                    "You are an expert research analyst. Provide a concise but insightful "
                    "interpretation of bibliometric analysis results. "
                    "Highlight: key trends, notable findings, research gaps, and implications. "
                    "Use clear academic prose with bullet points for key takeaways. "
                    "Keep the interpretation to 300-500 words. "
                    f"{language_instruction}"
                ),
            },
            {"role": "user", "content": f"Please interpret these analysis results:\n\n{summary}"},
        ]

        try:
            return await ai_service.chat(messages, role="analyst", temperature=0.5)
        except Exception as e:
            logger.error(f"AI interpretation failed: {e}")
            return "AI interpretation unavailable." if not output_language.startswith("zh") else "AI 解读暂时不可用。"


analyst_agent = AnalystAgent()
