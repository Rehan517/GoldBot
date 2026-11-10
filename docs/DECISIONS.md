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

### D-7: A stateless strategy whose signals carry distances (2026-11-10)
- **Choice:** `strategy.py` only answers "is there an entry signal on the latest closed bar?"
  It knows nothing about open positions, account size, spread, or the clock. A `Signal` holds
  stop/target **distances**. SL/TP prices are computed from the actual fill price.
- **Why:** The backtest and live bot share identical rules. The fill price isn't known when the
  signal fires (next bar open + spread), so distances keep the intended risk exact. Position
  state, sizing, and safety belong to the backtester/live loop, `risk.py`, and `guards.py`.

### D-8: Session filter of 10:00–20:00 server time (2026-11-10)
- **Choice:** Only enter when the entry time is in [10:00, 20:00) server time
  (≈ 08:00 London to 13:00 New York). It's configurable and can be switched off.
- **Why:** These are the most active hours (from check_data.py's activity profile).
  **Unproven:** it blocked the Nov 4 2026 cross, which would have been a big winner. Test it on
  vs off in Step 6.

### D-9: 1% target risk with a 1.5% ceiling; always round down (2026-11-10)
- **Choice:** Size each trade to risk 1% of equity, rounded DOWN to the 0.01 lot step. If that
  rounds below the minimum lot, trade 0.01 lot only if its risk is ≤ 1.5% of equity; otherwise
  skip the trade.
- **Why:** Rounding down means we never exceed the target. On a small account (~$2,547), even
  0.01 lot often exceeds 1% with H1 stops of about $26, so a strict 1% rule would skip most
  trades. The ceiling allows them while still blocking very wide-stop trades (3 of 35 in the
  last year).

### D-10: Plan around a $3,000 account (2026-11-10)
- **Choice:** Live starting balance $3,000, a matching $3,000 demo, and backtests starting at $3,000.
- **Why:** The backtest, demo and live account should behave identically. At this size the bot
  almost always trades 0.01 lot on H1, which is fine for learning with real money. Ideally the
  demo is with the same broker as the eventual live account.

### D-11: Pessimistic backtest assumptions (2026-11-10)
- **Choice:**
  - Fill at the next bar's open.
  - Spread = max(bar spread, 25 points). Slippage of 5 points on entries and stop exits; none
    on take profits.
  - SL assumed first if SL and TP are both inside one bar. A gap through the SL fills at the
    open; a gap through the TP fills at the TP.
  - Swap with Wed ×3 and weekends free.
  - The signal function is injected, so the engine is tested with scripted signals.
- **Why:** A backtest should understate, not overstate, live results. MetaQuotes-Demo spreads
  (median 5–8 points) are tighter than typical real accounts.
- **Consequence:** v1's gross edge (+0.054R) disappears under these costs (−0.001R). That's
  exactly the kind of truth this choice is meant to surface.
