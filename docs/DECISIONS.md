# Decision Log

Why the project is built the way it is. Add a new entry when a choice is made or reversed;
don't silently change an old one. If a decision is reversed, mark it **Superseded by D-x**.

---

### D-1: Python, with the live bot on a Windows VPS (2026-11-09)
- **Choice:** Python, not an MQL5 Expert Advisor. Live execution runs on a cloud Windows VPS.
- **Why:** The user knows some Python. The official `MetaTrader5` Python library is
  **Windows-only**, and the user's Mac (M2 Pro) runs MT5 through Wine, where bridging Python is
  fragile. A VPS also keeps the bot running 24/5 without the Mac.
- **Rejected:** MQL5 EA (a new language), a Windows VM on the Mac (the bot stops when the Mac
  sleeps), and the Wine/rpyc bridge (fragile with real money).

### D-2: Only the broker layer needs Windows (2026-11-09)
- **Choice:** Strategy, risk, backtest, and guards are plain Python that runs anywhere. Only
  `goldbot/broker/mt5_broker.py` imports `MetaTrader5`.
- **Why:** Most of the development and learning happens on the Mac. The backtest and live bot run
  the *same* strategy code, so they can't drift apart. The VPS is rented only once the strategy
  looks worthwhile.

### D-3: Start with a simple strategy, then iterate (2026-11-09)
- **Choice:** Strategy v1 on H1:
  - Trend filter: EMA(200).
  - Entry: EMA(20) crossing EMA(50).
  - Stop loss: 1.5 × ATR(14). Take profit: 2R.
  - One position at a time, a session filter, and 1% risk.
- **Why:** The first goal is to learn the whole pipeline end to end. The rules get refined from
  backtest evidence in Step 6. The user's style is intraday (M15–H1).

### D-4: Write our own backtester, then cross-check with backtesting.py (2026-11-09)
- **Choice:** A small bar-by-bar backtester with deliberately pessimistic fill rules, then compare
  its results with the `backtesting.py` library.
- **Why:** Every simulation assumption is visible and understood, and the cross-check catches
  bugs in our own code.

### D-5: Broker-agnostic config; MetaQuotes-Demo for now (2026-11-09)
- **Choice:** Symbol name, contract specs, and server live in `config/settings.toml` / `.env`.
- **Why:** No broker has been chosen yet. Gold symbol names (XAUUSD / GOLD / XAUUSD.m), contract
  sizes, and spreads differ between brokers, so switching should be a config change only.

### D-6: Sanity-check symbol specs in code (2026-11-09)
- **Choice:** `check_symbol_specs` verifies `tick_value == tick_size × contract_size`,
  `tick_size == 10^-digits`, and the volume limits. `check_data.py` prints a WARNING if any fail.
- **Why:** These numbers drive position sizing. The first reported tick value (0.1) was 10× off
  what the other specs imply, and a silent mistake like that would make every trade the wrong size.
- **Outcome:** MT5's Specification window really does display 0.1, but a live 0.01-lot demo
  trade proved the true value is 1.0 ($2.08 move → $2.08 profit). **Rule: measured P/L beats
  displayed specs.** Re-run this test whenever the broker or account changes.
