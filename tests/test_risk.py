import numpy as np
import pandas as pd
import pytest

from src.risk import component_risk_contribution, portfolio_returns, risk_metrics, stress_test


def _levels():
    index = pd.bdate_range("2008-09-01", periods=160)
    a = 100 * np.cumprod(np.repeat(1.001, len(index)))
    b = 100 * np.cumprod(np.tile([1.002, 0.999], len(index) // 2))
    return pd.DataFrame({"A": a, "B": b}, index=index)


def test_portfolio_weights_are_normalized():
    returns = portfolio_returns(_levels(), {"A": 60, "B": 40})
    expected = _levels().pct_change(fill_method=None).dropna().mul([0.6, 0.4]).sum(axis=1)
    pd.testing.assert_series_equal(returns, expected.rename("Portfolio"))


def test_risk_metrics_and_contributions():
    levels = _levels()
    returns = portfolio_returns(levels, {"A": 0.5, "B": 0.5})
    metrics = risk_metrics(returns)
    contributions = component_risk_contribution(levels, {"A": 0.5, "B": 0.5})
    assert metrics["Annualized Volatility"] >= 0
    assert contributions["Risk Share"].sum() == pytest.approx(1.0)


def test_stress_test_keeps_missing_scenarios_visible():
    returns = portfolio_returns(_levels(), {"A": 1.0})
    result = stress_test(returns, {"Inside": ("2008-09-15", "2008-10-01"), "Outside": ("2020-01-01", "2020-02-01")})
    assert result.loc["Inside", "Observations"] > 0
    assert result.loc["Outside", "Observations"] == 0


def test_negative_weights_are_rejected():
    with pytest.raises(ValueError, match="non-negative"):
        portfolio_returns(_levels(), {"A": 1.2, "B": -0.2})

