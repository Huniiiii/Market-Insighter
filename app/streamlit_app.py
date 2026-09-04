"""Interactive sell-side-style dashboard for Market Insighter."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.charts import (  # noqa: E402
    correlation_heatmap,
    event_path_chart,
    performance_chart,
    portfolio_drawdown_chart,
    rolling_correlation_chart,
)
from src.commentary import generate_market_commentary  # noqa: E402
from src.config import DEFAULT_ASSETS, SERIES  # noqa: E402
from src.data_loader import DataLoadError, load_data_bundle  # noqa: E402
from src.event_study import aggregate_event_paths, event_snapshot, run_event_study  # noqa: E402
from src.indicators import latest_change_table, to_moves  # noqa: E402
from src.risk import (  # noqa: E402
    component_risk_contribution,
    portfolio_returns,
    risk_metrics,
    simple_returns,
    stress_test,
)


st.set_page_config(
    page_title="Market Insighter | Huni Personal Project",
    page_icon="MI",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .stApp { background: #08111f; color: #e8eef7; }
    [data-testid="stSidebar"] { background: #0c1728; border-right: 1px solid #20314b; }
    [data-testid="stMetric"] {
        background: linear-gradient(145deg, #101e32, #0d192b);
        border: 1px solid #203651; border-radius: 12px; padding: 16px;
    }
    [data-testid="stMetricLabel"] { color: #9fb0c7; }
    div[data-testid="stDataFrame"] { border: 1px solid #203651; border-radius: 10px; }
    .research-tag {
        color: #63d6c5; letter-spacing: .12em; text-transform: uppercase;
        font-size: .75rem; font-weight: 700; margin-bottom: .25rem;
    }
    .subtle { color: #91a3ba; font-size: .9rem; }
    .commentary-card {
        background: #101e32; border-left: 4px solid #63d6c5;
        border-radius: 8px; padding: .75rem 1rem; margin: .55rem 0;
    }
    h1, h2, h3 { letter-spacing: -.02em; }
    </style>
    """,
    unsafe_allow_html=True,
)


def _secret(name: str) -> str:
    value = os.getenv(name, "")
    if value:
        return value
    try:
        return str(st.secrets.get(name, ""))
    except (FileNotFoundError, KeyError):
        return ""


@st.cache_data(ttl=3600, show_spinner=False)
def get_bundle(
    mode: str, selected: tuple[str, ...], start: pd.Timestamp, end: pd.Timestamp, fred_key: str
):
    return load_data_bundle(mode, selected, start, end, fred_key)


def _metric_delta(row: pd.Series) -> str:
    value = row["1W"]
    if pd.isna(value):
        return "n/a"
    unit = row["change_unit"]
    return f"{value:+.1f} bps (1W)" if unit == "bps" else f"{value:+.2f}% (1W)"


def _fmt_level(name: str, value: float) -> str:
    if name == "USDKRW":
        return f"{value:,.1f}"
    if name in {"US10Y", "FEDFUNDS"}:
        return f"{value:.2f}%"
    return f"{value:,.2f}"


with st.sidebar:
    st.markdown("### Market Insighter")
    st.caption("Macro and cross-asset research platform")
    mode = st.radio("Data source", ["Demo data", "Live data"], horizontal=True)
    default_start = pd.Timestamp("2007-01-01") if mode == "Demo data" else pd.Timestamp.today() - pd.DateOffset(years=5)
    start = st.date_input("Start date", value=default_start.date())
    end = st.date_input("End date", value=pd.Timestamp.today().date())
    selected = st.multiselect(
        "Series",
        options=list(SERIES),
        default=DEFAULT_ASSETS,
        format_func=lambda name: f"{name} - {SERIES[name].label}",
    )
    st.divider()
    st.markdown("**Research questions**")
    st.caption("How do oil shocks affect CAD and KRW?")
    st.caption("How do Treasury yields affect growth and financial assets?")
    st.caption("Which assets are most sensitive around CPI releases?")


