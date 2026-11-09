# Progress Log

Newest entries at the top. One entry per session that made progress.
Format: date, step, what was done, what was learned, what's left over.

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

**Left over (user's "your turn")**
- [ ] Activate the venv and run `pytest -v`; try it outside the venv to see it fail.
- [ ] Select the `.venv` interpreter in VS Code.
- [ ] Make the first commit: `git add . && git commit -m "Step 0: project setup"`.
