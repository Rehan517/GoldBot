"""Performance statistics for a backtest."""

import math

import pandas as pd

from goldbot.backtest import BacktestResult


def longest_losing_streak(pnls: pd.Series) -> int:
    longest = current = 0
    for pnl in pnls:
        current = current + 1 if pnl <= 0 else 0
        longest = max(longest, current)
    return longest


def max_drawdown(equity: pd.Series) -> tuple[float, float]:
    """Largest peak-to-trough fall in account value: ($, % of the peak at that time)."""
    peak = equity.cummax()                     # highest equity seen so far, at every bar
    drawdown_usd = peak - equity
    drawdown_pct = (peak - equity) / peak * 100
    return float(drawdown_usd.max()), float(drawdown_pct.max())


def summarize(result: BacktestResult) -> dict:
    t = result.trades
    if t.empty:
        return {"trades": 0}

    wins, losses = t[t["pnl"] > 0], t[t["pnl"] <= 0]
    gross_profit, gross_loss = wins["pnl"].sum(), -losses["pnl"].sum()
    dd_usd, dd_pct = max_drawdown(result.equity)
    final = float(result.equity.iloc[-1])

    return {
        "trades": len(t),
        "win_rate_pct": 100 * len(wins) / len(t),
        "avg_r": t["r"].mean(),                    # expectancy per trade, in R
        "avg_win_r": wins["r"].mean() if len(wins) else 0.0,
        "avg_loss_r": losses["r"].mean() if len(losses) else 0.0,
        "profit_factor": gross_profit / gross_loss if gross_loss > 0 else math.inf,
        "net_profit": t["pnl"].sum(),
        "final_equity": final,
        "return_pct": 100 * (final / result.initial_equity - 1),
        "max_drawdown_usd": dd_usd,
        "max_drawdown_pct": dd_pct,
        "longest_losing_streak": longest_losing_streak(t["pnl"]),
        "avg_bars_held": t["bars_held"].mean(),
        "total_swap": t["swap"].sum(),
        "total_commission": t["commission"].sum(),
        "exit_reasons": t["exit_reason"].value_counts().to_dict(),
        "signals_skipped": len(result.skipped),
    }
