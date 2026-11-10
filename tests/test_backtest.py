"""Tests for goldbot.backtest and goldbot.metrics.

Most tests use: $10,000 equity, 1% risk, $10 stop, $20 target
  -> 0.1 lots, $100 at risk (1R = $100), each $1 move = $10.
"""

import dataclasses

import numpy as np
import pandas as pd
import pytest

from goldbot.backtest import BacktestResult, Costs, run_backtest, swap_nights
from goldbot.metrics import max_drawdown, summarize
from goldbot.strategy import Signal, StrategyParams, add_indicators, evaluate_bar

GOLD = {"tick_size": 0.01, "tick_value": 1.0, "volume_min": 0.01, "volume_step": 0.01, "volume_max": 100.0}
RISK = {"risk_per_trade_pct": 1.0, "max_risk_per_trade_pct": 1.5}
NO_COSTS = Costs(min_spread_points=0, slippage_points=0, commission_per_lot=0,
                 swap_long_points=0, swap_short_points=0)
START = pd.Timestamp("2026-11-02 10:00")   # a Monday


def make_bars(ohlc, start=START, spread=0):
    """Hourly bars from a list of (open, high, low, close)."""
    index = pd.date_range(start, periods=len(ohlc), freq="h", name="time")
    df = pd.DataFrame(ohlc, columns=["open", "high", "low", "close"], index=index)
    df["spread"] = spread
    return df


def scripted(on_bar_time, direction="buy", stop=10.0, target=20.0):
    """A fake strategy: signal exactly once, on the bar with time `on_bar_time`."""
    def signal_fn(prev, curr, time):
        if time != on_bar_time:
            return None
        return Signal(direction, time, time + pd.Timedelta(hours=1), curr["close"], stop, target)
    return signal_fn


def run(bars, signal_fn, costs=NO_COSTS, equity=10_000.0):
    return run_backtest(bars, signal_fn, GOLD, RISK, costs, equity)


FLAT = (100, 101, 99, 100)
SIGNAL_ON_BAR_1 = scripted(START + pd.Timedelta(hours=1))   # -> enter at bar 2's open (100)


# ---------- Basic exits ----------

def test_buy_hits_target():
    bars = make_bars([FLAT, FLAT, (100, 105, 98, 104), (104, 121, 103, 118), FLAT])
    trade = run(bars, SIGNAL_ON_BAR_1).trades.iloc[0]

    assert trade.entry == 100 and trade.stop_loss == 90 and trade.take_profit == 120
    assert trade.exit_reason == "target"
    assert trade.pnl == 200.0          # +$20 x 0.1 lots x $100/lot-dollar
    assert trade.r == 2.0


def test_buy_hits_stop():
    bars = make_bars([FLAT, FLAT, (100, 105, 98, 104), (104, 105, 89, 95), FLAT])
    trade = run(bars, SIGNAL_ON_BAR_1).trades.iloc[0]
    assert trade.exit_reason == "stop"
    assert trade.pnl == -100.0 and trade.r == -1.0


def test_stop_and_target_in_same_bar_assumes_stop():
    # Bar 3 touches both 89 (below the stop) and 121 (above the target): assume the worst.
    bars = make_bars([FLAT, FLAT, (100, 105, 98, 104), (104, 121, 89, 100), FLAT])
    assert run(bars, SIGNAL_ON_BAR_1).trades.iloc[0].exit_reason == "stop"


def test_gap_through_stop_fills_at_worse_open():
    # Bar 3 OPENS at 85, already below the 90 stop: we get 85, not 90.
    bars = make_bars([FLAT, FLAT, (100, 105, 98, 104), (85, 86, 84, 85), FLAT])
    trade = run(bars, SIGNAL_ON_BAR_1).trades.iloc[0]
    assert trade.exit_reason == "stop_gap"
    assert trade.pnl == -150.0 and trade.r == -1.5   # a gap can cost MORE than 1R


