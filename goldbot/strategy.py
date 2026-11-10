"""Strategy v1: EMA trend-following on gold.

Rules (all numbers come from [strategy] in config/settings.toml):
  BUY  when EMA fast crosses ABOVE EMA slow on the latest closed bar,
       AND the close is above EMA trend (only buy in an uptrend).
  SELL when EMA fast crosses BELOW EMA slow on the latest closed bar,
       AND the close is below EMA trend (only sell in a downtrend).
  Only if the entry time falls inside the session window.
  Stop loss = sl_atr_mult x ATR away from entry. Take profit = reward_risk x stop distance.

Everything here is PURE: bars in, decision out. No MT5, no clock, no files.
That is what lets the backtest and the live bot run the exact same rules.
"""

from collections.abc import Mapping
from dataclasses import dataclass

import pandas as pd

from goldbot.data import TIMEFRAME_MINUTES
from goldbot.indicators import atr, ema


@dataclass(frozen=True)  # frozen = can't be changed after creation (no accidental edits)
class StrategyParams:
    timeframe: str
    ema_fast: int
    ema_slow: int
    ema_trend: int
    atr_period: int
    sl_atr_mult: float
    reward_risk: float
    use_session_filter: bool
    session_start_hour: int
    session_end_hour: int

    @classmethod
    def from_settings(cls, strategy_settings: dict) -> "StrategyParams":
        # A typo or missing key in settings.toml raises an error here, instead of silently
        # running with a wrong value.
        return cls(**strategy_settings)


@dataclass(frozen=True)
class Signal:
    direction: str                # "buy" or "sell"
    signal_bar: pd.Timestamp      # open time of the closed bar that triggered the signal
    entry_time: pd.Timestamp      # when we'd enter = that bar's close = next bar's open
    reference_price: float        # signal bar's close (the real fill comes later)
    stop_distance: float          # $ from entry to stop loss
    take_profit_distance: float   # $ from entry to take profit

    def stop_loss_price(self, entry_price: float) -> float:
        """Buy: stop goes BELOW the entry. Sell: stop goes ABOVE the entry."""
        if self.direction == "buy":
            return entry_price - self.stop_distance
        return entry_price + self.stop_distance

    def take_profit_price(self, entry_price: float) -> float:
        if self.direction == "buy":
            return entry_price + self.take_profit_distance
        return entry_price - self.take_profit_distance


def add_indicators(bars: pd.DataFrame, p: StrategyParams) -> pd.DataFrame:
    """Return a COPY of the bars with the indicator columns the strategy needs.

    The backtest calls this ONCE on the whole history, which is safe only because the Step 2
    causality tests prove each indicator value uses past bars only.
    """
    out = bars.copy()   # copy: never modify the caller's DataFrame (pure function)
    out["ema_fast"] = ema(out["close"], p.ema_fast)
    out["ema_slow"] = ema(out["close"], p.ema_slow)
    out["ema_trend"] = ema(out["close"], p.ema_trend)
    out["atr"] = atr(out, p.atr_period)
    return out


def evaluate_bar(prev: Mapping, curr: Mapping, bar_time: pd.Timestamp, p: StrategyParams) -> Signal | None:
    """Apply the rules to two consecutive CLOSED bars (with indicator columns).

    prev/curr can be a DataFrame row or a dict; anything that supports row["ema_fast"].
    Returns a Signal, or None for "do nothing".
    """
    needed = [prev["ema_fast"], prev["ema_slow"],
              curr["ema_fast"], curr["ema_slow"], curr["ema_trend"], curr["atr"]]
    if any(pd.isna(v) for v in needed):   # still in indicator warm-up
        return None

    crossed_up = prev["ema_fast"] <= prev["ema_slow"] and curr["ema_fast"] > curr["ema_slow"]
    crossed_down = prev["ema_fast"] >= prev["ema_slow"] and curr["ema_fast"] < curr["ema_slow"]
    uptrend = curr["close"] > curr["ema_trend"]
    downtrend = curr["close"] < curr["ema_trend"]

    if crossed_up and uptrend:
        direction = "buy"
    elif crossed_down and downtrend:
        direction = "sell"
    else:
        return None

    # We enter when this bar closes, which is when the next bar opens.
    entry_time = bar_time + pd.Timedelta(minutes=TIMEFRAME_MINUTES[p.timeframe])
    if p.use_session_filter and not (p.session_start_hour <= entry_time.hour < p.session_end_hour):
        return None

    stop_distance = p.sl_atr_mult * curr["atr"]
    return Signal(
        direction=direction,
        signal_bar=bar_time,
        entry_time=entry_time,
        reference_price=float(curr["close"]),
        stop_distance=float(stop_distance),
        take_profit_distance=float(p.reward_risk * stop_distance),
    )


def generate_signal(bars: pd.DataFrame, p: StrategyParams) -> Signal | None:
    """Is there a signal on the LATEST bar?

    `bars` must contain CLOSED bars only (see data.drop_forming_bar) and already have
    indicator columns (see add_indicators). The live bot calls this once per new bar.
    """
    if len(bars) < 2:
        return None
    return evaluate_bar(bars.iloc[-2], bars.iloc[-1], bars.index[-1], p)
