"""Tests for goldbot.risk: position sizing."""

import itertools

import pytest

from goldbot.risk import loss_per_lot, position_size, round_down_to_step

GOLD = {   # XAUUSD specs as verified in Step 1
    "tick_size": 0.01, "tick_value": 1.0,
    "volume_min": 0.01, "volume_step": 0.01, "volume_max": 100.0,
}


def size(equity, stop, risk_pct=1.0, max_risk_pct=1.5):
    return position_size(equity, stop, GOLD, risk_pct, max_risk_pct)


# ---------- Building blocks ----------

def test_loss_per_lot():
    # A $15 move = 1,500 ticks; each tick is $1 on 1 lot.
    assert loss_per_lot(15.0, tick_size=0.01, tick_value=1.0) == pytest.approx(1500.0)


@pytest.mark.parametrize("raw, expected", [
    (0.0667, 0.06),   # always DOWN, never to nearest
    (0.0999, 0.09),
    (0.29, 0.29),     # float trap: 0.29 / 0.01 = 28.999999999999996
    (0.57, 0.57),     # another one: 0.57 / 0.01 = 56.99999999999999
    (1.0, 1.0),
    (0.009, 0.0),     # below one step -> 0
])
def test_round_down_to_step(raw, expected):
    assert round_down_to_step(raw, 0.01) == expected


# ---------- The worked example from the roadmap ----------

def test_worked_example_10k_account():
    # $10,000 x 1% = $100 at risk. $15 stop -> $1,500 per lot -> 0.0667 -> 0.06 lots.
    result = size(equity=10_000, stop=15.0)
    assert result.lots == 0.06
    assert result.risk_money == 90.0     # 0.06 x $1,500
    assert result.risk_pct == 0.9        # slightly UNDER 1% because we rounded down
    assert result.note == "ok"


def test_bigger_stop_means_smaller_position():
    assert size(100_000, stop=10.0).lots == 1.0    # $1,000 / $1,000 per lot
    assert size(100_000, stop=20.0).lots == 0.5    # twice the stop -> half the lots


def test_never_risks_more_than_target_when_sizing_normally():
    """Across many accounts and stops: if we weren't forced up to the minimum lot,
    the money at risk must never exceed the 1% target."""
    for equity, stop in itertools.product([5_000, 12_345, 50_000, 250_000], [3.3, 7.77, 15, 26.4, 61]):
        result = size(equity, stop)
        if result.note == "ok":
            assert result.risk_money <= equity * 0.01 + 1e-9


# ---------- Small accounts and the minimum lot ----------

def test_small_account_uses_min_lot_within_ceiling():
    # Your demo: $2,547 x 1% = $25.47. A $26 stop costs $26 even at 0.01 lot (1.02%).
    result = size(equity=2_547, stop=26.0)
    assert result.lots == 0.01
    assert result.risk_money == 26.0
    assert result.risk_pct == pytest.approx(1.021, abs=0.001)
    assert result.note.startswith("min lot used")


def test_small_account_skips_trade_above_ceiling():
    # A $40 stop at 0.01 lot = $40 = 1.57% of $2,547 > 1.5% ceiling -> don't trade.
    result = size(equity=2_547, stop=40.0)
    assert result.lots == 0.0
    assert result.note.startswith("skip")


# ---------- Limits and bad input ----------

def test_capped_at_broker_max_volume():
    assert size(equity=100_000_000, stop=1.0).lots == 100.0


@pytest.mark.parametrize("equity, stop", [(0, 10.0), (-5, 10.0), (10_000, 0.0), (10_000, -3.0)])
def test_invalid_input_means_no_trade(equity, stop):
    assert size(equity, stop).lots == 0.0
