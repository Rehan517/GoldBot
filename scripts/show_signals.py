"""Scan the whole H1 history and list every signal Strategy v1 would have produced.

This does NOT simulate trades (that's Step 5). It only shows WHERE the rules fire,
so you can check a few of them by eye on your MT5 chart.

Run from the project root:   python -m scripts.show_signals
"""

import pandas as pd

from goldbot.config import PROJECT_ROOT, load_settings
from goldbot.data import drop_forming_bar, load_mt5_csv
from goldbot.strategy import StrategyParams, add_indicators, evaluate_bar


def export_time_in_server_time(path, server_utc_offset_hours: int) -> pd.Timestamp:
    """When was the file saved, expressed in broker server time? (Used to drop the forming bar.)"""
    saved_utc = pd.Timestamp(path.stat().st_mtime, unit="s")   # file timestamps are UTC-based
    return saved_utc + pd.Timedelta(hours=server_utc_offset_hours)


def main() -> None:
    settings = load_settings()
    params = StrategyParams.from_settings(settings["strategy"])
    path = PROJECT_ROOT / settings["data"]["h1_file"]

    bars = load_mt5_csv(path)
    now = export_time_in_server_time(path, settings["data"]["server_utc_offset_hours"])
    bars = drop_forming_bar(bars, now, params.timeframe)
    bars = add_indicators(bars, params)   # once, on all history (safe: indicators are causal)

    # Walk forward bar by bar, exactly as the live bot would see them.
    # to_dict("records") turns the rows into a list of plain dicts, which is fast to loop over.
    rows = bars.to_dict("records")
    times = bars.index
    signals = [
        s for i in range(1, len(rows))
        if (s := evaluate_bar(rows[i - 1], rows[i], times[i], params)) is not None
    ]

    table = pd.DataFrame([
        {
            "signal_bar": s.signal_bar,
            "entry_time": s.entry_time,
            "direction": s.direction,
            "close": round(s.reference_price, 2),
            "stop_$": round(s.stop_distance, 2),
            "target_$": round(s.take_profit_distance, 2),
        }
        for s in signals
    ])

    print(f"Scanned {len(bars):,} closed H1 bars: {bars.index[0]} -> {bars.index[-1]}")
    print(f"Signals: {len(table)} total  ({(table.direction == 'buy').sum()} buy, "
          f"{(table.direction == 'sell').sum()} sell)\n")

    per_year = table.groupby([table.signal_bar.dt.year, "direction"]).size().unstack(fill_value=0)
    print("Signals per year:")
    print(per_year.to_string())

    print(f"\nTypical stop distance: median ${table['stop_$'].median():.2f} "
          f"(range ${table['stop_$'].min():.2f} - ${table['stop_$'].max():.2f})")

    print("\nLast 10 signals (server time):")
    print(table.tail(10).to_string(index=False))


if __name__ == "__main__":
    main()
