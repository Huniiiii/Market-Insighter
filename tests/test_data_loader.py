import pandas as pd
import pytest
import requests

import src.data_loader as data_loader
from src.config import SERIES
from src.data_loader import DataLoadError, fetch_fred_series, fetch_live_levels


class _FailingResponse:
    def raise_for_status(self):
        raise requests.HTTPError(
            "403 Client Error for url: "
            "https://api.stlouisfed.org/fred/series/observations?api_key=SUPER_SECRET"
        )

    def json(self):
        return {}


def test_fred_request_error_never_exposes_api_key(monkeypatch):
    monkeypatch.setattr(data_loader.requests, "get", lambda *args, **kwargs: _FailingResponse())

    with pytest.raises(DataLoadError) as error:
        fetch_fred_series(
            {"US10Y": SERIES["US10Y"]},
            pd.Timestamp("2026-01-01"),
            pd.Timestamp("2026-02-01"),
            api_key="SUPER_SECRET",
        )

    assert "SUPER_SECRET" not in str(error.value)
    assert "api_key=" not in str(error.value)


def test_unexpected_fred_error_is_sanitized(monkeypatch):
    def _raise_unexpected(*args, **kwargs):
        raise RuntimeError("SUPER_SECRET")

    monkeypatch.setattr(data_loader, "fetch_fred_series", _raise_unexpected)
    with pytest.raises(DataLoadError) as error:
        fetch_live_levels(
            ["US10Y"],
            pd.Timestamp("2026-01-01"),
            pd.Timestamp("2026-02-01"),
            fred_api_key="SUPER_SECRET",
        )

    assert "SUPER_SECRET" not in str(error.value)
    assert "FRED download failed unexpectedly." in str(error.value)
