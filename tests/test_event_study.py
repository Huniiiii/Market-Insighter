import pandas as pd
import pytest

from src.event_study import aggregate_event_paths, event_snapshot, run_event_study


def test_event_study_uses_day_minus_one_baseline():
    index = pd.bdate_range("2026-01-01", periods=12)
    levels = pd.DataFrame(
        {"SPY": [100, 101, 102, 103, 104, 106, 108, 109, 110, 111, 112, 113]},
        index=index,
    )
    events = pd.DataFrame({"date": [index[5]], "event": ["Test event"]})
    study = run_event_study(levels, events, ["SPY"], pre_days=2, post_days=3)
    day_zero = study.loc[study["relative_day"] == 0, "cumulative_move"].iloc[0]
    assert day_zero == pytest.approx((106 / 104 - 1) * 100)


def test_event_study_aggregation_and_snapshot():
    index = pd.bdate_range("2026-01-01", periods=20)
    levels = pd.DataFrame({"SPY": range(100, 120)}, index=index)
    events = pd.DataFrame({"date": [index[5], index[12]], "event": ["A", "B"]})
    study = run_event_study(levels, events, ["SPY"], 2, 3)
    aggregate = aggregate_event_paths(study)
    snapshot = event_snapshot(study, (0, 1, 3))
    assert aggregate["observations"].max() == 2
    assert {"Day +0", "Day +1", "Day +3"}.issubset(snapshot.columns)

