"""Health report for the exported MT5 data and the symbol specs.

Run from the project root:   python -m scripts.check_data
"""

from goldbot.config import PROJECT_ROOT, check_symbol_specs, load_settings
from goldbot.data import find_problems, load_mt5_csv


def print_specs_check(symbol: dict) -> None:
    print("=== Symbol specs ===")
    problems = check_symbol_specs(symbol)
    if problems:
        for p in problems:
            print(f"  WARNING: {p}")
    else:
        print("  OK: specs are consistent")


def print_data_report(name: str, path, timeframe: str, tick_size: float) -> None:
    bars = load_mt5_csv(path)
    r = find_problems(bars, timeframe)

    print(f"\n=== {name} ({timeframe}) ===")
    print(f"  Bars:        {r['rows']:,}")
    print(f"  Date range:  {r['first_bar']}  ->  {r['last_bar']}")
    print(f"  Price range: {bars['low'].min():.2f}  ->  {bars['high'].max():.2f}")
    print(f"  Duplicates:  {r['duplicates']}     Impossible bars: {r['bad_ohlc']}")
    print(f"  Saturday bars: {r['weekend_bars']}")

    spread = bars["spread"]
    print(f"  Spread (points): median {spread.median():.0f}, 95th pct {spread.quantile(0.95):.0f},"
          f" max {spread.max():.0f}   (median = ${spread.median() * tick_size:.2f} per oz)")

    print(f"  Gaps: {len(r['weekend_gaps'])} weekend, {len(r['short_gaps'])} short (<=3h),"
          f" {len(r['long_gaps'])} long")
    longest = sorted(r["long_gaps"], key=lambda g: g[1] - g[0], reverse=True)[:5]
    for start, end in longest:
        print(f"     longest: {start} -> {end}  ({end - start})")


def print_hourly_activity(path) -> None:
    """Average tick volume per server hour: shows WHEN gold is busy in server time.

    We use it to work out the server's UTC offset: the biggest burst should be
    the US open / data releases around 12:30-14:30 UTC.
    """
    bars = load_mt5_csv(path)
    by_hour = bars.groupby(bars.index.hour)["tick_volume"].mean()
    biggest = by_hour.max()

    print("\n=== Average activity by SERVER hour (H1 tick volume) ===")
    for hour, vol in by_hour.items():
        bar = "#" * int(40 * vol / biggest)
        print(f"  {hour:02d}:00  {bar:<40}  {vol:,.0f}")


def main() -> None:
    settings = load_settings()
    symbol = settings["symbol"]
    data = settings["data"]

    print_specs_check(symbol)
    print_data_report("H1 bars", PROJECT_ROOT / data["h1_file"], "H1", symbol["tick_size"])
    print_data_report("M15 bars", PROJECT_ROOT / data["m15_file"], "M15", symbol["tick_size"])
    print_hourly_activity(PROJECT_ROOT / data["h1_file"])


if __name__ == "__main__":
    main()
