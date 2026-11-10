"""Helpers for Step 6: run a strategy variant on one period of history, the same way every time."""

import pandas as pd

from goldbot.backtest import BacktestResult, Costs, run_backtest
from goldbot.metrics import summarize
from goldbot.strategy import StrategyParams, add_indicators, evaluate_bar


def backtest_period(
    raw_bars: pd.DataFrame,
    params: StrategyParams,
    settings: dict,
    start: str | None = None,
    end: str | None = None,
    costs: Costs | None = None,
) -> tuple[dict, BacktestResult]:
    """Backtest `params` on bars between `start` and `end` (inclusive). Returns (stats, result).

    Indicators are computed on the FULL history first and only then sliced. That way the
    EMA 200 is already warmed up on the first day of the period, exactly as it would be live.
    (Safe because indicators are causal, as proved by the Step 2 tests.)
    """
    bars = add_indicators(raw_bars, params).loc[start:end]
    result = run_backtest(
        bars,
        signal_fn=lambda prev, curr, t: evaluate_bar(prev, curr, t, params),
        symbol=settings["symbol"],
        risk=settings["risk"],
        costs=costs or Costs.from_settings(settings),
        initial_equity=settings["backtest"]["initial_equity"],
    )
    return summarize(result), result
