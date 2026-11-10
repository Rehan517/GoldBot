"""Compute EMA 20/50/200 and ATR 14 on the real H1 data, print the latest values
(to compare with MT5) and save a chart to results/indicators_H1.png.

Run from the project root:   python -m scripts.show_indicators
"""

import matplotlib.pyplot as plt

from goldbot.config import PROJECT_ROOT, load_settings
from goldbot.data import load_mt5_csv
from goldbot.indicators import atr, ema

SHOW_LAST_BARS = 300   # how many bars to draw on the chart


def main() -> None:
    settings = load_settings()
    s = settings["strategy"]

    bars = load_mt5_csv(PROJECT_ROOT / settings["data"]["h1_file"])
    # The last bar of an MT5 export is usually still forming (Step 1 finding).
    # Drop it: its "close" is just the price at the moment you exported.
    bars = bars.iloc[:-1]

    bars["ema_fast"] = ema(bars["close"], s["ema_fast"])
    bars["ema_slow"] = ema(bars["close"], s["ema_slow"])
    bars["ema_trend"] = ema(bars["close"], s["ema_trend"])
    bars["atr"] = atr(bars, s["atr_period"])

    # ---- Numbers to compare with MT5's Data Window ----
    cols = ["close", "ema_fast", "ema_slow", "ema_trend", "atr"]
    print(f"Last 5 CLOSED H1 bars (server time). EMA {s['ema_fast']}/{s['ema_slow']}/"
          f"{s['ema_trend']}, ATR {s['atr_period']}:\n")
    print(bars[cols].tail(5).round(2).to_string())

    # ---- Chart ----
    recent = bars.tail(SHOW_LAST_BARS)
    fig, (ax_price, ax_atr) = plt.subplots(
        2, 1, figsize=(14, 8), sharex=True, gridspec_kw={"height_ratios": [3, 1]}
    )
    ax_price.plot(recent.index, recent["close"], color="black", linewidth=1, label="Close")
    ax_price.plot(recent.index, recent["ema_fast"], label=f"EMA {s['ema_fast']}")
    ax_price.plot(recent.index, recent["ema_slow"], label=f"EMA {s['ema_slow']}")
    ax_price.plot(recent.index, recent["ema_trend"], label=f"EMA {s['ema_trend']}")
    ax_price.set_title(f"XAUUSD H1: last {SHOW_LAST_BARS} closed bars")
    ax_price.set_ylabel("Price ($)")
    ax_price.legend(loc="upper left")
    ax_price.grid(alpha=0.3)

    ax_atr.plot(recent.index, recent["atr"], color="purple")
    ax_atr.set_ylabel(f"ATR {s['atr_period']} ($)")
    ax_atr.grid(alpha=0.3)

    out_dir = PROJECT_ROOT / "results"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "indicators_H1.png"
    fig.tight_layout()
    fig.savefig(out_path, dpi=110)
    print(f"\nChart saved to {out_path.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
