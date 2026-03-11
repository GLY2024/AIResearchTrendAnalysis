from types import SimpleNamespace

from app.analysis.trend_detection import run_trend_analysis


def _paper(year: int, citations: int, keywords: list[str] | None = None):
    return SimpleNamespace(year=year, citation_count=citations, keywords=keywords or [])


def test_trend_analysis_returns_consistent_shape_for_single_year_data():
    papers = [
        _paper(2024, 10, ["llm", "hallucination"]),
        _paper(2024, 5, ["llm"]),
    ]

    result, charts = run_trend_analysis(papers)

    assert charts == []
    assert result["growth_trend"] == "insufficient_data"
    assert result["early_avg_papers_per_year"] == 0.0
    assert result["late_avg_papers_per_year"] == 0.0
    assert result["emerging_keywords"] == []
    assert result["yearly_data"] == {"2024": {"count": 2, "citations": 15}}


def test_trend_analysis_calculates_growth_and_emerging_keywords():
    papers = [
        _paper(2021, 3, ["transformer", "nlp"]),
        _paper(2022, 4, ["transformer", "nlp"]),
        _paper(2023, 8, ["rag", "llm"]),
        _paper(2023, 9, ["rag", "llm"]),
        _paper(2024, 10, ["rag", "llm"]),
        _paper(2024, 12, ["rag", "agent"]),
    ]

    result, charts = run_trend_analysis(papers)

    assert result["growth_trend"] == "growing"
    assert result["yearly_data"]["2023"]["count"] == 2
    assert any(item["keyword"] == "rag" for item in result["emerging_keywords"])
    assert len(charts) == 2
