"""Parameter sweep on the IN-SAMPLE period only (out-of-sample stays sealed).

Grid A: ema_fast x ema_slow       (how we enter)
Grid B: sl_atr_mult x reward_risk (how we exit)

We're looking for a PLATEAU (many neighbouring settings that all work), not the single best
cell. One bright cell surrounded by losers is luck, not an edge.

Run from the project root:   python -m scripts.sweep
Outputs: results/sweep_entry.png, results/sweep_exit.png
"""

import dataclasses

import matplotlib.pyplot as plt
import pandas as pd

from goldbot.config import PROJECT_ROOT, load_settings
from goldbot.data import load_closed_bars
from goldbot.strategy import StrategyParams
from goldbot.validation import backtest_period


def sweep(raw_bars, base: StrategyParams, settings: dict, row_param: str, rows: list,
          col_param: str, cols: list, end: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Run every (row, col) combination. Returns (avg R table, trade count table)."""
    avg_r = pd.DataFrame(index=rows, columns=cols, dtype=float)
    n_trades = pd.DataFrame(index=rows, columns=cols, dtype=float)
    for r in rows:
        for c in cols:
            params = dataclasses.replace(base, **{row_param: r, col_param: c})
            stats, _ = backtest_period(raw_bars, params, settings, end=end)
            avg_r.loc[r, c] = stats.get("avg_r", float("nan"))
            n_trades.loc[r, c] = stats["trades"]
    avg_r.index.name, avg_r.columns.name = row_param, col_param
    return avg_r, n_trades


def save_heatmap(table: pd.DataFrame, title: str, path, highlight: tuple) -> None:
    fig, ax = plt.subplots(figsize=(8, 6))
    limit = max(abs(table.min().min()), abs(table.max().max()), 0.05)
    im = ax.imshow(table.values, cmap="RdYlGn", vmin=-limit, vmax=limit)   # red = losing, green = winning
    ax.set_xticks(range(len(table.columns)), labels=table.columns)
    ax.set_yticks(range(len(table.index)), labels=table.index)
    ax.set_xlabel(table.columns.name)
    ax.set_ylabel(table.index.name)
    for i, row in enumerate(table.index):
        for j, col in enumerate(table.columns):
            is_v1 = (row, col) == highlight
            ax.text(j, i, f"{table.loc[row, col]:+.3f}", ha="center", va="center", fontsize=9,
                    fontweight="bold" if is_v1 else "normal")
    ax.set_title(title + "\n(bold = current v1 settings)")
    fig.colorbar(im, ax=ax, label="average R per trade")
    fig.tight_layout()
    fig.savefig(path, dpi=110)


def main() -> None:
    settings = load_settings()
    base = StrategyParams.from_settings(settings["strategy"])
    end = settings["validation"]["in_sample_end"]
    raw = load_closed_bars(PROJECT_ROOT / settings["data"]["h1_file"], base.timeframe,
                           settings["data"]["server_utc_offset_hours"])
    out = PROJECT_ROOT / "results"
    out.mkdir(exist_ok=True)
    pd.set_option("display.width", 120)

    print(f"IN-SAMPLE ONLY: start -> {end}. Pessimistic costs. Cells = average R per trade.\n")

    entry_r, entry_n = sweep(raw, base, settings, "ema_fast", [10, 15, 20, 25, 30],
                             "ema_slow", [40, 50, 60, 80, 100], end)
    print("Grid A: entry (ema_fast rows x ema_slow columns)")
    print(entry_r.round(3).to_string())
    print(f"  trades per cell: {int(entry_n.min().min())} - {int(entry_n.max().max())}")
    save_heatmap(entry_r, "Entry: EMA fast x EMA slow (in-sample)", out / "sweep_entry.png",
                 (base.ema_fast, base.ema_slow))

    exit_r, exit_n = sweep(raw, base, settings, "sl_atr_mult", [1.0, 1.5, 2.0, 2.5, 3.0],
                           "reward_risk", [1.0, 1.5, 2.0, 2.5, 3.0], end)
    print("\nGrid B: exits (sl_atr_mult rows x reward_risk columns)")
    print(exit_r.round(3).to_string())
    print(f"  trades per cell: {int(exit_n.min().min())} - {int(exit_n.max().max())}")
    save_heatmap(exit_r, "Exits: stop size x reward:risk (in-sample)", out / "sweep_exit.png",
                 (base.sl_atr_mult, base.reward_risk))

    positive = (entry_r > 0).sum().sum() + (exit_r > 0).sum().sum()
    print(f"\nCells with positive average R: {positive} / {entry_r.size + exit_r.size}")
    print("Saved results/sweep_entry.png and results/sweep_exit.png")


if __name__ == "__main__":
    main()
