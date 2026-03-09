"""ECharts configuration generator for analysis visualizations."""

import logging

logger = logging.getLogger(__name__)

# Default ECharts theme settings for glassmorphism UI
DEFAULT_THEME = {
    "backgroundColor": "transparent",
    "textStyle": {"color": "rgba(255, 255, 255, 0.85)"},
    "title": {"textStyle": {"color": "rgba(255, 255, 255, 0.9)"}},
    "legend": {"textStyle": {"color": "rgba(255, 255, 255, 0.7)"}},
}

# Color palette for charts
COLOR_PALETTE = [
    "#6366f1",  # indigo
    "#8b5cf6",  # violet
    "#ec4899",  # pink
    "#f97316",  # orange
    "#14b8a6",  # teal
    "#06b6d4",  # cyan
    "#84cc16",  # lime
    "#f59e0b",  # amber
    "#ef4444",  # red
    "#3b82f6",  # blue
]


def apply_theme(chart_config: dict) -> dict:
    """Apply glassmorphism theme to an ECharts config."""
    option = chart_config.get("option", {})

    # Apply default theme
    option.setdefault("backgroundColor", DEFAULT_THEME["backgroundColor"])
    option.setdefault("textStyle", DEFAULT_THEME["textStyle"])

    # Apply color palette
    option.setdefault("color", COLOR_PALETTE)

    # Style axes
    for axis_key in ("xAxis", "yAxis"):
        axis = option.get(axis_key)
        if isinstance(axis, dict):
            axis.setdefault("axisLine", {"lineStyle": {"color": "rgba(255,255,255,0.2)"}})
            axis.setdefault("splitLine", {"lineStyle": {"color": "rgba(255,255,255,0.05)"}})
        elif isinstance(axis, list):
            for ax in axis:
                ax.setdefault("axisLine", {"lineStyle": {"color": "rgba(255,255,255,0.2)"}})
                ax.setdefault("splitLine", {"lineStyle": {"color": "rgba(255,255,255,0.05)"}})

    # Style tooltip
    tooltip = option.get("tooltip", {})
    tooltip.setdefault("backgroundColor", "rgba(30, 30, 46, 0.9)")
    tooltip.setdefault("borderColor", "rgba(255, 255, 255, 0.1)")
    tooltip.setdefault("textStyle", {"color": "rgba(255, 255, 255, 0.9)"})
    option["tooltip"] = tooltip

    chart_config["option"] = option
    return chart_config


def theme_all_charts(charts: list[dict]) -> list[dict]:
    """Apply theme to all charts in a list."""
    return [apply_theme(c) for c in charts]