if len(selected) < 2:
    st.warning("Select at least two series from the sidebar.")
    st.stop()

try:
    bundle = get_bundle(
        mode,
        tuple(selected),
        pd.Timestamp(start),
        pd.Timestamp(end),
        _secret("FRED_API_KEY"),
    )
except (DataLoadError, ValueError, KeyError) as exc:
    st.error(f"Live download could not complete: {exc}")
    st.info("Showing the bundled offline demo so the dashboard remains usable.")
    bundle = get_bundle(
        "Demo data", tuple(selected), pd.Timestamp(start), pd.Timestamp(end), ""
    )

levels = bundle.levels.dropna(how="all")
if levels.empty:
    st.error("No observations fall inside the selected date range.")
    st.stop()

st.markdown('<div class="research-tag">Cross-Asset Strategy Lab</div>', unsafe_allow_html=True)
st.title("Market Insighter")
st.markdown(
    f'<div class="subtle">{bundle.source_label} | {levels.index.min():%d %b %Y} to '
    f'{levels.index.max():%d %b %Y} | Educational analytics, not investment advice</div>',
    unsafe_allow_html=True,
)
for warning in bundle.warnings:
    st.warning(warning)

overview_tab, cross_tab, event_tab, risk_tab, data_tab = st.tabs(
    ["Market Overview", "Cross-Asset", "Event Study", "Portfolio Risk", "Data Explorer"]
)

with overview_tab:
    changes = latest_change_table(levels)
    metric_names = [name for name in ("SPY", "WTI", "US10Y", "USDCAD", "USDKRW") if name in changes.index]
    columns = st.columns(len(metric_names))
    for column, name in zip(columns, metric_names):
        row = changes.loc[name]
        column.metric(name, _fmt_level(name, float(row["level"])), _metric_delta(row))

    st.plotly_chart(performance_chart(levels.dropna(axis=1, how="all")), width="stretch")
    st.subheader("Desk commentary")
    for item in generate_market_commentary(levels):
        st.markdown(f'<div class="commentary-card">{item}</div>', unsafe_allow_html=True)
    with st.expander("How the commentary is produced"):
        st.write(
            "The text is deterministic and auditable: it summarizes the latest weekly moves and "
            "60-day rolling correlations. It deliberately describes relationships without claiming "
            "causality. No LLM or API key is required."
        )

with cross_tab:
    left_col, right_col, window_col = st.columns([2, 2, 1])
    left = left_col.selectbox("First series", list(levels.columns), index=0)
    right_options = [name for name in levels.columns if name != left]
    right = right_col.selectbox("Second series", right_options, index=0)
    window = window_col.selectbox("Window", [20, 60, 120, 252], index=1)
    st.plotly_chart(
        rolling_correlation_chart(levels, left, right, int(window)), width="stretch"
    )
    st.plotly_chart(correlation_heatmap(levels), width="stretch")
    moves = to_moves(levels)
    unusual = (
        moves.tail(252).apply(lambda series: (series - series.mean()) / series.std(ddof=1)).iloc[-1]
    )
    unusual = unusual.dropna().sort_values(key=abs, ascending=False).rename("Latest z-score")
    st.markdown("#### Latest move monitor")
    st.dataframe(unusual.to_frame().style.format("{:+.2f}"), width="stretch")

