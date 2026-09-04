"""Transparent, deterministic market commentary generation."""

from __future__ import annotations

import math

import pandas as pd

from src.indicators import latest_change_table, rolling_correlation


def _direction(value: float) -> str:
    return "rose" if value > 0 else "fell" if value < 0 else "was unchanged"


def _fmt_move(value: float, unit: str) -> str:
    return f"{abs(value):.1f} {unit}" if unit == "bps" else f"{abs(value):.2f}%"


def generate_market_commentary(levels: pd.DataFrame, correlation_window: int = 60) -> list[str]:
    """Create concise observations without inventing causal explanations."""
    changes = latest_change_table(levels)
    if changes.empty:
        return ["No valid observations are available for commentary."]

    comments: list[str] = []
    focus = [name for name in ("SPY", "WTI", "US10Y", "USDCAD", "USDKRW") if name in changes.index]
    for name in focus:
        move = float(changes.loc[name, "1W"])
        if math.isnan(move):
            continue
        unit = str(changes.loc[name, "change_unit"])
        comments.append(f"{name} {_direction(move)} {_fmt_move(move, unit)} over the latest week.")

    pairs = [("WTI", "USDCAD"), ("US10Y", "USDKRW"), ("US10Y", "SPY")]
    for left, right in pairs:
        if left not in levels or right not in levels:
            continue
        correlation = rolling_correlation(levels, left, right, correlation_window).dropna()
        if correlation.empty:
            continue
        value = float(correlation.iloc[-1])
        strength = "strong" if abs(value) >= 0.6 else "moderate" if abs(value) >= 0.3 else "weak"
        sign = "positive" if value >= 0 else "negative"
        comments.append(
            f"The {correlation_window}-day {left}/{right} move correlation is {value:+.2f}, "
            f"a {strength} {sign} relationship."
        )

    comments.append(
        "These are statistical observations, not proof of causality or an investment recommendation."
    )
    return comments


def one_paragraph_summary(levels: pd.DataFrame, correlation_window: int = 60) -> str:
    """Join the highest-signal observations for reports and the dashboard."""
    comments = generate_market_commentary(levels, correlation_window)
    return " ".join(comments[:5] + comments[-1:])

