"""Cross-check our backtester against the independent backtesting.py library.

Both engines get the SAME signals (from strategy.evaluate_bar) and ZERO costs, so any
difference comes from how each engine simulates fills and exits.

One known, intentional difference: our engine places SL/TP relative to the actual FILL
price (next bar's open). backtesting.py needs SL/TP prices when the order is placed, so
there we use the signal bar's CLOSE. On H1, open and previous close are usually cents
apart, so most trades should match exactly.

Run from the project root:   python -m scripts.cross_check
"""

import warnings

import numpy as np
import pandas as pd
from backtesting import Backtest, Strategy

from goldbot.backtest import Costs, run_backtest
from goldbot.config import PROJECT_ROOT, load_settings
from goldbot.data import load_mt5_csv
from goldbot.strategy import StrategyParams, add_indicators, evaluate_bar

ZERO_COSTS = Costs(0, 0, 0, 0, 0)


def precompute_signals(bars: pd.DataFrame, params: StrategyParams) -> tuple[np.ndarray, np.ndarray]:
    """For every bar: direction (+1 buy, -1 sell, 0 none) and stop distance."""
    rows, times = bars.to_dict("records"), bars.index
    direction, stop = np.zeros(len(rows)), np.zeros(len(rows))
    for i in range(1, len(rows)):
        s = evaluate_bar(rows[i - 1], rows[i], times[i], params)
        if s is not None:
            direction[i] = 1 if s.direction == "buy" else -1
            stop[i] = s.stop_distance
    return direction, stop


class ReplaySignals(Strategy):
    """backtesting.py strategy that simply replays our precomputed signals."""
    reward_risk = 2.0

    def init(self):
        pass

    def next(self):
        if self.position:              # one position at a time, like our engine
            return
        d, stop, close = self.data.SigDir[-1], self.data.SigStop[-1], self.data.Close[-1]
        if d > 0:
            self.buy(size=1, sl=close - stop, tp=close + self.reward_risk * stop)
        elif d < 0:
            self.sell(size=1, sl=close + stop, tp=close - self.reward_risk * stop)


def main() -> None:
    settings = load_settings()
    params = StrategyParams.from_settings(settings["strategy"])
    bars = add_indicators(load_mt5_csv(PROJECT_ROOT / settings["data"]["h1_file"]).iloc[:-1], params)

    # --- Ours: zero costs, huge equity so position sizing never skips a trade ---
    # Our engine uses max(bar's recorded spread, min_spread_points), so "zero costs" also
    # needs the bar spreads set to 0. (The first version of this script forgot that.)
    no_spread_bars = bars.assign(spread=0)
    ours = run_backtest(no_spread_bars, lambda a, b, t: evaluate_bar(a, b, t, params),
                        settings["symbol"], settings["risk"], ZERO_COSTS, initial_equity=1e9).trades
    ours = ours.set_index("entry_time")

    # --- backtesting.py: same signals, 1 unit (1 oz) per trade, zero costs ---
    direction, stop = precompute_signals(bars, params)
    df = bars.rename(columns={"open": "Open", "high": "High", "low": "Low", "close": "Close",
                              "tick_volume": "Volume"})[["Open", "High", "Low", "Close", "Volume"]]
    df["SigDir"], df["SigStop"] = direction, stop
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        bt = Backtest(df, ReplaySignals, cash=10_000_000, commission=0, spread=0,
                      trade_on_close=False, finalize_trades=True)
        stats = bt.run(reward_risk=params.reward_risk)
    theirs = stats._trades.set_index("EntryTime")
    sig_stop = pd.Series(stop, index=df.index).shift(1)            # stop of the bar BEFORE entry
    theirs["r_bt"] = theirs["PnL"] / (sig_stop.reindex(theirs.index) * theirs["Size"].abs())

    # --- Compare trade by trade ---
    both = ours.join(theirs, how="inner")
    same_exit = (both["exit_time"] == both["ExitTime"])
    r_diff = (both["r"] - both["r_bt"]).abs()

    print(f"Trades:  ours {len(ours)},  backtesting.py {len(theirs)},  same entry time {len(both)}")
    print(f"Same exit time:         {same_exit.sum()} / {len(both)}  ({100 * same_exit.mean():.1f}%)")
    print(f"Average R:              ours {ours['r'].mean():+.4f}   backtesting.py {theirs['r_bt'].mean():+.4f}")
    print(f"Total R:                ours {ours['r'].sum():+.2f}    backtesting.py {theirs['r_bt'].sum():+.2f}")
    print(f"Median |R difference| on matched trades: {r_diff.median():.4f}")

    mismatched = both[~same_exit]
    if len(mismatched):
        print(f"\nFirst {min(5, len(mismatched))} trades with different exits:")
        cols = ["direction", "exit_time", "exit_reason", "r", "ExitTime", "ExitPrice", "r_bt"]
        print(mismatched[cols].head(5).to_string())


if __name__ == "__main__":
    main()