def test_exit_can_happen_on_the_entry_bar():
    bars = make_bars([FLAT, FLAT, (100, 100.5, 89, 92), FLAT])
    trade = run(bars, SIGNAL_ON_BAR_1).trades.iloc[0]
    assert trade.entry_time == START + pd.Timedelta(hours=2)
    assert trade.exit_time == trade.entry_time and trade.exit_reason == "stop"


# ---------- Spread, slippage, commission ----------

def test_buy_pays_spread_on_entry():
    costs = dataclasses.replace(NO_COSTS, min_spread_points=50)   # $0.50
    bars = make_bars([FLAT, FLAT, (100, 105, 98, 104), (104, 120.4, 103, 118), FLAT])
    trade = run(bars, SIGNAL_ON_BAR_1, costs).trades.iloc[0]
    assert trade.entry == 100.5              # ask = bid 100 + 0.50
    assert trade.take_profit == 120.5        # so 120.4 was NOT enough to reach the target
    assert trade.exit_reason == "end_of_data"


def test_sell_stop_triggers_on_ask_not_bid():
    costs = dataclasses.replace(NO_COSTS, min_spread_points=50)   # $0.50
    sell = scripted(START + pd.Timedelta(hours=1), direction="sell")
    # Sell at bid 100 -> stop at 110. Bar 3's BID high is only 109.6, but the ASK is 110.1.
    bars = make_bars([FLAT, FLAT, (100, 101, 99, 100), (100, 109.6, 99, 105), FLAT])
    trade = run(bars, sell, costs).trades.iloc[0]
    assert trade.entry == 100 and trade.stop_loss == 110
    assert trade.exit_reason == "stop"
    assert trade.r == -1.0


def test_slippage_on_entry_and_stop_but_not_target():
    costs = dataclasses.replace(NO_COSTS, slippage_points=5)      # $0.05
    stop_bars = make_bars([FLAT, FLAT, (100, 105, 98, 104), (104, 105, 89, 95), FLAT])
    stopped = run(stop_bars, SIGNAL_ON_BAR_1, costs).trades.iloc[0]
    assert stopped.entry == 100.05 and stopped.exit == 90.0       # SL 90.05, minus $0.05 slip
    assert stopped.pnl == pytest.approx(-100.5)

    tp_bars = make_bars([FLAT, FLAT, (100, 105, 98, 104), (104, 121, 103, 118), FLAT])
    won = run(tp_bars, SIGNAL_ON_BAR_1, costs).trades.iloc[0]
    assert won.exit == 120.05 and won.pnl == pytest.approx(200.0)  # a limit order fills at its price


def test_commission_is_deducted():
    costs = dataclasses.replace(NO_COSTS, commission_per_lot=7.0)
    bars = make_bars([FLAT, FLAT, (100, 105, 98, 104), (104, 121, 103, 118), FLAT])
    trade = run(bars, SIGNAL_ON_BAR_1, costs).trades.iloc[0]
    assert trade.commission == 0.7 and trade.pnl == pytest.approx(199.3)


# ---------- Swap ----------

@pytest.mark.parametrize("entry, exit_, nights", [
    ("2026-11-02 12:00", "2026-11-02 18:00", 0),   # same day
    ("2026-11-02 12:00", "2026-11-03 12:00", 1),   # Mon night
    ("2026-11-04 12:00", "2026-11-05 12:00", 3),   # Wed night = triple
    ("2026-11-06 12:00", "2026-11-09 12:00", 1),   # Fri night only; Sat/Sun are free
    ("2026-11-02 12:00", "2026-11-09 12:00", 7),   # a full week
])
def test_swap_nights(entry, exit_, nights):
    assert swap_nights(pd.Timestamp(entry), pd.Timestamp(exit_)) == nights


