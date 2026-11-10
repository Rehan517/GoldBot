# GoldBot Roadmap

The detailed plan for every step. Progress is tracked in [CLAUDE.md](../CLAUDE.md) (checklist)
and [PROGRESS.md](PROGRESS.md) (session log). This file only changes if the plan itself changes.

Each step has three parts: what you **learn**, what we **build**, and a **checkpoint** to reach
before moving on.

---

## Phase A: Mac (no VPS needed)

### Step 0: Project setup
- **Learn:** virtual environments, project structure, git, why secrets never go into git.
- **Build:** git repo, `.gitignore`, `.venv`, pinned `requirements.txt`, `pyproject.toml`
  (pytest config), `goldbot/` package skeleton, smoke tests, README.
- **Checkpoint:** `pytest` passes inside the venv and the first commit is made.

### Step 1: Gold basics + getting historical data
- **Learn:**
  - What a lot of gold is (usually 100 oz, so a $1 move = $100 per lot).
  - Point and tick size, tick value, spread, leverage and margin.
  - OHLC bars and tick volume.
  - **Broker server time vs UTC.**
- **You do:**
  - In Mac MT5, open the XAUUSD *Specification* window and note contract size, tick size,
    tick value, min/step/max volume, and stops level.
  - Export H1 and M15 bars (View → Symbols → Bars → Request → Export) to `data/raw/`.
- **Build:**
  - `goldbot/data.py`: parse the MT5 export into a pandas DataFrame.
  - `scripts/check_data.py`: find gaps, duplicates, and weekend bars, and print the date range.
  - `config/settings.toml` with the symbol specs.
- **Checkpoint:** the data loads, the checks print a sensible summary, and the specs are in config.

