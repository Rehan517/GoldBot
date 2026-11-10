"""Position size calculator + what sizing means for real signals on YOUR account size.

Run from the project root:
    python -m scripts.position_size --equity 2547 --stop 26     # one calculation
    python -m scripts.position_size --equity 2547               # apply to recent real signals
"""

import argparse

import pandas as pd

from goldbot.config import PROJECT_ROOT, load_settings
from goldbot.data import load_mt5_csv
from goldbot.risk import position_size
from goldbot.strategy import StrategyParams, add_indicators, evaluate_bar


def show_one(equity: float, stop: float, symbol: dict, risk: dict) -> None:
    r = position_size(equity, stop, symbol, risk["risk_per_trade_pct"], risk["max_risk_per_trade_pct"])
    print(f"Equity ${equity:,.2f}, stop ${stop:.2f}, target risk {risk['risk_per_trade_pct']}%")
    print(f"  -> lots: {r.lots}   risk: ${r.risk_money:.2f} ({r.risk_pct}%)   [{r.note}]")
    if r.lots:
        print(f"  -> win at 2R: +${2 * r.risk_money:.2f}   loss at stop: -${r.risk_money:.2f}")


def show_signals(equity: float, settings: dict, months: int = 12) -> None:
    """Size every signal from the last `months` months as if the account were `equity`."""
    params = StrategyParams.from_settings(settings["strategy"])
    symbol, risk = settings["symbol"], settings["risk"]

    bars = add_indicators(load_mt5_csv(PROJECT_ROOT / settings["data"]["h1_file"]).iloc[:-1], params)
    bars = bars[bars.index >= bars.index[-1] - pd.DateOffset(months=months + 1)]  # +1 for warm-up
    rows, times = bars.to_dict("records"), bars.index
    cutoff = bars.index[-1] - pd.DateOffset(months=months)

    results = []
    for i in range(1, len(rows)):
        s = evaluate_bar(rows[i - 1], rows[i], times[i], params)
        if s is None or s.signal_bar < cutoff:
            continue
        r = position_size(equity, s.stop_distance, symbol,
                          risk["risk_per_trade_pct"], risk["max_risk_per_trade_pct"])
        results.append({"signal_bar": s.signal_bar, "dir": s.direction, "stop_$": round(s.stop_distance, 2),
                        "lots": r.lots, "risk_$": r.risk_money, "risk_%": r.risk_pct, "note": r.note})

    table = pd.DataFrame(results)
    status = table["note"].str.split(":").str[0]   # "ok" / "min lot used" / "skip"
    print(f"Last {months} months of signals, sized for a ${equity:,.0f} account "
          f"(target {risk['risk_per_trade_pct']}%, ceiling {risk['max_risk_per_trade_pct']}%):\n")
    print(table.to_string(index=False))
    print(f"\nTotal {len(table)}:  " + ",  ".join(f"{k} = {v}" for k, v in status.value_counts().items()))


def main() -> None:
    parser = argparse.ArgumentParser(description="Position size calculator")
    parser.add_argument("--equity", type=float, required=True, help="account equity in $")
    parser.add_argument("--stop", type=float, help="stop distance in $ (omit to size recent real signals)")
    args = parser.parse_args()

    settings = load_settings()
    if args.stop is not None:
        show_one(args.equity, args.stop, settings["symbol"], settings["risk"])
    else:
        show_signals(args.equity, settings)


if __name__ == "__main__":
    main()
