# GoldBot

A rule-based trading bot for **gold (XAUUSD)** on **MetaTrader 5**, built step by step.

> **Status:** Step 5 (backtester). Demo account only. No real money until Step 12.

## How it's organised

| Part | Runs on | What it does |
|------|---------|--------------|
| `goldbot/` strategy, risk, backtest | Mac **and** VPS | Plain Python: rules, position sizing, simulation |
| `goldbot/broker/mt5_broker.py` | Windows VPS only | Talks to MT5 (the `MetaTrader5` library is Windows-only) |

## Setup (Mac)

```bash
cd ~/Desktop/Trading/GoldBot
python3 -m venv .venv              # create the virtual environment (once)
source .venv/bin/activate          # activate it (every new terminal)
pip install -r requirements.txt    # install pinned dependencies
pytest                             # run the tests
```

## Project docs

- [CLAUDE.md](CLAUDE.md): current step, checklist, and working rules (Claude Code loads it automatically)
- [docs/ROADMAP.md](docs/ROADMAP.md): what each of the 12 steps covers and its checkpoint
- [docs/PROGRESS.md](docs/PROGRESS.md): dated log of each session
- [docs/DECISIONS.md](docs/DECISIONS.md): why the project is built the way it is

## Strategy v1 (to be tested, not trusted)

H1 timeframe. Only long when the close is above EMA(200), only short when it's below.
Enter when EMA(20) crosses EMA(50) in the trend direction. Stop loss = 1.5 × ATR(14),
take profit = 2 × stop distance. One position at a time, 1% risk per trade.
