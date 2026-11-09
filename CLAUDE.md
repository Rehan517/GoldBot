# GoldBot: project guide for Claude

Rule-based trading bot for **gold (XAUUSD)** on **MetaTrader 5**, in Python. It's being built
**step by step as a learning project**: the user wants to understand every part, not receive a finished bot.

## Current status  ← update this at the end of every step / session

- **Current step:** Step 2: Indicators by hand (not started)
- **Last completed:** Step 1: Gold basics + historical data (2026-11-09, commit `86fd1fb`)
- **Next action:** Start Step 2: teach EMA, true range/ATR, and lookahead bias; build
  `goldbot/indicators.py` + tests. (The user should commit the tick_value fix first.)
- **Open questions / blockers:**
  - Broker not chosen yet (using MetaQuotes-Demo).
- **Account facts (demo):** USD account, balance ≈ $2,547, leverage 1:100. Tick value proven = 1.0
  by a live demo trade (MT5's Specification window wrongly displays 0.1). See D-6.
- **Git:** remote is named `GoldBot` (not `origin`) → https://github.com/Rehan517/GoldBot.git

## Roadmap checklist (details per step: [docs/ROADMAP.md](docs/ROADMAP.md))

Phase A: Mac (research and backtesting)
- [x] 0. Project setup: git, venv, skeleton, smoke tests
- [x] 1. Gold basics + export historical data from MT5 → `goldbot/data.py`, `scripts/check_data.py`, `config/settings.toml`
- [ ] 2. Indicators by hand (EMA, ATR) → `goldbot/indicators.py`
- [ ] 3. Strategy as a pure function → `goldbot/strategy.py`
- [ ] 4. Risk and position sizing → `goldbot/risk.py`
- [ ] 5. Our own backtester + metrics → `goldbot/backtest.py`, `goldbot/metrics.py`
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
