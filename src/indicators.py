"""Cross-asset transformations and rolling analytics."""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np
import pandas as pd

from src.config import SERIES


def _method(series_name: str, metadata: Mapping | None = None) -> str:
    if metadata and series_name in metadata:
        item = metadata[series_name]
        return item.get("return_method", "pct") if isinstance(item, dict) else item.return_method
    return SERIES[series_name].return_method if series_name in SERIES else "pct"


def to_moves(levels: pd.DataFrame, metadata: Mapping | None = None) -> pd.DataFrame:
    """Convert levels into comparable daily moves.

    Price/FX/commodity series are decimal returns. Rate series are basis-point
    changes. CPI is converted to year-over-year percent change.
    """
    moves = pd.DataFrame(index=levels.index)
    for column in levels:
        method = _method(column, metadata)
        series = levels[column].astype(float)
        if method == "diff_bps":
            moves[column] = series.diff() * 100.0
        elif method == "yoy":
            moves[column] = series.pct_change(12, fill_method=None) * 100.0
        else:
            moves[column] = series.pct_change(fill_method=None)
    return moves.replace([np.inf, -np.inf], np.nan)


def normalized_performance(levels: pd.DataFrame, base: float = 100.0) -> pd.DataFrame:
    """Rebase each level series to a common starting value."""
    output = pd.DataFrame(index=levels.index)
    for column in levels:
        valid = levels[column].dropna()
        if valid.empty:
            output[column] = np.nan
        else:
            output[column] = levels[column] / valid.iloc[0] * base
    return output


def rolling_correlation(
    levels: pd.DataFrame,
    left: str,
    right: str,
    window: int = 60,
    metadata: Mapping | None = None,
) -> pd.Series:
    """Rolling correlation of daily moves for two series."""
    if window < 5:
        raise ValueError("window must be at least 5 observations")
    if left == right:
        raise ValueError("Select two different series")
    moves = to_moves(levels[[left, right]], metadata)
    return moves[left].rolling(window, min_periods=max(5, window // 2)).corr(moves[right])


def correlation_matrix(levels: pd.DataFrame, metadata: Mapping | None = None) -> pd.DataFrame:
    """Full-sample correlation matrix of daily moves."""
    return to_moves(levels, metadata).corr()


def latest_change_table(levels: pd.DataFrame, metadata: Mapping | None = None) -> pd.DataFrame:
    """Latest levels and 1D/1W/1M changes with unit-aware calculations."""
    rows: list[dict[str, float | str]] = []
    for column in levels:
        series = levels[column].dropna()
        if series.empty:
            continue
        method = _method(column, metadata)
        row: dict[str, float | str] = {"series": column, "level": float(series.iloc[-1])}
        for label, periods in (("1D", 1), ("1W", 5), ("1M", 21)):
            if len(series) <= periods:
                row[label] = np.nan
            elif method == "diff_bps":
                row[label] = float((series.iloc[-1] - series.iloc[-periods - 1]) * 100.0)
            else:
                row[label] = float((series.iloc[-1] / series.iloc[-periods - 1] - 1.0) * 100.0)
        row["change_unit"] = "bps" if method == "diff_bps" else "%"
        rows.append(row)
    return pd.DataFrame(rows).set_index("series") if rows else pd.DataFrame()


def rolling_zscore(series: pd.Series, window: int = 60) -> pd.Series:
    """Rolling z-score useful for identifying unusual market moves."""
    mean = series.rolling(window, min_periods=max(5, window // 2)).mean()
    std = series.rolling(window, min_periods=max(5, window // 2)).std(ddof=1)
    return (series - mean) / std.replace(0, np.nan)


def drawdown(index_series: pd.Series) -> pd.Series:
    """Drawdown from the running high of a price or wealth index."""
    running_max = index_series.cummax()
    return index_series / running_max - 1.0

