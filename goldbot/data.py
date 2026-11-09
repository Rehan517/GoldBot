"""Load MT5 bar exports into pandas and look for data problems.

MT5 "Export Bars" writes a tab-separated file like:

    <DATE>      <TIME>    <OPEN>   <HIGH>   <LOW>    <CLOSE>  <TICKVOL> <VOL>   <SPREAD>
    2018.01.02  09:00:00  1309.81  1310.17  1308.62  1309.28  6186      2538457 36

Prices are BID prices. Times are BROKER SERVER time (not UTC, not your local time).
SPREAD is in points (1 point = tick_size, so 36 points = $0.36 for gold).
"""

from pathlib import Path

import pandas as pd

# How many minutes each MT5 timeframe covers.
TIMEFRAME_MINUTES = {"M1": 1, "M5": 5, "M15": 15, "M30": 30, "H1": 60, "H4": 240, "D1": 1440}


def load_mt5_csv(path: str | Path) -> pd.DataFrame:
    """Read an MT5 bar export into a DataFrame indexed by bar open time.

    Returns columns: open, high, low, close, tick_volume, real_volume, spread.
    The index ("time") is the bar's OPEN time in broker server time.
    """
    df = pd.read_csv(path, sep="\t")

    # "<DATE>" -> "date", "<TICKVOL>" -> "tickvol", ...
    df.columns = [col.strip("<>").lower() for col in df.columns]

    # Date and time come as two text columns; join them into one real datetime.
    df["time"] = pd.to_datetime(df["date"] + " " + df["time"], format="%Y.%m.%d %H:%M:%S")

    df = (
        df.drop(columns=["date"])
        .rename(columns={"tickvol": "tick_volume", "vol": "real_volume"})
        .set_index("time")
        .sort_index()
    )
    return df


def find_problems(bars: pd.DataFrame, timeframe: str) -> dict:
    """Check bar data for anything that could mislead a backtest.

    Returns a dict of findings, so the caller (or a test) decides what to do.
    """
    bar_length = pd.Timedelta(minutes=TIMEFRAME_MINUTES[timeframe])
    times = bars.index

    # 1. Duplicate timestamps: the same bar twice would double-count trades.
    duplicates = int(times.duplicated().sum())

    # 2. Impossible bars: the high must be the highest price, the low the lowest.
    bad_ohlc = (
        (bars["high"] < bars[["open", "close"]].max(axis=1))
        | (bars["low"] > bars[["open", "close"]].min(axis=1))
        | (bars["high"] < bars["low"])
    )

    # 3. Gaps: places where the next bar starts later than expected.
    step = times.to_series().diff()      # time since the previous bar
    gaps = step[step > bar_length]       # only the steps that are too big

    weekend_gaps, short_gaps, long_gaps = [], [], []
    for gap_end, gap_size in gaps.items():
        gap_start = gap_end - gap_size   # open time of the bar before the gap
        days_covered = pd.date_range(gap_start.normalize(), gap_end.normalize(), freq="D")
        if 5 in days_covered.day_of_week:  # 5 = Saturday -> normal weekend closure
            weekend_gaps.append((gap_start, gap_end))
        # Daily break: about 1h until early 2026, then 22:00 -> 01:00 server time (3h).
        elif gap_size <= pd.Timedelta(hours=3):
            short_gaps.append((gap_start, gap_end))
        else:                            # holidays, or genuinely missing data
            long_gaps.append((gap_start, gap_end))

    return {
        "rows": len(bars),
        "first_bar": times.min(),
        "last_bar": times.max(),
        "duplicates": duplicates,
        "bad_ohlc": int(bad_ohlc.sum()),
        "weekend_bars": int((times.day_of_week == 5).sum()),  # bars on a Saturday
        "weekend_gaps": weekend_gaps,
        "short_gaps": short_gaps,
        "long_gaps": long_gaps,
    }
