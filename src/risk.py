"""Portfolio risk, drawdown, and historical stress-testing analytics."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.config import STRESS_WINDOWS


TRADING_DAYS = 252


def simple_returns(levels: pd.DataFrame) -> pd.DataFrame:
    """Decimal daily returns for investable price series."""
    return levels.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan)


def normalize_weights(weights: dict[str, float] | pd.Series) -> pd.Series:
    """Validate and normalize long-only portfolio weights to one."""
    clean = pd.Series(weights, dtype=float)
    if clean.empty:
        raise ValueError("At least one portfolio weight is required")
    if (clean < 0).any():
        raise ValueError("This dashboard currently supports non-negative weights")
    if clean.sum() <= 0:
        raise ValueError("Portfolio weights must sum to more than zero")
    return clean / clean.sum()


def portfolio_returns(levels: pd.DataFrame, weights: dict[str, float] | pd.Series) -> pd.Series:
    """Calculate rebalanced daily portfolio returns."""
    normalized = normalize_weights(weights)
    missing = sorted(set(normalized.index) - set(levels.columns))
    if missing:
        raise KeyError(f"Missing level series: {missing}")
    returns = simple_returns(levels[normalized.index]).dropna(how="all")
    returns = returns.dropna()
    output = returns.mul(normalized, axis=1).sum(axis=1)
    output.name = "Portfolio"
    return output


def max_drawdown(returns: pd.Series) -> float:
    wealth = (1.0 + returns.dropna()).cumprod()
    return float((wealth / wealth.cummax() - 1.0).min()) if not wealth.empty else np.nan


def risk_metrics(
    returns: pd.Series,
    benchmark_returns: pd.Series | None = None,
    risk_free_rate: float = 0.02,
    confidence: float = 0.95,
) -> dict[str, float]:
    """Annualized performance and historical tail-risk statistics."""
    clean = returns.dropna()
    if clean.empty:
        raise ValueError("No valid returns supplied")
    annual_return = float((1.0 + clean).prod() ** (TRADING_DAYS / len(clean)) - 1.0)
    annual_volatility = float(clean.std(ddof=1) * np.sqrt(TRADING_DAYS))
    sharpe = (annual_return - risk_free_rate) / annual_volatility if annual_volatility else np.nan
    cutoff = float(clean.quantile(1.0 - confidence))
    tail = clean[clean <= cutoff]
    expected_shortfall = float(tail.mean()) if not tail.empty else cutoff

    beta = np.nan
    if benchmark_returns is not None:
        paired = pd.concat([clean, benchmark_returns.rename("benchmark")], axis=1).dropna()
        if len(paired) > 1 and paired["benchmark"].var(ddof=1) > 0:
            beta = float(paired.iloc[:, 0].cov(paired["benchmark"]) / paired["benchmark"].var(ddof=1))

    return {
        "Annualized Return": annual_return,
        "Annualized Volatility": annual_volatility,
        "Sharpe Ratio": float(sharpe),
        "Beta vs SPY": beta,
        f"Historical VaR ({confidence:.0%})": cutoff,
        f"Expected Shortfall ({confidence:.0%})": expected_shortfall,
        "Maximum Drawdown": max_drawdown(clean),
    }


def stress_test(
    returns: pd.Series,
    windows: dict[str, tuple[str, str]] | None = None,
) -> pd.DataFrame:
    """Measure portfolio performance inside named historical stress windows."""
    windows = windows or STRESS_WINDOWS
    rows: list[dict[str, float | str | int]] = []
    for scenario, (start, end) in windows.items():
        sample = returns.loc[pd.Timestamp(start) : pd.Timestamp(end)].dropna()
        if sample.empty:
            rows.append(
                {
                    "Scenario": scenario,
                    "Start": start,
                    "End": end,
                    "Observations": 0,
                    "Cumulative Return": np.nan,
                    "Volatility": np.nan,
                    "Max Drawdown": np.nan,
                }
            )
            continue
        rows.append(
            {
                "Scenario": scenario,
                "Start": start,
                "End": end,
                "Observations": len(sample),
                "Cumulative Return": float((1.0 + sample).prod() - 1.0),
                "Volatility": float(sample.std(ddof=1) * np.sqrt(TRADING_DAYS)),
                "Max Drawdown": max_drawdown(sample),
            }
        )
    return pd.DataFrame(rows).set_index("Scenario")


def component_risk_contribution(
    levels: pd.DataFrame, weights: dict[str, float] | pd.Series
) -> pd.DataFrame:
    """Euler volatility contribution under a covariance risk model."""
    normalized = normalize_weights(weights)
    returns = simple_returns(levels[normalized.index]).dropna()
    covariance = returns.cov() * TRADING_DAYS
    portfolio_variance = float(normalized.to_numpy() @ covariance.to_numpy() @ normalized.to_numpy())
    portfolio_volatility = np.sqrt(portfolio_variance)
    marginal = covariance.to_numpy() @ normalized.to_numpy() / portfolio_volatility
    component = normalized.to_numpy() * marginal
    return pd.DataFrame(
        {
            "Weight": normalized,
            "Marginal Risk": marginal,
            "Risk Contribution": component,
            "Risk Share": component / component.sum(),
        },
        index=normalized.index,
    )

