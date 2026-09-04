"""Plotly chart constructors shared by Streamlit and notebooks."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from src.indicators import correlation_matrix, normalized_performance, rolling_correlation


COLORS = ["#63D6C5", "#FFB547", "#7AA2FF", "#F07178", "#B794F4", "#5CC8FF", "#A3BE8C"]


def _layout(fig: go.Figure, title: str, y_title: str = "") -> go.Figure:
    fig.update_layout(
        title=title,
        template="plotly_dark",
        paper_bgcolor="#0B1220",
        plot_bgcolor="#0B1220",
        font={"color": "#E7EDF6"},
        colorway=COLORS,
        hovermode="x unified",
        legend_title_text="",
        margin={"l": 25, "r": 20, "t": 55, "b": 30},
        yaxis_title=y_title,
        xaxis_title="",
    )
    return fig


def performance_chart(levels: pd.DataFrame) -> go.Figure:
    rebased = normalized_performance(levels)
    fig = px.line(rebased, x=rebased.index, y=list(rebased.columns))
    return _layout(fig, "Normalized Cross-Asset Performance", "Start = 100")


def rolling_correlation_chart(
    levels: pd.DataFrame, left: str, right: str, window: int
) -> go.Figure:
    series = rolling_correlation(levels, left, right, window)
    fig = go.Figure(go.Scatter(x=series.index, y=series, name=f"{left} vs {right}", line={"width": 2}))
    fig.add_hline(y=0, line_width=1, line_dash="dot", line_color="#6B7280")
    fig.update_yaxes(range=[-1, 1])
    return _layout(fig, f"{window}-Day Rolling Correlation: {left} vs {right}", "Correlation")


def correlation_heatmap(levels: pd.DataFrame) -> go.Figure:
    matrix = correlation_matrix(levels)
    fig = go.Figure(
        go.Heatmap(
            z=matrix.values,
            x=matrix.columns,
            y=matrix.index,
            zmin=-1,
            zmax=1,
            colorscale=[[0, "#B54747"], [0.5, "#17243A"], [1, "#3CB7A5"]],
            text=matrix.round(2).values,
            texttemplate="%{text}",
            colorbar={"title": "rho"},
        )
    )
    return _layout(fig, "Daily-Move Correlation Matrix")


def event_path_chart(aggregate: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    for i, (asset, group) in enumerate(aggregate.groupby("asset")):
        color = COLORS[i % len(COLORS)]
        fig.add_trace(
            go.Scatter(
                x=group["relative_day"],
                y=group["mean"],
                name=asset,
                mode="lines+markers",
                line={"color": color, "width": 2},
            )
        )
    fig.add_vline(x=0, line_width=1, line_dash="dash", line_color="#FFB547")
    return _layout(fig, "Average Response Around Selected Events", "Cumulative move (% or bps)")


def portfolio_drawdown_chart(portfolio_returns: pd.Series) -> go.Figure:
    wealth = (1.0 + portfolio_returns).cumprod()
    drawdown = wealth / wealth.cummax() - 1.0
    fig = go.Figure(
        go.Scatter(
            x=drawdown.index,
            y=drawdown * 100,
            fill="tozeroy",
            name="Drawdown",
            line={"color": "#F07178"},
        )
    )
    return _layout(fig, "Portfolio Drawdown", "% from peak")

