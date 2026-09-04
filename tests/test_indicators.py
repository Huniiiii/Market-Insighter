import numpy as np
import pandas as pd
import pytest

from src.indicators import latest_change_table, rolling_correlation, to_moves


def test_to_moves_respects_price_and_rate_units():
    index = pd.bdate_range("2026-01-01", periods=4)
    levels = pd.DataFrame(
        {"SPY": [100.0, 101.0, 102.01, 103.0301], "US10Y": [4.00, 4.05, 4.02, 4.12]},
        index=index,
    )
    moves = to_moves(levels)
    assert moves.loc[index[1], "SPY"] == pytest.approx(0.01)
    assert moves.loc[index[1], "US10Y"] == pytest.approx(5.0)


def test_latest_change_table_labels_basis_points():
    index = pd.bdate_range("2026-01-01", periods=25)
    levels = pd.DataFrame({"US10Y": np.linspace(4.0, 4.24, 25)}, index=index)
    table = latest_change_table(levels)
    assert table.loc["US10Y", "change_unit"] == "bps"
    assert table.loc["US10Y", "1W"] == pytest.approx(5.0)


def test_rolling_correlation_rejects_same_series():
    levels = pd.DataFrame({"SPY": range(10)}, index=pd.bdate_range("2026-01-01", periods=10))
    with pytest.raises(ValueError, match="different"):
        rolling_correlation(levels, "SPY", "SPY", 5)

