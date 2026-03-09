"""LLM function-calling tool definitions for the Executor Agent."""

from app.agents.tools.search_tools import SEARCH_TOOLS, execute_tool

__all__ = ["SEARCH_TOOLS", "execute_tool"]
