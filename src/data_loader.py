"""Data ingestion for live FRED/Yahoo data and the offline demo dataset."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd
import requests
import yfinance as yf
from dotenv import load_dotenv

from src.config import SAMPLE_DIR, SERIES, SeriesSpec


load_dotenv()


class DataLoadError(RuntimeError):
    """Raised when a requested market or macro series cannot be loaded."""


@dataclass
class DataBundle:
    levels: pd.DataFrame
    events: pd.DataFrame
    source_label: str
    warnings: list[str]


def _validate_dates(start: str | pd.Timestamp, end: str | pd.Timestamp) -> tuple[pd.Timestamp, pd.Timestamp]:
    start_ts = pd.Timestamp(start).normalize()
    end_ts = pd.Timestamp(end).normalize()
    if start_ts >= end_ts:
        raise ValueError("start must be earlier than end")
    return start_ts, end_ts


def fetch_yahoo_series(
    specs: dict[str, SeriesSpec], start: str | pd.Timestamp, end: str | pd.Timestamp
) -> pd.DataFrame:
    """Download adjusted closing levels from Yahoo Finance."""
    start_ts, end_ts = _validate_dates(start, end)
    if not specs:
        return pd.DataFrame()

    symbol_to_name = {spec.symbol: name for name, spec in specs.items()}
    raw = yf.download(
        tickers=list(symbol_to_name),
        start=start_ts,
        end=end_ts + pd.Timedelta(days=1),
        auto_adjust=True,
        progress=False,
        group_by="column",
        threads=True,
    )
    if raw.empty:
        raise DataLoadError("Yahoo Finance returned no observations.")

    if isinstance(raw.columns, pd.MultiIndex):
        close = raw["Close"].copy()
    else:
        close = raw[["Close"]].copy()
        close.columns = list(symbol_to_name)

    if isinstance(close, pd.Series):
        close = close.to_frame()
    close = close.rename(columns=symbol_to_name)
    close.index = pd.to_datetime(close.index).tz_localize(None).normalize()
    return close.sort_index().apply(pd.to_numeric, errors="coerce")


def fetch_fred_series(
    specs: dict[str, SeriesSpec],
    start: str | pd.Timestamp,
    end: str | pd.Timestamp,
    api_key: str | None = None,
) -> pd.DataFrame:
    """Download macro series from the official FRED API."""
    start_ts, end_ts = _validate_dates(start, end)
    key = (api_key or os.getenv("FRED_API_KEY", "")).strip()
    if not key:
        raise DataLoadError("FRED_API_KEY is blank. Add it to .env or Streamlit secrets.")

    frames: list[pd.Series] = []
    endpoint = "https://api.stlouisfed.org/fred/series/observations"
    for name, spec in specs.items():
        try:
            response = requests.get(
                endpoint,
                params={
                    "series_id": spec.symbol,
                    "api_key": key,
                    "file_type": "json",
                    "observation_start": start_ts.date().isoformat(),
                    "observation_end": end_ts.date().isoformat(),
                },
                timeout=30,
            )
            response.raise_for_status()
            observations = response.json()["observations"]
        except requests.RequestException as exc:
            # Request exceptions may contain the full URL, including the API key.
            # Keep user-facing errors generic so Streamlit never renders credentials.
            raise DataLoadError(
                f"FRED request failed for {name}. Check the service and API key."
            ) from exc
        except (KeyError, TypeError, ValueError) as exc:
            raise DataLoadError(f"FRED returned an invalid response for {name}.") from exc

        frame = pd.DataFrame(observations)
        if frame.empty:
            continue
        values = pd.to_numeric(frame["value"].replace(".", pd.NA), errors="coerce")
        frames.append(pd.Series(values.to_numpy(), index=pd.to_datetime(frame["date"]), name=name))

    if not frames:
        raise DataLoadError("FRED returned no observations.")
    return pd.concat(frames, axis=1).sort_index()


def fetch_live_levels(
    series_names: Iterable[str],
    start: str | pd.Timestamp,
    end: str | pd.Timestamp,
    fred_api_key: str | None = None,
) -> tuple[pd.DataFrame, list[str]]:
    """Fetch selected series, preserving partial results if one provider fails."""
    selected = list(dict.fromkeys(series_names))
    unknown = sorted(set(selected) - set(SERIES))
    if unknown:
        raise KeyError(f"Unknown series: {unknown}")

    yahoo_specs = {name: SERIES[name] for name in selected if SERIES[name].source == "yahoo"}
    fred_specs = {name: SERIES[name] for name in selected if SERIES[name].source == "fred"}
    frames: list[pd.DataFrame] = []
    warnings: list[str] = []

    if yahoo_specs:
        try:
            frames.append(fetch_yahoo_series(yahoo_specs, start, end))
        except Exception as exc:  # surface provider failure while allowing FRED results
            warnings.append(str(exc))
    if fred_specs:
        try:
            frames.append(fetch_fred_series(fred_specs, start, end, fred_api_key))
        except DataLoadError as exc:
            warnings.append(str(exc))
        except Exception:
            warnings.append("FRED download failed unexpectedly.")

    if not frames:
        raise DataLoadError("No live series could be loaded. " + " | ".join(warnings))

    levels = pd.concat(frames, axis=1).sort_index()
    levels = levels.loc[:, [name for name in selected if name in levels.columns]]
    levels.index.name = "date"
    return levels, warnings


def load_sample_levels(path: Path | None = None) -> pd.DataFrame:
    """Load deterministic sample levels bundled with the repository."""
    sample_path = path or SAMPLE_DIR / "market_data.csv"
    if not sample_path.exists():
        raise DataLoadError(
            f"Sample data not found at {sample_path}. Run `python scripts/generate_sample_assets.py`."
        )
    data = pd.read_csv(sample_path, parse_dates=["date"], index_col="date")
    return data.sort_index().apply(pd.to_numeric, errors="coerce")


def load_events(path: Path | None = None) -> pd.DataFrame:
    """Load an event calendar with required date/name columns."""
    event_path = path or SAMPLE_DIR / "events.csv"
    events = pd.read_csv(event_path, parse_dates=["date"])
    required = {"date", "event"}
    missing = required - set(events.columns)
    if missing:
        raise DataLoadError(f"Event file is missing columns: {sorted(missing)}")
    return events.sort_values("date").reset_index(drop=True)


def load_data_bundle(
    mode: str = "Demo data",
    series_names: Iterable[str] | None = None,
    start: str | pd.Timestamp = "2019-01-01",
    end: str | pd.Timestamp | None = None,
    fred_api_key: str | None = None,
) -> DataBundle:
    """Single app entry point for demo or live data."""
    end = end or pd.Timestamp.today().normalize()
    events = load_events()
    if mode == "Live data":
        names = list(series_names or SERIES)
        levels, warnings = fetch_live_levels(names, start, end, fred_api_key)
        return DataBundle(levels, events, "Live: FRED + Yahoo Finance", warnings)

    levels = load_sample_levels()
    levels = levels.loc[pd.Timestamp(start) : pd.Timestamp(end)]
    if series_names:
        levels = levels[[name for name in series_names if name in levels.columns]]
    return DataBundle(levels, events, "Illustrative offline demo", [])
