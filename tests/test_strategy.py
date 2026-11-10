"""Tests for goldbot.strategy: the v1 entry rules."""

import dataclasses

import numpy as np
import pandas as pd
import pytest

from goldbot.config import load_settings
from goldbot.strategy import StrategyParams, add_indicators, generate_signal

PARAMS = StrategyParams(
    timeframe="H1", ema_fast=20, ema_slow=50, ema_trend=200, atr_period=14,
    sl_atr_mult=1.5, reward_risk=2.0,
    use_session_filter=True, session_start_hour=10, session_end_hour=20,
)


def two_bars(prev_fast, prev_slow, fast, slow, close, trend, atr=10.0, time="2026-11-09 13:00"):
    """Two consecutive closed H1 bars with hand-picked indicator values.

    Default time 13:00 -> entry at 14:00, inside the 10-20 session window.
    """
    t = pd.Timestamp(time)
    index = pd.DatetimeIndex([t - pd.Timedelta(hours=1), t], name="time")
    return pd.DataFrame(
        {
            "close":     [close, close],
            "ema_fast":  [prev_fast, fast],
            "ema_slow":  [prev_slow, slow],
            "ema_trend": [trend, trend],
            "atr":       [atr, atr],
        },
        index=index,
    )


# ---------- The core rules ----------

def test_buy_when_fast_crosses_above_slow_in_uptrend():
    bars = two_bars(prev_fast=99, prev_slow=100, fast=101, slow=100, close=110, trend=105)
    signal = generate_signal(bars, PARAMS)

    assert signal.direction == "buy"
    assert signal.entry_time == pd.Timestamp("2026-11-09 14:00")   # signal bar 13:00 + 1h
    assert signal.stop_distance == 15.0          # 1.5 x ATR(10)
    assert signal.take_profit_distance == 30.0   # 2 x 15
    # If we get filled at 111: SL below, TP above.
    assert signal.stop_loss_price(111.0) == 96.0
    assert signal.take_profit_price(111.0) == 141.0


def test_sell_when_fast_crosses_below_slow_in_downtrend():
    bars = two_bars(prev_fast=101, prev_slow=100, fast=99, slow=100, close=90, trend=95)
    signal = generate_signal(bars, PARAMS)

    assert signal.direction == "sell"
    assert signal.stop_loss_price(89.0) == 104.0     # SL ABOVE a sell
    assert signal.take_profit_price(89.0) == 59.0    # TP BELOW a sell


def test_no_signal_without_a_cross():
    # Fast was already above slow on both bars: an uptrend continuing, not a NEW cross.
    bars = two_bars(prev_fast=102, prev_slow=100, fast=103, slow=100, close=110, trend=105)
    assert generate_signal(bars, PARAMS) is None


def test_trend_filter_blocks_buy_in_downtrend():
    # A bullish cross, but the close (100) is BELOW EMA 200 (105): counter-trend, so skip it.
    bars = two_bars(prev_fast=99, prev_slow=100, fast=101, slow=100, close=100, trend=105)
    assert generate_signal(bars, PARAMS) is None


def test_touching_then_crossing_counts_as_a_cross():
    # prev fast == slow exactly, then fast moves above: that's a cross (<= in the rule).
    bars = two_bars(prev_fast=100, prev_slow=100, fast=101, slow=100, close=110, trend=105)
    assert generate_signal(bars, PARAMS).direction == "buy"


# ---------- Session filter ----------

def test_session_filter_blocks_entries_outside_hours():
    # Signal bar 22:00 -> entry 23:00, outside 10:00-20:00.
    bars = two_bars(99, 100, 101, 100, close=110, trend=105, time="2026-11-09 22:00")
    assert generate_signal(bars, PARAMS) is None


def test_session_end_hour_is_exclusive():
    # Signal bar 19:00 -> entry 20:00. Window is [10, 20) so 20:00 is just outside.
    bars = two_bars(99, 100, 101, 100, close=110, trend=105, time="2026-11-09 19:00")
    assert generate_signal(bars, PARAMS) is None


def test_session_filter_can_be_turned_off():
    no_filter = dataclasses.replace(PARAMS, use_session_filter=False)
    bars = two_bars(99, 100, 101, 100, close=110, trend=105, time="2026-11-09 22:00")
    assert generate_signal(bars, no_filter).direction == "buy"


# ---------- Edge cases ----------

def test_no_signal_during_indicator_warmup():
    bars = two_bars(99, 100, 101, 100, close=110, trend=np.nan)   # EMA 200 not ready yet
    assert generate_signal(bars, PARAMS) is None


def test_needs_at_least_two_bars():
    bars = two_bars(99, 100, 101, 100, close=110, trend=105).iloc[-1:]
    assert generate_signal(bars, PARAMS) is None


def test_strategy_does_not_modify_its_input():
    """Pure function: calling it must leave the caller's data untouched."""
    bars = two_bars(99, 100, 101, 100, close=110, trend=105)
    before = bars.copy()
    generate_signal(bars, PARAMS)
    pd.testing.assert_frame_equal(bars, before)

    raw = bars[["close"]].assign(high=111.0, low=109.0)
    raw_before = raw.copy()
    add_indicators(raw, PARAMS)
    pd.testing.assert_frame_equal(raw, raw_before)


# ---------- Config wiring ----------

def test_params_load_from_settings_file():
    params = StrategyParams.from_settings(load_settings()["strategy"])
    assert params.ema_fast < params.ema_slow < params.ema_trend


def test_typo_in_settings_is_rejected():
    settings = {**load_settings()["strategy"], "ema_fsat": 20}   # misspelt key
    with pytest.raises(TypeError):
        StrategyParams.from_settings(settings)
