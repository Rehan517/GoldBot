# Progress Log

Newest entries at the top. One entry per session that made progress.
Format: date, step, what was done, what was learned, what's left over.

---

## 2026-11-10: Step 5 (Our own backtester)

**Done**
- Taught: the order of each simulated bar (enter → exit → record equity → signal), bid/ask
  conventions, pessimistic rules (spread floor 25 pts, 5 pts slippage on entries and stops, SL
  first when both are hit in one bar, gap through the SL fills at the open, gap through the TP
  fills at the TP), swap (Wed ×3, weekends free), and the metrics (win rate, avg R, PF, drawdown,
  losing streak).
- Config `[backtest]`: initial_equity 3000, min_spread_points 25, slippage_points 5,
  commission_per_lot 0.
- Built `goldbot/backtest.py` (`run_backtest` with an injectable `signal_fn`, `Costs`,
  `swap_nights`), `goldbot/metrics.py` (`summarize`, `max_drawdown`, `longest_losing_streak`),
  `scripts/run_backtest.py` (summary, by-year table, `results/trades_H1.csv`,
  `results/equity_H1.png`), and `tests/test_backtest.py`. **76 tests pass.**

**Results: Strategy v1, H1, 2018-01 → 2026-11, $3,000 start**
| Costs | avg R | PF | Net |
|---|---|---|---|
| None | +0.054 | 1.08 | +$499 |
| Demo spreads only | +0.046 | 1.06 | +$343 |
| **Pessimistic (default)** | **−0.001** | **0.97** | **−$183** |

320 trades, 9 skipped, win rate 34.1% (breakeven ≈33%), max DD $798 (24.4%), worst losing streak
12, avg hold 9 bars, swap −$73. Profitable years: 2020–22, 2024–25. Losing years: 2018–19, 2023,
2026. **Conclusion: v1 has at most a tiny gross edge, and realistic costs erase it.** Step 6
investigates, with out-of-sample discipline.

Note: avg R ≈ 0 but net −$183 because the $ risk per trade varies (min-lot effects and rounding),
so $ results and R results don't line up exactly.

**Left over**
- [ ] The user explains the first trades in `results/trades_H1.csv`.
- [ ] Commit Step 5.

---

## 2026-11-10: Step 4 (Risk and position sizing)

**Done**
- Taught: R-multiples (breakeven win rate at 2R targets = 33%), fixed-fractional sizing,
  rounding DOWN to the volume step, min/max lot, and the float trap (0.29/0.01 = 28.999…).
- Config `[risk]`: `risk_per_trade_pct = 1.0` and `max_risk_per_trade_pct = 1.5` (if even the
  minimum lot exceeds the ceiling, skip the trade).
- Built `goldbot/risk.py` (`loss_per_lot`, `round_down_to_step`, `position_size` →
  `PositionSize(lots, risk_money, risk_pct, note)`) and `tests/test_risk.py`. **54 tests pass.**
- Built `scripts/position_size.py`: a calculator (`--equity --stop`), or sizing of the last 12
  months of real signals for a given equity.
- Checkpoint example: $10,000, $15 stop → 0.06 lots, $90 (0.9%). Matches.

**Finding: account size vs minimum lot.** At $2,547, all 35 signals from the last 12 months
size to 0.01 lot: 17 under 1%, 15 between 1% and 1.5% (min lot used), and 3 skipped (stops of
$46–87 would risk 1.8–3.4%). There's effectively no sizing at this equity; risk just floats with
the stop distance.

**Exercise:** the user sized (a) $2,547 with an $18 stop → 0.01 lots, 0.71% and (b) $20,000 with
a $26 stop → 0.07 lots, 0.91%. Both correct. The user didn't know why the results were under 1%,
so we explained: rounding down discards up to one 0.01 step, and one step is 71% of the ideal
size in (a) but only 13% in (b).

**Account size decided:** $3,000 live, plus a matching $3,000 demo. Suggested choosing the broker
first and opening the demo with them. At $3,000: 23 ok / 9 min-lot / 3 skipped over the last 12
months.

Committed: `5f53a7d`. **Step 4 complete.**

---

## 2026-11-10: Step 3 (Strategy as a pure function)

**Done**
- Taught: pure functions and why the backtest and live bot must share them; separation of
  concerns (strategy vs risk vs position state vs guards); the exact definition of a cross;
  why signals carry stop *distances*, not prices; and the closed-bar rule.
- Added to `[strategy]` in config: `sl_atr_mult`, `reward_risk`, and the session filter
  (entries 10:00–20:00 server time ≈ London open to NY early afternoon).
- Built `goldbot/strategy.py`: `StrategyParams` (strict loading from config, typos rejected),
  `Signal` (with `stop_loss_price`/`take_profit_price`), `add_indicators`, `evaluate_bar`, and
  `generate_signal`.
- Added `drop_forming_bar(bars, now, timeframe)` to `goldbot/data.py`.
- Tests: `tests/test_strategy.py` (13) plus 2 closed-bar tests. **37 tests pass.**
- Built `scripts/show_signals.py`: scans the whole history and lists signals.

**Findings**
- 329 signals over 2018–2026 (171 buy / 158 sell), about 37 per year. The median stop is $6.02
  across all years, and about $20–35 in 2026 (gold is now around $4,000, so ATR is bigger).
- The Nov 4 2026 bullish cross (07:00 bar, close 3997.82 just above EMA200 3995.82) was
  **blocked by the session filter** (entry 08:00 < 10:00), and gold then rallied more than $100.
  Lesson: filters block winners too, so test session filter on vs off in Step 6.