def test_swap_is_charged_on_overnight_trade():
    costs = dataclasses.replace(NO_COSTS, swap_long_points=-12.6)
    # Signal on bar 1 (Mon 11:00), enter bar 2 (Mon 12:00); bars run until Tue 12:00, then the target.
    hold = [(100, 101, 99, 100)] * 24
    bars = make_bars([FLAT, FLAT] + hold + [(100, 121, 99, 118), FLAT])
    trade = run(bars, SIGNAL_ON_BAR_1, costs).trades.iloc[0]
    assert trade.swap == pytest.approx(-1.26)    # 1 night x -12.6 points x $1 x 0.1 lots
    assert trade.pnl == pytest.approx(200 - 1.26)


# ---------- Position handling ----------

def test_only_one_position_at_a_time():
    def signal_every_bar(prev, curr, time):
        return Signal("buy", time, time + pd.Timedelta(hours=1), curr["close"], 10.0, 20.0)

    bars = make_bars([FLAT] * 6)
    result = run(bars, signal_every_bar)
    assert len(result.trades) == 1                            # one trade, held to the end
    assert result.trades.iloc[0].exit_reason == "end_of_data"
    assert (result.skipped["reason"] == "skip: position already open").sum() >= 1


def test_signal_on_last_bar_is_ignored():
    bars = make_bars([FLAT, FLAT, FLAT])
    result = run(bars, scripted(START + pd.Timedelta(hours=2)))   # no next bar to enter on
    assert result.trades.empty


def test_trade_skipped_when_sizing_says_no():
    # $1,000 account, $200 stop: even 0.01 lot risks $200 = 20% > 1.5% ceiling.
    bars = make_bars([FLAT, FLAT, FLAT, FLAT])
    result = run(bars, scripted(START + pd.Timedelta(hours=1), stop=200, target=400), equity=1_000)
    assert result.trades.empty
    assert result.skipped.iloc[0]["reason"].startswith("skip: min lot")


def test_equity_curve_adds_up():
    bars = make_bars([FLAT, FLAT, (100, 105, 98, 104), (104, 121, 103, 118), FLAT])
    result = run(bars, SIGNAL_ON_BAR_1)
    assert len(result.equity) == len(bars)
    assert result.equity.iloc[-1] == pytest.approx(10_000 + result.trades["pnl"].sum())


def test_runs_with_the_real_strategy():
    """Smoke test: the real strategy plugged into the engine on fake random-walk data."""
    rng = np.random.default_rng(7)
    n = 3000
    close = 4000 + rng.normal(0, 3, n).cumsum()
    bars = make_bars(list(zip(close, close + 2, close - 2, close)), spread=10)
    params = StrategyParams("H1", 20, 50, 200, 14, 1.5, 2.0, False, 10, 20)
    with_ind = add_indicators(bars, params)
    result = run(with_ind, lambda prev, curr, t: evaluate_bar(prev, curr, t, params))
    assert len(result.trades) > 0
    assert result.equity.iloc[-1] == pytest.approx(10_000 + result.trades["pnl"].sum())


# ---------- Metrics ----------

def test_metrics_on_known_trades():
    trades = pd.DataFrame({
        "pnl": [200.0, -100.0, -100.0, 300.0], "r": [2.0, -1.0, -1.0, 3.0],
        "exit_reason": ["target", "stop", "stop", "target"], "bars_held": [5, 3, 2, 10],
        "swap": [0.0] * 4, "commission": [0.0] * 4,
    })
    equity = pd.Series([1000.0, 1200.0, 1100.0, 1000.0, 1300.0])
    stats = summarize(BacktestResult(trades, equity, pd.DataFrame(), initial_equity=1000.0))

    assert stats["win_rate_pct"] == 50.0
    assert stats["profit_factor"] == 2.5             # won 500 / lost 200
    assert stats["avg_r"] == 0.75
    assert stats["longest_losing_streak"] == 2
    assert stats["max_drawdown_usd"] == 200.0        # 1200 -> 1000
    assert stats["max_drawdown_pct"] == pytest.approx(16.667, abs=0.001)
    assert stats["return_pct"] == pytest.approx(30.0)


def test_max_drawdown_of_rising_equity_is_zero():
    assert max_drawdown(pd.Series([1.0, 2.0, 3.0])) == (0.0, 0.0)
