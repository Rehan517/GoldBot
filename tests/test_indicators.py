"""Tests for goldbot.indicators: EMA, true range, ATR."""

import numpy as np
import pandas as pd
import pytest

from goldbot.indicators import atr, ema, ema_loop, true_range


def random_walk_bars(n=500, seed=42):
    """Fake but realistic-looking gold bars: a random walk around 4000."""
    rng = np.random.default_rng(seed)   # fixed seed -> the same "random" data every run
    close = 4000 + rng.normal(0, 3, n).cumsum()
    open_ = np.concatenate([[4000], close[:-1]]) + rng.normal(0, 0.5, n)   # open near prev close
    high = np.maximum(open_, close) + rng.uniform(0, 4, n)
    low = np.minimum(open_, close) - rng.uniform(0, 4, n)
    index = pd.date_range("2024-01-01", periods=n, freq="h", name="time")
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close}, index=index)


# ---------- EMA ----------

def test_ema_loop_by_hand():
    # period 3 -> alpha = 2/(3+1) = 0.5, so each EMA is halfway between the price and the previous EMA
    #   10 (seed) -> 0.5*11 + 0.5*10 = 10.5 -> 0.5*12 + 0.5*10.5 = 11.25
    assert ema_loop([10, 11, 12], period=3) == [10, 10.5, 11.25]


def test_fast_ema_matches_loop_version():
    close = random_walk_bars()["close"]
    fast = ema(close, period=20)
    slow = pd.Series(ema_loop(close.tolist(), period=20), index=close.index)
    # After warm-up the two must agree (tiny float rounding differences allowed).
    pd.testing.assert_series_equal(fast.iloc[19:], slow.iloc[19:], check_names=False)


def test_ema_warmup_is_blank():
    close = random_walk_bars()["close"]
    result = ema(close, period=20)
    assert result.iloc[:19].isna().all()    # first period-1 values are NaN
    assert result.iloc[19:].notna().all()   # everything after is filled in


def test_ema_of_flat_price_is_that_price():
    flat = pd.Series([4000.0] * 50)
    assert (ema(flat, period=10).dropna() == 4000.0).all()


# ---------- True range / ATR ----------

def test_true_range_includes_gaps():
    bars = pd.DataFrame({
        "open":  [4000.0, 4030.0],
        "high":  [4005.0, 4035.0],
        "low":   [3995.0, 4025.0],
        "close": [4000.0, 4030.0],
    })
    tr = true_range(bars)
    assert tr.iloc[0] == 10.0   # first bar: just high - low
    assert tr.iloc[1] == 35.0   # gapped up: high (4035) - previous close (4000), not 4035-4025=10


def test_atr_of_constant_range():
    # Every bar has a $6 range with no gaps -> ATR must be exactly 6.
    n = 30
    bars = pd.DataFrame({
        "open": [4000.0] * n, "high": [4003.0] * n, "low": [3997.0] * n, "close": [4000.0] * n,
    })
    result = atr(bars, period=14)
    assert result.iloc[:13].isna().all()
    assert result.iloc[13:].eq(6.0).all()


# ---------- No lookahead (causality) ----------

@pytest.mark.parametrize("cut", [100, 250, 499])
def test_indicators_never_use_future_bars(cut):
    """Calculating on the first `cut` bars must give the SAME values as calculating
    on all bars, for those first `cut` bars. If extra (future) bars changed a past
    value, the indicator would be peeking into the future."""
    full = random_walk_bars(500)
    partial = full.iloc[:cut]

    pd.testing.assert_series_equal(ema(full["close"], 50).iloc[:cut], ema(partial["close"], 50))
    pd.testing.assert_series_equal(atr(full, 14).iloc[:cut], atr(partial, 14))


def test_causality_test_catches_a_cheating_indicator():
    """Prove the test above actually works: a deliberately cheating 'indicator'
    that uses the NEXT bar's close must fail the same check."""
    def cheating_indicator(close):
        return close.shift(-1)   # looks one bar into the future

    full = random_walk_bars(500)["close"]
    partial = full.iloc[:250]
    with pytest.raises(AssertionError):
        pd.testing.assert_series_equal(cheating_indicator(full).iloc[:250], cheating_indicator(partial))