**User tasks (all done):** verified the 2026-10-29 sell on the MT5 chart, did the session filter
exercise (H1 without the filter gives ~648 signals vs 329), and committed (`fa67069`).

**Side discussion:** the user is interested in scalping (several trades per day). We discussed
faster testing versus spread taking a bigger share of small stops, and added scalping variants
with pessimistic costs to the Step 5/6 plans (see the ROADMAP and CLAUDE.md open questions).

**Step 3 complete.**

---

## 2026-11-10: Step 2 (Indicators by hand)

**Done**
- Taught: the EMA formula (α = 2/(n+1), seeded with the first price like MT5), true range
  (includes gaps), ATR (MT5 = simple average of TR; TradingView uses Wilder's smoothing),
  warm-up periods, and lookahead bias.
- Built `goldbot/indicators.py` (`ema_loop` teaching version, `ema`, `true_range`, `atr`), plus
  `tests/test_indicators.py`. The tests include a **causality test** (indicator values on
  truncated data must equal those on full data) and a test proving it catches a cheating
  `shift(-1)` indicator.
- Built `scripts/show_indicators.py`: prints the last 5 closed H1 bars with indicators and saves
  `results/indicators_H1.png`.
- Added a `[strategy]` section to `config/settings.toml` (timeframe, EMA periods, ATR period).
- 22 tests pass.

**Checkpoint: passed.** MT5 Data Window vs ours, 2026-11-09 08:00: EMA20 4091.435/4091.44,
EMA50 4075.350/4075.35, EMA200 4038.453/4038.45, ATR 17.84/17.84. At 09:00: 4090.972/4090.97,
4075.790/4075.79, 4038.931/4038.93, 18.72/18.72. Exact match.

**Also noticed:** the demo account is a **hedging** account, and the user has manual trades open
on it (e.g. SELL 0.05 at 4114.03). This matters for Step 8 (magic numbers; hedging vs netting).

**Left over**
- [ ] Commit Step 2.

**Step 2 complete.**

---

## 2026-11-09: Step 1 (Gold basics + historical data)

**Done**
- Taught: lots and contract size, tick size and tick value, bid/ask/spread, leverage vs risk,
  OHLC bars and tick volume, server time vs UTC, and the shape of a gold trading day.
- The user exported `data/raw/XAUUSD_H1.csv` (52,097 bars) and `XAUUSD_M15.csv` (208,232 bars),
  2018-01-02 → 2026-11-09, from MetaQuotes-Demo.
- Built `config/settings.toml`, `goldbot/config.py` (load + `check_symbol_specs`),
  `goldbot/data.py` (`load_mt5_csv`, `find_problems`), `scripts/check_data.py`, and tests
  (12 passing).

**Findings from the data**
- No duplicate or impossible bars, and no Saturday bars.
- Spread on MetaQuotes-Demo: median 5 points ($0.05) on H1, 95th percentile 20. That's tighter
  than typical retail gold spreads, so the backtest should assume more.
- Server = UTC+2 now (export saved 08:12 UTC, last bar stamped 10:00). NY time = server − 7h.
- The daily break widened in about April 2026 (bars run 01:00–22:00 server time), so the
  short-gap threshold was raised to 3h.
- The **last bar in an export is still forming** (10:00 bar exported at 10:12), so it must be
  dropped before use. This is the lesson for Step 3.
- Busiest server hours: 15:00–17:00 (the US open / US data releases).

**Left over**
- [x] Tick value: MT5's Specification window shows 0.1, but a live demo test proved **1.0**
      (0.01 lot bought at 4095.12; at 4097.20 the profit was +$2.08, so profit ÷ move = 1.00).
      The margin agrees: $40.95 for 0.01 lot at 1:100 = 1 oz. Config fixed, and the warning is gone.
      Demo account: USD, balance ≈ $2,547.
- [x] Quiz: 0.05 lots, +$12 move → $60 (correct).
- [x] Committed and pushed (`86fd1fb`) to GitHub (remote `GoldBot`).

**Step 1 complete.**

---

## 2026-11-09: Planning + Step 0 (Project setup)

**Done**
- Agreed on the 12-step roadmap ([ROADMAP.md](ROADMAP.md)) and the key decisions ([DECISIONS.md](DECISIONS.md)).
- Created the git repo (branch `main`), `.gitignore`, `.venv` (Python 3.13), and a pinned
  `requirements.txt` (pandas 3.1.1, numpy 2.5.4, matplotlib 3.11.2, pytest 9.2.0).
- Added `pyproject.toml` (pytest config), the `goldbot/` and `goldbot/broker/` packages, and
  `tests/test_setup.py` (3 smoke tests, all passing).
- Added project tracking: `CLAUDE.md`, `docs/ROADMAP.md`, `docs/PROGRESS.md`, `docs/DECISIONS.md`.

**Concepts covered**
- What virtual environments are for, pinned dependencies, `.gitignore` and keeping secrets out
  of git, Python packages (`__init__.py`), and isolating MT5 code in `goldbot/broker/`.

**User's "your turn" (all done)**
- [x] Activated the venv and ran `pytest -v`; ran it outside the venv to see it fail.
- [x] Selected the `.venv` interpreter in VS Code.
- [x] Made the first commit: `f24019b Step 0: project setup + tracking docs`.

**Step 0 complete.** Step 1 started: gold contract concepts explained; waiting for the user's
Specification values and the bar exports.
