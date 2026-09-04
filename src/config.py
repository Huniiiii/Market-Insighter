"""Central configuration and the cross-asset data dictionary."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
SAMPLE_DIR = DATA_DIR / "sample"


@dataclass(frozen=True)
class SeriesSpec:
    label: str
    source: str
    symbol: str
    asset_class: str
    unit: str
    return_method: str = "pct"


SERIES: dict[str, SeriesSpec] = {
    "SPY": SeriesSpec("S&P 500 ETF", "yahoo", "SPY", "Equity", "Index", "pct"),
    "XLF": SeriesSpec("US Financials ETF", "yahoo", "XLF", "Equity", "Price", "pct"),
    "XLE": SeriesSpec("US Energy ETF", "yahoo", "XLE", "Equity", "Price", "pct"),
    "WTI": SeriesSpec("WTI Crude Oil", "yahoo", "CL=F", "Commodity", "USD/bbl", "pct"),
    "USDCAD": SeriesSpec("USD/CAD", "yahoo", "CAD=X", "FX", "CAD per USD", "pct"),
    "USDKRW": SeriesSpec("USD/KRW", "yahoo", "KRW=X", "FX", "KRW per USD", "pct"),
    "US10Y": SeriesSpec("US 10Y Treasury", "fred", "DGS10", "Rates", "%", "diff_bps"),
    "FEDFUNDS": SeriesSpec("Effective Fed Funds", "fred", "DFF", "Rates", "%", "diff_bps"),
    "CPI": SeriesSpec("US CPI All Urban", "fred", "CPIAUCSL", "Macro", "Index", "yoy"),
}


DEFAULT_ASSETS = ["SPY", "XLF", "XLE", "WTI", "USDCAD", "USDKRW", "US10Y"]

STRESS_WINDOWS = {
    "Global Financial Crisis": ("2008-09-15", "2009-03-09"),
    "COVID Selloff": ("2020-02-19", "2020-03-23"),
    "2022 Rates Shock": ("2022-01-03", "2022-10-14"),
}


def series_metadata() -> dict[str, dict[str, str]]:
    """Return JSON-friendly metadata used by the app and loaders."""
    return {
        key: {
            "label": spec.label,
            "source": spec.source,
            "symbol": spec.symbol,
            "asset_class": spec.asset_class,
            "unit": spec.unit,
            "return_method": spec.return_method,
        }
        for key, spec in SERIES.items()
    }

