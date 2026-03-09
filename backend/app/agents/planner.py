"""Planner Agent - generates search plans from research topics."""

import json
import logging
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from app.services.ai_service import ai_service
from app.sources.registry import source_registry

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent / "prompts"


class PlannerAgent:
    """Generates structured search plans based on research topic discussion."""

    def __init__(self):
        self._jinja = Environment(
            loader=FileSystemLoader(str(PROMPTS_DIR)),
            autoescape=False,
        )

    async def generate_plan(
        self,
        topic: str,
        chat_history: list[dict],
        available_sources: list[str] | None = None,
    ) -> dict:
        """Generate a search plan for a research topic.

        Returns a structured plan with queries, sources, and parameters.
        """
        if available_sources is None:
            available_sources = source_registry.list_sources()

        template = self._jinja.get_template("planner_system.j2")
        system_prompt = template.render(
            available_sources=available_sources,
        )

        messages = [
            {"role": "system", "content": system_prompt},
            *chat_history,
            {
                "role": "user",
                "content": f"Based on our discussion, generate a comprehensive search plan for the topic: {topic}\n\nRespond with a JSON object.",
            },
        ]

        response = await ai_service.chat(messages, role="planner", temperature=0.3)

        # Parse JSON from response
        try:
            # Try to extract JSON from markdown code block
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0].strip()
            else:
                json_str = response.strip()
            plan = json.loads(json_str)
        except (json.JSONDecodeError, IndexError) as e:
            logger.error(f"Failed to parse planner response: {e}")
            plan = {
                "topic": topic,
                "queries": [{"query": topic, "source": "openalex"}],
                "year_range": {"from": None, "to": None},
                "max_results_per_query": 100,
                "notes": "Auto-generated fallback plan",
            }

        return plan


planner_agent = PlannerAgent()
