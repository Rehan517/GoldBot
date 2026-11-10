"""Tests for goldbot.validation and the shared closed-bar loader."""

import os

import numpy as np
import pandas as pd

from goldbot.data import load_closed_bars
from goldbot.strategy import StrategyParams
from goldbot.validation import backtest_period

PARAMS = StrategyParams("H1", 20, 50, 200, 14, 1.5, 2.0, False, 10, 20)
SETTINGS = {
    "symbol": {"tick_size": 0.01, "tick_value": 1.0, "volume_min": 0.01, "volume_step": 0.01,
               "volume_max": 100.0, "swap_long": 0.0, "swap_short": 0.0},
    "risk": {"risk_per_trade_pct": 1.0, "max_risk_per_trade_pct": 1.5},
    "backtest": {"initial_equity": 10_000.0, "min_spread_points": 0, "slippage_points": 0,
                 "commission_per_lot": 0.0},
}


def random_walk(n=4000, seed=3):
    rng = np.random.default_rng(seed)
    close = 4000 + rng.normal(0, 3, n).cumsum()
    index = pd.date_range("2024-01-01", periods=n, freq="h", name="time")
    return pd.DataFrame({"open": close, "high": close + 2, "low": close - 2, "close": close,
                         "spread": 0}, index=index)


def test_period_backtest_only_trades_inside_the_period():
    bars = random_walk()
    start, end = "2024-03-01", "2024-04-30 23:00"
    stats, result = backtest_period(bars, PARAMS, SETTINGS, start=start, end=end)
    assert stats["trades"] > 0
    assert result.trades["entry_time"].min() >= pd.Timestamp(start)
    assert result.equity.index.max() <= pd.Timestamp(end)


def test_indicators_are_warm_on_the_first_day_of_the_period():
    """Slicing AFTER computing indicators means a period starting mid-history can trade
    immediately. Slicing first would leave the EMA 200 blank for 200 bars."""
    bars = random_walk()
    start = bars.index[1000]
    _, warm = backtest_period(bars, PARAMS, SETTINGS, start=start)
    _, cold = backtest_period(bars.loc[start:], PARAMS, SETTINGS)
    first_warm = warm.trades["entry_time"].min()
    first_cold = cold.trades["entry_time"].min()
    assert first_warm <= first_cold


def test_load_closed_bars_drops_forming_bar(tmp_path):
    path = tmp_path / "bars.csv"
    path.write_text(
        "<DATE>\t<TIME>\t<OPEN>\t<HIGH>\t<LOW>\t<CLOSE>\t<TICKVOL>\t<VOL>\t<SPREAD>\r\n"
        "2026.11.09\t09:00:00\t1\t2\t0.5\t1.5\t1\t1\t1\r\n"
        "2026.11.09\t10:00:00\t1\t2\t0.5\t1.5\t1\t1\t1\r\n"
    )
    # Pretend the file was saved at 08:12 UTC = 10:12 server time (UTC+2).
    saved = pd.Timestamp("2026-11-09 08:12").timestamp()
    os.utime(path, (saved, saved))
    bars = load_closed_bars(path, "H1", server_utc_offset_hours=2)
    assert list(bars.index) == [pd.Timestamp("2026-11-09 09:00")]
