"""Position sizing: how many lots so that hitting the stop loss costs a fixed % of equity.

    money at risk  = equity x risk%
    loss per lot   = (stop distance / tick size) x tick value
    lots           = money at risk / loss per lot     -> rounded DOWN to the volume step

Rounding is always DOWN, so we never risk more than intended. If even the minimum
lot is too big, we only trade it if the risk stays under a hard ceiling; otherwise skip.

Note: with SL/TP prices set from the actual fill price (Signal.stop_loss_price), the loss
at the stop equals the stop distance exactly. Slippage and weekend gaps can still make a
real loss bigger than 1R, which is why the ceiling and the Step 9 guards exist.
"""

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class PositionSize:
    lots: float          # 0.0 means "don't trade"
    risk_money: float    # $ lost if the stop is hit with this many lots
    risk_pct: float      # the same, as % of equity
    note: str            # human-readable explanation (shown in logs and backtest reports)


def loss_per_lot(stop_distance: float, tick_size: float, tick_value: float) -> float:
    """$ lost on 1.00 lot if price moves `stop_distance` against us."""
    ticks = stop_distance / tick_size   # e.g. $15 / $0.01 = 1,500 ticks
    return ticks * tick_value           # 1,500 ticks x $1 per tick per lot = $1,500


def round_down_to_step(lots: float, step: float) -> float:
    """Round DOWN to a multiple of `step`, e.g. 0.0667 -> 0.06 for step 0.01.

    Floats are imprecise: 0.29 / 0.01 gives 28.999999999999996, and a plain floor()
    would wrongly give 0.28. The tiny 1e-9 nudge fixes that without ever rounding
    a genuinely smaller number up.
    """
    steps = math.floor(lots / step + 1e-9)
    decimals = max(0, -math.floor(math.log10(step)))   # step 0.01 -> 2 decimal places
    return round(steps * step, decimals)


def position_size(
    equity: float,
    stop_distance: float,
    symbol: dict,
    risk_pct: float,
    max_risk_pct: float,
) -> PositionSize:
    """How many lots to trade. `symbol` is the [symbol] section of settings.toml."""
    if equity <= 0 or stop_distance <= 0:
        return PositionSize(0.0, 0.0, 0.0, "skip: equity and stop distance must be positive")

    per_lot = loss_per_lot(stop_distance, symbol["tick_size"], symbol["tick_value"])
    target_money = equity * risk_pct / 100
    max_money = equity * max_risk_pct / 100

    lots = round_down_to_step(target_money / per_lot, symbol["volume_step"])
    lots = min(lots, symbol["volume_max"])
    note = "ok"

    if lots < symbol["volume_min"]:
        # Even the smallest allowed trade risks more than the target.
        min_lot_money = symbol["volume_min"] * per_lot
        if min_lot_money <= max_money:
            lots = symbol["volume_min"]
            note = f"min lot used: risk above target but within the {max_risk_pct}% ceiling"
        else:
            return PositionSize(
                0.0, 0.0, 0.0,
                f"skip: min lot {symbol['volume_min']} would risk ${min_lot_money:.2f} "
                f"({min_lot_money / equity * 100:.2f}%), above the {max_risk_pct}% ceiling",
            )

    risk_money = lots * per_lot
    return PositionSize(lots, round(risk_money, 2), round(risk_money / equity * 100, 3), note)
