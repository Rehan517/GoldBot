# Progress Log

Newest entries at the top. One entry per session that made progress.
Format: date, step, what was done, what was learned, what's left over.

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
- [ ] Tick value: the user reported 0.1, but tick_size × contract_size = 1.0. Re-check in MT5.
- [ ] Quiz answer (0.05 lots, +$12 move).
- [ ] Commit Step 1.

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
