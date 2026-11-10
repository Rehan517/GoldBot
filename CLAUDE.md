# GoldBot: project guide for Claude

Rule-based trading bot for **gold (XAUUSD)** on **MetaTrader 5**, in Python. It's being built
**step by step as a learning project**: the user wants to understand every part, not receive a finished bot.

## Current status  ← update this at the end of every step / session

- **Current step:** Step 6: Validation. Parts 1–2 done (cross-check, in-sample sweep);
  **Part 3 next**: experiments (session filter on/off, M15, end-of-day exit, exit-plateau
  candidate SL 2.0×ATR / RR 2.5–3) on IN-SAMPLE, then ONE out-of-sample look at ≤3 candidates
  and a decision. 79 tests pass.
- **Last completed:** Step 5: Our own backtester (2026-11-10, commit `22d952b`)
- **Next action:** The user commits Step 6 Parts 1–2. Then Part 3. **The out-of-sample period
  (2024-01-01 →) is SEALED**: don't run anything on it until the candidates are fixed.
- **Step 6 findings so far:**
  - Cross-check vs backtesting.py (zero costs, same signals): 322/322 same entries, 98.4% same
    exits. The remaining 5 differ by one bar because of SL anchoring (fill vs signal close).
    Engine confirmed.
  - In-sample sweep (2018–2023, pessimistic costs): entry grid (EMA fast×slow) has **no
    plateau** (mostly negative). Exit grid shows a **mild plateau** at wider stops + bigger
    targets (SL 2.0–2.5×ATR, RR 2.5–3.0: +0.06 to +0.08R). But the best cell has t ≈ 0.7
    (std error ±0.11R): **not statistically significant**.
- **Step 5 headline result (2026-11-10):** v1 on H1 2018–2026, $3,000 start, pessimistic costs:
  320 trades, win 34.1%, **avg −0.001R, PF 0.97, −$183 (−6.1%)**, max DD 24.4%, worst losing
  streak 12. Truly zero-cost edge: +0.073R. With demo bar spreads only: +0.054R; with demo
  spreads + swap: +0.046R. Costs consume the whole edge.
- **Planned account size: $3,000** live, plus a matching $3,000 demo. Recommended: pick the
  broker first and open the demo with that broker (needed by Step 7). At $3,000, the last 12
  months of H1 signals size as 23 ok / 9 min-lot (1–1.5%) / 3 skipped, i.e. almost always 0.01 lot.
- **Open questions / blockers:**
  - Broker not chosen yet (using MetaQuotes-Demo).
  - The user is interested in **scalping** (several trades per day), partly so testing goes
    faster. The code supports other timeframes via config. Risks: spread and slippage become a
    large fraction of small stops; demo fills and MetaQuotes-Demo spreads are optimistic; bar data
    is less precise for small stops. Planned as a Step 6 experiment (M15, plus M5 if exported)
    with **pessimistic spread + slippage**, compared against H1 on cost-adjusted results.
    Estimated signals/year (2026-11-10): M15 ~160 (session on) / ~290 (off), H1 ~37 / ~73.
  - **Trade frequency vs forward test:** ~37 signals/year means 30 demo trades ≈ 10 months.
    Resolve in Step 6.
- **Account facts (demo):** MetaQuotes-Demo, **hedging** account type, USD, balance ≈ $2,547,
  leverage 1:100. Tick value proven = 1.0 by a live demo trade (MT5's Specification window
  wrongly displays 0.1). See D-6. The user also places manual trades on this account, so the bot
  must only touch positions carrying its own magic number (Step 8).
- **Git:** remote is named `GoldBot` (not `origin`) → https://github.com/Rehan517/GoldBot.git

## Roadmap checklist (details per step: [docs/ROADMAP.md](docs/ROADMAP.md))

Phase A: Mac (research and backtesting)
- [x] 0. Project setup: git, venv, skeleton, smoke tests
- [x] 1. Gold basics + export historical data from MT5 → `goldbot/data.py`, `scripts/check_data.py`, `config/settings.toml`
- [x] 2. Indicators by hand (EMA, ATR) → `goldbot/indicators.py`
- [x] 3. Strategy as a pure function → `goldbot/strategy.py`
- [x] 4. Risk and position sizing → `goldbot/risk.py`
- [x] 5. Our own backtester + metrics → `goldbot/backtest.py`, `goldbot/metrics.py`
- [ ] 6. Validation: `backtesting.py` cross-check, out-of-sample, parameter sweeps

Phase B: Windows VPS (connection and execution)
- [ ] 7. VPS + MT5 + Python setup, `scripts/check_connection.py`
- [ ] 8. Broker layer → `goldbot/broker/base.py`, `goldbot/broker/mt5_broker.py`
- [ ] 9. Safety guards → `goldbot/guards.py`
- [ ] 10. Live loop (dry run first) → `goldbot/live.py`

Phase C: Forward testing and going live
- [ ] 11. Demo forward test (4–8 weeks, 30+ trades)
- [ ] 12. Go-live checklist (start at 0.25–0.5% risk)

## How to work with this user (important)

- **One step at a time.** Never build ahead of the current step, even if it would be faster.
- For each step: explain the concept (trading + code) → write code in small, explained pieces →
  user runs it → stop at the **checkpoint** and ask if they're ready to move on.
- Include short "your turn" exercises. Leave git commits to the user unless they ask.
- The user knows basic Python. Explain pandas, trading concepts, and MT5 specifics; skip the
  basics of Python syntax.
- Every new piece of logic gets a pytest test. All tests must stay green.

## Hard rules for the code

- **Demo only** until Step 12 is signed off. Never weaken or bypass the safety guards (Step 9).
- `goldbot/broker/` is the ONLY place that may `import MetaTrader5`. Strategy, risk, and backtest
  code must stay plain Python so it runs on the Mac.
- The strategy is a pure function of **closed** bars (no lookahead). The backtest and live loop
  share the same `strategy.py` / `risk.py`.
- Broker-specific values (symbol name, contract size, tick value, server) live in
  `config/settings.toml`. Never hard-code them. Secrets live in `.env` (gitignored).
- Every live order is sent with its stop loss attached.

## Environment

- **Mac (dev):** Apple Silicon M2 Pro, Python 3.13, venv at `.venv/` (`source .venv/bin/activate`, then `pytest`).
  MT5 Mac app runs under Wine. It's used for manual data export, not for Python.
- **Windows VPS (live, from Step 7):** 64-bit Python + `MetaTrader5` package, attached to a running,
  logged-in MT5 terminal with Algo Trading enabled. Not rented yet.

## Keeping the tracking files up to date

At the end of every step (or a session that made progress):
1. Update **Current status** above and tick the checklist.
2. Add a dated entry to [docs/PROGRESS.md](docs/PROGRESS.md): what was done, what was learned,
   anything unfinished.
3. If a design choice was made or changed, add it to [docs/DECISIONS.md](docs/DECISIONS.md).
4. Update the "Status" line in [README.md](README.md).