with event_tab:
    events = bundle.events.copy()
    categories = ["All"] + sorted(events["category"].dropna().unique().tolist())
    category = st.selectbox("Event category", categories)
    filtered_events = events if category == "All" else events[events["category"] == category]
    event_assets = st.multiselect(
        "Assets for event study",
        options=list(levels.columns),
        default=[name for name in ("SPY", "XLF", "WTI", "USDCAD", "USDKRW", "US10Y") if name in levels],
    )
    pre_col, post_col = st.columns(2)
    pre_days = pre_col.slider("Trading days before", 1, 20, 5)
    post_days = post_col.slider("Trading days after", 1, 30, 10)
    study = run_event_study(levels, filtered_events, event_assets, pre_days, post_days)
    aggregate = aggregate_event_paths(study)
    if aggregate.empty:
        st.info("No complete event windows are available for this selection.")
    else:
        st.plotly_chart(event_path_chart(aggregate), width="stretch")
        st.markdown("#### Average response by horizon")
        snapshot = event_snapshot(study, tuple(sorted({0, 1, min(5, post_days), post_days})))
        st.dataframe(
            snapshot.style.format({column: "{:+.2f}" for column in snapshot if column.startswith("Day")}),
            width="stretch",
        )
        st.caption(
            "Price assets are cumulative percent returns; Treasury yields are cumulative basis-point changes. "
            "Demo events and data are illustrative."
        )

with risk_tab:
    investable = [name for name in ("SPY", "XLF", "XLE", "WTI") if name in levels]
    if not investable:
        st.info("Add SPY, XLF, XLE, or WTI to run the portfolio module.")
    else:
        st.markdown("#### Portfolio weights")
        weight_columns = st.columns(len(investable))
        default_weights = {"SPY": 40, "XLF": 25, "XLE": 20, "WTI": 15}
        raw_weights = {
            name: column.number_input(
                name, min_value=0.0, max_value=100.0, value=float(default_weights.get(name, 25)), step=5.0
            )
            for column, name in zip(weight_columns, investable)
        }
        if sum(raw_weights.values()) <= 0:
            st.warning("At least one weight must be positive.")
        else:
            portfolio = portfolio_returns(levels, raw_weights)
            benchmark = simple_returns(levels[["SPY"]])["SPY"] if "SPY" in levels else None
            confidence = st.select_slider("Tail-risk confidence", [0.90, 0.95, 0.975, 0.99], value=0.95)
            metrics = risk_metrics(portfolio, benchmark, confidence=float(confidence))
            metric_cols = st.columns(4)
            display = [
                ("Annualized Return", ".1%"),
                ("Annualized Volatility", ".1%"),
                ("Sharpe Ratio", ".2f"),
                ("Maximum Drawdown", ".1%"),
            ]
            for column, (name, fmt) in zip(metric_cols, display):
                column.metric(name, format(metrics[name], fmt))

            st.plotly_chart(portfolio_drawdown_chart(portfolio), width="stretch")
            left_panel, right_panel = st.columns(2)
            with left_panel:
                st.markdown("#### Historical stress tests")
                stress = stress_test(portfolio)
                st.dataframe(
                    stress.style.format(
                        {
                            "Cumulative Return": "{:.1%}",
                            "Volatility": "{:.1%}",
                            "Max Drawdown": "{:.1%}",
                        },
                        na_rep="n/a",
                    ),
                    width="stretch",
                )
            with right_panel:
                st.markdown("#### Component risk contribution")
                contributions = component_risk_contribution(levels, raw_weights)
                st.dataframe(
                    contributions.style.format(
                        {"Weight": "{:.1%}", "Marginal Risk": "{:.1%}", "Risk Contribution": "{:.1%}", "Risk Share": "{:.1%}"}
                    ),
                    width="stretch",
                )
            tail_names = [name for name in metrics if "VaR" in name or "Expected Shortfall" in name]
            st.caption(
                " | ".join(f"{name}: {metrics[name]:.2%}" for name in tail_names)
                + " | VaR and ES are one-day historical estimates."
            )

with data_tab:
    st.markdown("#### Level data")
    st.dataframe(levels.tail(250), width="stretch")
    st.download_button(
        "Download selected levels as CSV",
        data=levels.to_csv().encode("utf-8"),
        file_name="market_insighter_levels.csv",
        mime="text/csv",
    )
    st.markdown("#### Event calendar")
    st.dataframe(bundle.events, width="stretch", hide_index=True)
    st.caption(
        "Live market prices: Yahoo Finance. Live macro series: FRED. Bundled demo data is synthetic "
        "and is provided only for reproducible demonstrations."
    )
