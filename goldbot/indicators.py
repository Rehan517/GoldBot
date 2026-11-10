"""Technical indicators, written by hand so we understand every number.

Every function here is CAUSAL: the value at bar t uses only bars up to and
including t, never later bars. A bar's value is therefore only final once
that bar has CLOSED. That's why the strategy acts on the close of bar t and
trades at the open of bar t+1.

The formulas match MetaTrader 5's built-in indicators, so you can check our
numbers against your MT5 charts.
"""

import pandas as pd


def ema_loop(prices: list[float], period: int) -> list[float]:
    """Teaching version of the EMA: a plain Python loop. Slow, but every step is visible.

    EMA_t = alpha * price_t + (1 - alpha) * EMA_(t-1),   alpha = 2 / (period + 1)

    Like MT5, the very first EMA value is simply the first price.
    """
    alpha = 2 / (period + 1)
    result = []
    ema_value = None
    for price in prices:
        if ema_value is None:
            ema_value = price                                     # seed with the first price
        else:
            ema_value = alpha * price + (1 - alpha) * ema_value   # blend new price with old EMA
        result.append(ema_value)
    return result


def ema(prices: pd.Series, period: int) -> pd.Series:
    """Fast EMA using pandas. Gives the same numbers as `ema_loop`.

    `ewm(span=period, adjust=False)` is pandas' built-in version of exactly the
    loop above. `min_periods=period` blanks out (NaN) the first period-1 values:
    those are the "warm-up", when the EMA is still dominated by the seed price
    and isn't trustworthy yet.
    """
    return prices.ewm(span=period, adjust=False, min_periods=period).mean()


def true_range(bars: pd.DataFrame) -> pd.Series:
    """How far price really travelled in each bar, including any gap from the previous close.

    TR = max(high - low, |high - prev_close|, |low - prev_close|)
    The first bar has no previous close, so its TR is just high - low.
    """
    prev_close = bars["close"].shift(1)   # shift(1): each row now sees the PREVIOUS bar's close
    candidates = pd.concat(
        [
            bars["high"] - bars["low"],
            (bars["high"] - prev_close).abs(),
            (bars["low"] - prev_close).abs(),
        ],
        axis=1,
    )
    return candidates.max(axis=1)   # max across the three columns (ignores NaN on the first bar)


def atr(bars: pd.DataFrame, period: int = 14) -> pd.Series:
    """Average True Range, MT5 style: a SIMPLE average of the last `period` true ranges.

    (TradingView's ATR uses Wilder's smoothing instead, so its numbers differ slightly.)
    """
    return true_range(bars).rolling(period).mean()
