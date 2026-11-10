"""Backtest Strategy v1 on the full H1 history and report the results.

Run from the project root:   python -m scripts.run_backtest
Outputs: results/trades_H1.csv, results/equity_H1.png
"""

import matplotlib.pyplot as plt
import pandas as pd

from goldbot.backtest import Costs, run_backtest
from goldbot.config import PROJECT_ROOT, load_settings
from goldbot.data import drop_forming_bar, load_mt5_csv
from goldbot.metrics import summarize
from goldbot.strategy import StrategyParams, add_indicators, evaluate_bar
from scripts.show_signals import export_time_in_server_time


def print_summary(stats: dict, initial_equity: float) -> None:
    print("\n=== Results ===")
    print(f"  Trades:               {stats['trades']}   (signals skipped: {stats['signals_skipped']})")
    print(f"  Win rate:             {stats['win_rate_pct']:.1f}%   (breakeven at 2R targets ~33%)")
    print(f"  Average R per trade:  {stats['avg_r']:+.3f} R   <- the key number")
    print(f"  Avg win / avg loss:   {stats['avg_win_r']:+.2f} R / {stats['avg_loss_r']:+.2f} R")
    print(f"  Profit factor:        {stats['profit_factor']:.2f}")
    print(f"  Net profit:           ${stats['net_profit']:+,.2f}   "
          f"(${initial_equity:,.0f} -> ${stats['final_equity']:,.2f}, {stats['return_pct']:+.1f}%)")
    print(f"  Max drawdown:         ${stats['max_drawdown_usd']:,.2f}  ({stats['max_drawdown_pct']:.1f}%)")
    print(f"  Longest losing run:   {stats['longest_losing_streak']} trades")
    print(f"  Avg hold:             {stats['avg_bars_held']:.1f} bars")
    print(f"  Swap paid:            ${stats['total_swap']:,.2f}   Commission: ${stats['total_commission']:,.2f}")
    print(f"  Exits:                {stats['exit_reasons']}")


def print_by_year(trades: pd.DataFrame) -> None:
    by_year = trades.groupby(trades["exit_time"].dt.year).agg(
        trades=("r", "size"),
        win_pct=("pnl", lambda p: 100 * (p > 0).mean()),
        total_r=("r", "sum"),
        avg_r=("r", "mean"),
        pnl=("pnl", "sum"),
    ).round(2)
    print("\n=== By year ===")
    print(by_year.to_string())


def save_equity_chart(equity: pd.Series, path) -> None:
    peak = equity.cummax()
    drawdown_pct = (equity - peak) / peak * 100
    fig, (ax_eq, ax_dd) = plt.subplots(2, 1, figsize=(14, 8), sharex=True,
                                       gridspec_kw={"height_ratios": [3, 1]})
    ax_eq.plot(equity.index, equity, color="black", linewidth=1)
    ax_eq.axhline(equity.iloc[0], color="grey", linestyle="--", linewidth=0.8)
    ax_eq.set_title("Strategy v1 (H1): account equity")
    ax_eq.set_ylabel("Equity ($)")
    ax_eq.grid(alpha=0.3)
    ax_dd.fill_between(drawdown_pct.index, drawdown_pct, 0, color="firebrick", alpha=0.5)
    ax_dd.set_ylabel("Drawdown (%)")
    ax_dd.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=110)


def main() -> None:
    settings = load_settings()
    params = StrategyParams.from_settings(settings["strategy"])
    costs = Costs.from_settings(settings)
    initial = settings["backtest"]["initial_equity"]

    path = PROJECT_ROOT / settings["data"]["h1_file"]
    bars = load_mt5_csv(path)
    bars = drop_forming_bar(bars, export_time_in_server_time(path, settings["data"]["server_utc_offset_hours"]),
                            params.timeframe)
    bars = add_indicators(bars, params)

    print(f"Backtest: {bars.index[0]} -> {bars.index[-1]}  ({len(bars):,} H1 bars)")
    print(f"Start ${initial:,.0f}, risk {settings['risk']['risk_per_trade_pct']}%/trade, "
          f"spread >= {costs.min_spread_points} pts, slippage {costs.slippage_points} pts")

    result = run_backtest(
        bars,
        signal_fn=lambda prev, curr, t: evaluate_bar(prev, curr, t, params),
        symbol=settings["symbol"], risk=settings["risk"], costs=costs, initial_equity=initial,
    )

    print_summary(summarize(result), initial)
    print_by_year(result.trades)

    out = PROJECT_ROOT / "results"
    out.mkdir(exist_ok=True)
    result.trades.to_csv(out / "trades_H1.csv", index=False)
    save_equity_chart(result.equity, out / "equity_H1.png")
    print("\nSaved results/trades_H1.csv and results/equity_H1.png")


if __name__ == "__main__":
    main()
