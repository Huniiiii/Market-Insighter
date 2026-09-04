import numpy as np
import pandas as pd

from src.commentary import generate_market_commentary


def test_commentary_is_auditable_and_includes_disclaimer():
    index = pd.bdate_range("2025-01-01", periods=100)
    levels = pd.DataFrame(
        {
            "SPY": 100 * np.exp(np.linspace(0, 0.2, 100)),
            "WTI": 70 * np.exp(np.linspace(0, 0.1, 100)),
            "USDCAD": 1.4 * np.exp(np.linspace(0, -0.03, 100)),
        },
        index=index,
    )
    comments = generate_market_commentary(levels, 20)
    assert any("WTI/USDCAD" in item for item in comments)
    assert "not proof of causality" in comments[-1]

