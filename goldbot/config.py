"""Load config/settings.toml and sanity-check the symbol specs."""

import math
import tomllib
from pathlib import Path

# goldbot/config.py -> goldbot/ -> project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SETTINGS_PATH = PROJECT_ROOT / "config" / "settings.toml"


def load_settings(path: Path = DEFAULT_SETTINGS_PATH) -> dict:
    """Read the TOML settings file into a plain dict."""
    with open(path, "rb") as f:  # tomllib requires binary mode
        return tomllib.load(f)


def check_symbol_specs(symbol: dict) -> list[str]:
    """Return a list of problems with the symbol specs (empty list = all good).

    These numbers drive position sizing, so a typo here means every trade
    is the wrong size. We check them instead of trusting them.
    """
    problems = []

    # Tick value = how many $ one tick is worth on 1 lot = tick size x contract size.
    # (This identity holds when the profit currency equals your account currency, USD here.)
    expected_tick_value = symbol["tick_size"] * symbol["contract_size"]
    if not math.isclose(symbol["tick_value"], expected_tick_value, rel_tol=1e-9):
        problems.append(
            f"tick_value is {symbol['tick_value']} but tick_size x contract_size = "
            f"{expected_tick_value:g}. One of these numbers is probably wrong."
        )

    if symbol["volume_min"] <= 0 or symbol["volume_step"] <= 0:
        problems.append("volume_min and volume_step must be positive.")
    if symbol["volume_min"] > symbol["volume_max"]:
        problems.append("volume_min is larger than volume_max.")

    # tick_size should match the number of digits (2 digits -> 0.01).
    if not math.isclose(symbol["tick_size"], 10 ** -symbol["digits"]):
        problems.append(
            f"tick_size {symbol['tick_size']} doesn't match digits={symbol['digits']}."
        )

    return problems