### Step 2: Indicators by hand
- **Learn:** EMA math, true range and ATR, and **lookahead bias** (using information the bot
  couldn't have had at the time).
- **Build:** `goldbot/indicators.py`, `tests/test_indicators.py`, and a matplotlib chart of price + EMAs.
- **Checkpoint:** tests pass, and our EMA/ATR values match MT5's built-in indicators on the same
  bars (within rounding).

### Step 3: Strategy as a pure function
- **Learn:** turning trading rules into code, closed bar vs forming bar, and why a pure function
  (no MT5 calls) can be shared by the backtest and the live bot.
- **Build:** `goldbot/strategy.py` (a `Signal` dataclass: direction, entry reference, SL, TP) and
  `tests/test_strategy.py` with hand-made bar data.
- **Checkpoint:** tests cover a long signal, a short signal, no signal, and the trend filter
  blocking a counter-trend cross.

### Step 4: Risk and position sizing
- **Learn:** R-multiples, fixed-fractional sizing,
  `lots = (equity × risk%) / (stop distance ÷ tick size × tick value)`, rounding down to the
  volume step, and min/max lot clamps.
- **Build:** `goldbot/risk.py` and `tests/test_risk.py`.
- **Checkpoint:** a worked example by hand (e.g. $10,000, 1% risk, $15 stop → 0.06 lots) matches the code.

### Step 5: Our own backtester
- **Learn:** how a simulation can lie to you, and the assumptions we make on purpose:
  - Signal on bar close, fill at the next bar's open.
  - Buys pay the spread (MT5 bars are bid prices; the export includes the spread).
  - SL/TP are checked against the bar's high and low. If both are hit in the same bar, we assume
    the SL hit first (the pessimistic choice).
  - Price gaps past the SL fill at the bar's open.
  - Commission and slippage are set in config.
  - **Swap (overnight fees)** is charged for positions held past the daily rollover.
  - **Spread and slippage are configurable and pessimistic.** They decide whether scalping
    variants survive in Step 6.
- **Build:** `goldbot/backtest.py`, `goldbot/metrics.py`, `scripts/run_backtest.py` (trade list
  CSV + equity curve chart), and `tests/test_backtest.py` (tiny scenarios with known answers).
- **Checkpoint:** the backtest runs on your exported data, you can explain every trade in the
  first 10, and these stats are calculated: net P&L, number of trades, win rate, average R,
  profit factor, expectancy, max drawdown.

### Step 6: Validation and iteration
- **Learn:** overfitting; in-sample vs out-of-sample; looking for a **plateau** of good
  parameters, not a single best peak; walk-forward testing.
- **Build:**
  - Cross-check against `backtesting.py`: the same signals should produce the same trades, and
    P&L should be close.
  - A parameter-sweep script with a heatmap.
  - Experiments: M15 vs H1, session filter on/off, end-of-day exit, and **scalping variants**
    (M15, plus M5 if exported). Judge them on results *after* pessimistic spread + slippage, and
    check how sensitive each one is to the spread assumption.
  - **Trade frequency vs forward-test length:** H1 + session filter gives ~37 signals/year, so 30
    demo trades would take ~10 months. Decide here how to resolve that (timeframe, filters, or a
    longer demo period).
- **Checkpoint:** a written-down v1 config with out-of-sample results we both believe in. If the
  edge looks bad, we change the rules here, before paying for a VPS.

## Phase B: Windows VPS + MT5 connection

### Step 7: VPS and MT5 setup
- **Learn:**
  - RDP from the Mac (Microsoft "Windows App").
  - Choosing a VPS: 2 vCPU / 4 GB is plenty; locate it near the broker's server.
  - How the Python library attaches to a **running, logged-in** MT5 terminal.
  - Enabling the *Algo Trading* button.
- **You do:**
  - Rent the VPS.
  - Install MT5 and log in to the demo account.
  - Install **64-bit Python** (the newest version `MetaTrader5` supports on PyPI; 3.12 is a safe choice).
  - Push the repo to a private GitHub repo and clone it on the VPS.
- **Build:** `.env` handling, `requirements-windows.txt`, and `scripts/check_connection.py`
  (prints account info, confirms `trade_mode == DEMO`, and shows the live XAUUSD specs and spread).
- **Checkpoint:** the script prints the demo balance and the XAUUSD specs, and they match config.

### Step 8: Broker layer
- **Learn:**
  - `mt5.initialize`, `copy_rates_from_pos`, `symbol_info_tick`, `positions_get`.
  - The `order_send` request dict, `order_check` before sending, and filling modes (FOK/IOC/RETURN).
  - The `deviation` field, **magic numbers**, and return codes (`TRADE_RETCODE_DONE`,
    10027 = Algo Trading disabled, …).
  - Hedging vs netting accounts.
- **Build:**
  - `goldbot/broker/base.py`: the interface.
  - `goldbot/broker/mt5_broker.py`: get bars, account, and positions; place a market order
    **with SL/TP attached**; close; modify.
  - `scripts/demo_order_roundtrip.py`: open 0.01 lot, read it back, close it.
- **Checkpoint:** the round-trip works on demo, and the trade appears in MT5 history with our
  magic number and comment.

### Step 9: Safety guards (before the bot trades on its own)
- **Learn:** defense in depth, and why every guard should "fail closed" (if a check fails or
  errors, the bot doesn't trade).
- **Build:** `goldbot/guards.py` + tests:
  - **Demo-only lock:** refuse a real account unless `allow_real = true` is set in config *and*
    confirmed in `.env`.
  - **Daily loss limit**, e.g. −3%.
  - **Max lot cap** and max one open position.
  - **Spread filter:** skip trades if the current spread is too wide.
  - **Session / rollover / weekend-close filter.**
  - **`STOP` kill-switch file.**
- **Checkpoint:** each guard is shown blocking a trade in a test.

### Step 10: The live loop
- **Learn:**
  - Detecting a newly closed bar by polling.
  - Processing each bar exactly once (idempotency).
  - **Reconciling state from MT5 on restart**: read open positions by magic number.
  - Reconnecting with backoff, structured logging, and a trade journal CSV.
- **Build:** `goldbot/live.py` and `scripts/run_live.py`. They reuse `strategy.py`, `risk.py`, and
  `guards.py` unchanged.
- **Checkpoint:** a dry-run mode logs "would buy/sell" without sending orders. After that, it
  trades on demo.

## Phase C: Forward testing and going live

### Step 11: Demo forward test on the VPS
- **Build:** auto-start (Task Scheduler + MT5 auto-login), log rotation, optional Telegram alerts,
  and a weekly review script.
- **Run:** at least 4–8 weeks / 30+ trades. Re-run the backtest on the same period and compare
  the trades one by one. Measure real spread and slippage against our assumptions.
- **Checkpoint:** demo results are consistent with the backtest, with no unexplained trades or crashes.

### Step 12: Go-live checklist (real money)
- Forward test passed, all guards tested, and the broker is chosen (its symbol and specs re-checked).
- Switch the account through `.env` and config only, with no code changes.
- Start at **0.25–0.5% risk** and the smallest lot sizes, and review daily.
