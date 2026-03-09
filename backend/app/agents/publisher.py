"""Publisher Agent - generates Markdown + ECharts reports."""

import logging
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import event_bus
from app.db.models import AnalysisRun, Paper, Report
from app.services.ai_service import ai_service

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent / "prompts"


class PublisherAgent:
    """Generates comprehensive research trend reports."""

    async def generate_report(
        self,
        db: AsyncSession,
        report: Report,
    ):
        """Generate a full report for a research session."""
        report.status = "generating"
        await db.commit()

        # Gather data
        papers_result = await db.execute(
            select(Paper)
            .where(Paper.session_id == report.session_id)
            .where(Paper.is_included == True)
            .order_by(Paper.citation_count.desc())
        )
        papers = papers_result.scalars().all()

        analyses_result = await db.execute(
            select(AnalysisRun)
            .where(AnalysisRun.session_id == report.session_id)
            .where(AnalysisRun.status == "completed")
        )
        analyses = analyses_result.scalars().all()

        await event_bus.emit("report_progress", {
            "report_id": report.id,
            "step": "generating",
            "progress": 0.3,
        })

        # Build context for AI
        paper_summaries = "\n".join([
            f"- {p.title} ({p.year}) - {p.citation_count} citations"
            for p in papers[:50]
        ])

        analysis_summaries = "\n\n".join([
            f"### {a.analysis_type}\n{a.ai_interpretation[:500]}"
            for a in analyses
        ])

        # Load system prompt from template
        try:
            jinja_env = Environment(loader=FileSystemLoader(str(PROMPTS_DIR)), autoescape=False)
            system_prompt = jinja_env.get_template("publisher_system.j2").render()
        except Exception:
            system_prompt = "You are a research report writer. Generate a comprehensive Markdown report about research trends."

        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"""Generate a research trend report based on this data:

**Top Papers ({len(papers)} total):**
{paper_summaries}

**Analysis Results:**
{analysis_summaries}

Write a comprehensive report in Markdown format.""",
            },
        ]

        try:
            content = ""
            async for token in ai_service.chat_stream(messages, role="publisher"):
                content += token
                await event_bus.emit("report_progress", {
                    "report_id": report.id,
                    "step": "streaming",
                    "token": token,
                })

            report.title = self._extract_title(content)
            report.content_markdown = content
            report.chart_configs = [a.chart_configs for a in analyses if a.chart_configs]
            report.status = "completed"
        except Exception as e:
            logger.error(f"Report generation failed: {e}")
            report.status = "failed"
            report.content_markdown = f"Report generation failed: {e}"

        await db.commit()

        await event_bus.emit("report_progress", {
            "report_id": report.id,
            "step": "completed",
            "progress": 1.0,
        })

    def _extract_title(self, content: str) -> str:
        """Extract title from first heading."""
        for line in content.split("\n"):
            line = line.strip()
            if line.startswith("# "):
                return line[2:].strip()
        return "Research Trend Report"


publisher_agent = PublisherAgent()
