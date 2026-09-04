"""Reusable event-window engine for macro announcements and market shocks."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.config import SERIES


def _trading_position(index: pd.DatetimeIndex, event_date: pd.Timestamp) -> int | None:
    """Locate the first market observation on or after an event date."""
    position = int(index.searchsorted(event_date, side="left"))
    return position if position < len(index) else None


def run_event_study(
    levels: pd.DataFrame,
    events: pd.DataFrame,
    assets: list[str],
    pre_days: int = 5,
    post_days: int = 10,
) -> pd.DataFrame:
    """Return long-form event-window moves and cumulative responses.

    Prices are expressed as cumulative percentage returns from day -1. Yield
    series are expressed as cumulative basis-point changes from day -1.
    """
    if pre_days < 1 or post_days < 1:
        raise ValueError("pre_days and post_days must both be positive")
    if not {"date", "event"}.issubset(events.columns):
        raise ValueError("events must contain date and event columns")

    clean_levels = levels.sort_index().copy()
    clean_levels.index = pd.to_datetime(clean_levels.index).tz_localize(None).normalize()
    records: list[dict] = []

    for event in events.itertuples(index=False):
        event_date = pd.Timestamp(event.date).normalize()
        event_name = str(event.event)
        position = _trading_position(clean_levels.index, event_date)
        if position is None or position - pre_days < 0 or position + post_days >= len(clean_levels):
            continue

        start_pos = position - pre_days
        end_pos = position + post_days
        window = clean_levels.iloc[start_pos : end_pos + 1]
        relative_days = np.arange(-pre_days, post_days + 1)
        baseline_idx = max(pre_days - 1, 0)

        for asset in assets:
            if asset not in window or window[asset].isna().any():
                continue
            values = window[asset].astype(float)
            method = SERIES[asset].return_method if asset in SERIES else "pct"
            if method == "diff_bps":
                cumulative = (values - values.iloc[baseline_idx]) * 100.0
                daily = values.diff() * 100.0
                unit = "bps"
            else:
                cumulative = (values / values.iloc[baseline_idx] - 1.0) * 100.0
                daily = values.pct_change(fill_method=None) * 100.0
                unit = "%"

            for i, rel_day in enumerate(relative_days):
                record = {
                    "event_date": event_date,
                    "event": event_name,
                    "asset": asset,
                    "relative_day": int(rel_day),
                    "observation_date": window.index[i],
                    "daily_move": float(daily.iloc[i]) if pd.notna(daily.iloc[i]) else np.nan,
                    "cumulative_move": float(cumulative.iloc[i]),
                    "unit": unit,
                }
                for optional in ("category", "actual", "consensus", "surprise"):
                    if hasattr(event, optional):
                        record[optional] = getattr(event, optional)
                records.append(record)
    return pd.DataFrame.from_records(records)


def aggregate_event_paths(study: pd.DataFrame) -> pd.DataFrame:
    """Average cumulative path across events, with dispersion bands."""
    if study.empty:
        return pd.DataFrame()
    return (
        study.groupby(["asset", "unit", "relative_day"])["cumulative_move"]
        .agg(mean="mean", median="median", std="std", observations="count")
        .reset_index()
    )


def event_snapshot(study: pd.DataFrame, horizons: tuple[int, ...] = (0, 1, 5, 10)) -> pd.DataFrame:
    """Summarize each asset's average response at selected event horizons."""
    if study.empty:
        return pd.DataFrame()
    subset = study[study["relative_day"].isin(horizons)]
    table = subset.pivot_table(
        index=["asset", "unit"],
        columns="relative_day",
        values="cumulative_move",
        aggfunc="mean",
    )
    table.columns = [f"Day {int(day):+d}" for day in table.columns]
    return table.reset_index()

