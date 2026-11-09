"""Tests for goldbot.config: the symbol spec sanity checks."""

from goldbot.config import check_symbol_specs

GOOD_SPECS = {
    "digits": 2,
    "contract_size": 100.0,
    "tick_size": 0.01,
    "tick_value": 1.0,
    "volume_min": 0.01,
    "volume_step": 0.01,
    "volume_max": 100.0,
}


def test_consistent_specs_pass():
    assert check_symbol_specs(GOOD_SPECS) == []


def test_inconsistent_tick_value_is_flagged():
    specs = {**GOOD_SPECS, "tick_value": 0.1}  # 10x too small
    problems = check_symbol_specs(specs)
    assert len(problems) == 1
    assert "tick_value" in problems[0]


def test_tick_size_must_match_digits():
    specs = {**GOOD_SPECS, "digits": 3}
    assert any("digits" in p for p in check_symbol_specs(specs))
