"""Search tool definitions for LLM function calling.

These tools allow the Executor Agent to dynamically decide which
source to query and how to refine searches based on initial results.
"""

import json
import logging

from app.sources.registry import source_registry

logger = logging.getLogger(__name__)

# OpenAI-compatible tool definitions for function calling
SEARCH_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_papers",
            "description": "Search for academic papers using a specific data source. Use this to execute search queries against OpenAlex, arXiv, or Scopus.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query string. Can include Boolean operators (AND, OR) for precision.",
                    },
                    "source": {
                        "type": "string",
                        "enum": ["openalex", "arxiv", "scopus"],
                        "description": "Data source to search.",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return.",
                        "default": 50,
                    },
                    "year_from": {
                        "type": "integer",
                        "description": "Filter: minimum publication year (inclusive).",
                    },
                    "year_to": {
                        "type": "integer",
                        "description": "Filter: maximum publication year (inclusive).",
                    },
                },
                "required": ["query", "source"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "refine_query",
            "description": "Generate a refined search query based on initial results. Use this when initial results are too broad or too narrow.",
            "parameters": {
                "type": "object",
                "properties": {
                    "original_query": {
                        "type": "string",
                        "description": "The original search query.",
                    },
                    "refinement": {
                        "type": "string",
                        "description": "How to refine: 'narrow' to add specificity, 'broaden' to relax constraints, 'pivot' to try different terms.",
                    },
                    "new_query": {
                        "type": "string",
                        "description": "The refined query string.",
                    },
                    "source": {
                        "type": "string",
                        "enum": ["openalex", "arxiv", "scopus"],
                        "description": "Data source for the refined search.",
                    },
                },
                "required": ["original_query", "refinement", "new_query", "source"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_paper_details",
            "description": "Get full details of a specific paper by its identifier (DOI, arXiv ID, or OpenAlex ID).",
            "parameters": {
                "type": "object",
                "properties": {
                    "paper_id": {
                        "type": "string",
                        "description": "Paper identifier (DOI, arXiv ID, OpenAlex ID, or Scopus EID).",
                    },
                    "source": {
                        "type": "string",
                        "enum": ["openalex", "arxiv", "scopus"],
                        "description": "Data source to query.",
                    },
                },
                "required": ["paper_id", "source"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_complete",
            "description": "Signal that the search execution is complete. Call this when all planned queries have been executed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {
                        "type": "string",
                        "description": "Brief summary of what was found.",
                    },
                    "total_queries_executed": {
                        "type": "integer",
                        "description": "Total number of search queries executed.",
                    },
                },
                "required": ["summary"],
            },
        },
    },
]


async def execute_tool(name: str, arguments: str | dict) -> dict:
    """Execute a tool call and return the result."""
    if isinstance(arguments, str):
        args = json.loads(arguments)
    else:
        args = arguments

    if name == "search_papers":
        return await _search_papers(**args)
    elif name == "refine_query":
        return await _refine_query(**args)
    elif name == "get_paper_details":
        return await _get_paper_details(**args)
    elif name == "search_complete":
        return {"status": "complete", "summary": args.get("summary", "")}
    else:
        return {"error": f"Unknown tool: {name}"}


async def _search_papers(
    query: str,
    source: str,
    max_results: int = 50,
    year_from: int | None = None,
    year_to: int | None = None,
) -> dict:
    """Execute a search query against a data source."""
    src = source_registry.get(source)
    if not src:
        return {"error": f"Source '{source}' not available", "results": []}

    try:
        results = await src.search(
            query=query,
            max_results=max_results,
            year_from=year_from,
            year_to=year_to,
        )
        return {
            "source": source,
            "query": query,
            "total_results": len(results),
            "papers": [
                {
                    "title": p.title,
                    "year": p.year,
                    "citations": p.citation_count,
                    "doi": p.doi,
                    "source": p.source_name,
                }
                for p in results[:10]  # Summary of first 10 for context
            ],
            "_full_results": results,  # Internal: full results for saving
        }
    except Exception as e:
        logger.error(f"Search tool error: {e}")
        return {"error": str(e), "results": []}


async def _refine_query(
    original_query: str,
    refinement: str,
    new_query: str,
    source: str,
) -> dict:
    """Execute a refined search."""
    return await _search_papers(query=new_query, source=source)


async def _get_paper_details(paper_id: str, source: str) -> dict:
    """Get details of a specific paper."""
    src = source_registry.get(source)
    if not src:
        return {"error": f"Source '{source}' not available"}

    try:
        paper = await src.get_paper_by_id(paper_id)
        if paper:
            return {
                "title": paper.title,
                "abstract": paper.abstract[:500],
                "authors": [a["name"] for a in paper.authors[:5]],
                "year": paper.year,
                "citations": paper.citation_count,
                "doi": paper.doi,
                "journal": paper.journal,
            }
        return {"error": "Paper not found"}
    except Exception as e:
        return {"error": str(e)}
