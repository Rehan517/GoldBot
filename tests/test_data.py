"""Tests for goldbot.data: loading MT5 exports and finding data problems."""

import pandas as pd

from goldbot.data import drop_forming_bar, find_problems, load_mt5_csv

HEADER = "<DATE>\t<TIME>\t<OPEN>\t<HIGH>\t<LOW>\t<CLOSE>\t<TICKVOL>\t<VOL>\t<SPREAD>"


def write_mt5_file(tmp_path, rows):
    """Write rows in the exact MT5 export format (tabs + Windows CRLF line endings)."""
    path = tmp_path / "bars.csv"
    path.write_text("\r\n".join([HEADER, *rows]) + "\r\n")
    return path


def test_load_parses_mt5_format(tmp_path):
    path = write_mt5_file(tmp_path, [
        "2018.01.02\t09:00:00\t1309.81\t1310.17\t1308.62\t1309.28\t6186\t2538457\t36",
        "2018.01.02\t10:00:00\t1309.28\t1310.73\t1308.40\t1310.12\t7079\t3035023\t36",
    ])

    bars = load_mt5_csv(path)

    assert list(bars.columns) == ["open", "high", "low", "close", "tick_volume", "real_volume", "spread"]
    assert bars.index.name == "time"
    assert bars.index[0] == pd.Timestamp("2018-01-02 09:00:00")
    assert bars["close"].iloc[1] == 1310.12
    assert bars["spread"].iloc[0] == 36


def test_load_sorts_out_of_order_rows(tmp_path):
    path = write_mt5_file(tmp_path, [
        "2018.01.02\t10:00:00\t1\t2\t0.5\t1.5\t1\t1\t1",
        "2018.01.02\t09:00:00\t1\t2\t0.5\t1.5\t1\t1\t1",
    ])
    bars = load_mt5_csv(path)
    assert bars.index.is_monotonic_increasing


def make_bars(times, open_=10.0, high=11.0, low=9.0, close=10.5):
    """Build a small DataFrame of identical, valid bars at the given times."""
    index = pd.DatetimeIndex(pd.to_datetime(times), name="time")
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close}, index=index
    )


def test_clean_data_has_no_problems():
    bars = make_bars(["2024-01-02 09:00", "2024-01-02 10:00", "2024-01-02 11:00"])
    report = find_problems(bars, "H1")
    assert report["duplicates"] == 0
    assert report["bad_ohlc"] == 0
    assert report["short_gaps"] == report["long_gaps"] == report["weekend_gaps"] == []


def test_detects_duplicate_bar():
    bars = make_bars(["2024-01-02 09:00", "2024-01-02 09:00", "2024-01-02 10:00"])
    assert find_problems(bars, "H1")["duplicates"] == 1


def test_detects_impossible_bar():
    bars = make_bars(["2024-01-02 09:00", "2024-01-02 10:00"])
    bars.loc[bars.index[1], "high"] = 8.0  # high below the open: impossible
    assert find_problems(bars, "H1")["bad_ohlc"] == 1


def test_classifies_gaps():
    # 2024-01-05 is a Friday, 2024-01-08 is a Monday.
    bars = make_bars([
        "2024-01-04 21:00",
        "2024-01-04 22:00",
        "2024-01-05 00:00",   # 2h step -> short gap (the daily break, <= 3h)
        "2024-01-05 06:00",   # 6h step -> long gap (missing data?)
        "2024-01-05 22:00",   # 16h step on a weekday -> long gap
        "2024-01-08 00:00",   # Fri -> Mon -> weekend gap
    ])
    report = find_problems(bars, "H1")
    assert len(report["short_gaps"]) == 1
    assert len(report["long_gaps"]) == 2
    assert len(report["weekend_gaps"]) == 1


# ---------- Closed-bar rule ----------

def test_forming_bar_is_dropped():
    bars = make_bars(["2026-11-09 09:00", "2026-11-09 10:00"])
    # At 10:12 the 10:00 H1 bar is still forming (it closes at 11:00).
    result = drop_forming_bar(bars, now=pd.Timestamp("2026-11-09 10:12"), timeframe="H1")
    assert list(result.index) == [pd.Timestamp("2026-11-09 09:00")]


def test_closed_bar_is_kept():
    bars = make_bars(["2026-11-09 09:00", "2026-11-09 10:00"])
    # At exactly 11:00 the 10:00 bar has closed, so keep it.
    result = drop_forming_bar(bars, now=pd.Timestamp("2026-11-09 11:00"), timeframe="H1")
    assert len(result) == 2
