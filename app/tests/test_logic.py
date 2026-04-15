"""
Unit tests — no TWS required.
Run with:  pytest app/tests/test_logic.py -v
"""

import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "claude"))

from routes.orders import _build_plan
from routes.targets import DEFAULT_TARGETS, DEFAULT_PNL_THRESHOLD


# ── Helpers ───────────────────────────────────────────────────────────────

def pnl_flag(pnl_pct: float, threshold: float = DEFAULT_PNL_THRESHOLD) -> str:
    if pnl_pct < threshold:
        return "red"
    elif pnl_pct < threshold / 2:
        return "yellow"
    return "green"


def weight_sum_valid(weights: dict) -> bool:
    return abs(sum(weights.values()) - 100.0) <= 0.1


def calc_pnl(avg_cost: float, current_price: float):
    if not avg_cost or avg_cost == 0:
        return None
    return (current_price - avg_cost) / avg_cost * 100


def calc_delta(current_pct: float, target_pct: float) -> float:
    return current_pct - target_pct


# ── UT-01 to UT-03: Weight validation ─────────────────────────────────────

def test_weight_valid_sums_to_100():
    weights = {"SUSW": 50, "XDWT": 20, "CHDVD": 10, "XDWH": 10, "CHSPI": 5, "NUKL": 5}
    assert weight_sum_valid(weights) is True


def test_weight_invalid_over_100():
    weights = {"SUSW": 50, "XDWT": 25, "CHDVD": 15, "XDWH": 10, "CHSPI": 5, "NUKL": 5}
    assert weight_sum_valid(weights) is False


def test_weight_invalid_under_100():
    weights = {"SUSW": 40, "XDWT": 20, "CHDVD": 10, "XDWH": 10, "CHSPI": 5, "NUKL": 5}
    assert weight_sum_valid(weights) is False


# ── UT-04 to UT-07: Rebalancing plan ─────────────────────────────────────

def test_plan_cash_exactly_covers():
    positions = {"SUSW": 5000.0}
    cash = 5000.0
    total = 10000.0
    targets = {"SUSW": 100.0}
    plan = _build_plan(positions, cash, total, targets, min_trade=500, excluded=[])
    included = [r for r in plan if r["included"]]
    assert len(included) == 1
    assert included[0]["ticker"] == "SUSW"
    assert abs(included[0]["suggested_chf"] - 5000) < 1


def test_plan_excludes_overweight():
    positions = {"NUKL": 2664.0}
    cash = 500.0
    total = 3164.0
    targets = {"NUKL": 5.0}
    plan = _build_plan(positions, cash, total, targets, min_trade=500, excluded=[])
    # NUKL is ~84% of total, target 5% → overweight, must NOT appear in plan
    assert all(r["ticker"] != "NUKL" or not r["included"] for r in plan)
    included = [r for r in plan if r["included"]]
    assert len(included) == 0


def test_plan_excludes_below_minimum():
    positions = {"XDWH": 2650.0}
    cash = 500.0
    total = 3150.0
    targets = {"XDWH": 85.0}
    # current = 2650/3150 = 84.1%, target = 85% → gap = ~0.9%, buy ≈ CHF 28
    plan = _build_plan(positions, cash, total, targets, min_trade=500, excluded=[])
    included = [r for r in plan if r["included"]]
    assert len(included) == 0, "Buy below min trade must be excluded"


def test_plan_trims_when_cash_insufficient():
    # Three positions all underweight, total needed > cash
    positions = {"SUSW": 1000.0, "XDWT": 1000.0, "NUKL": 1000.0}
    cash = 1000.0
    total = 4000.0
    targets = {"SUSW": 50.0, "XDWT": 30.0, "NUKL": 20.0}
    plan = _build_plan(positions, cash, total, targets, min_trade=100, excluded=[])
    included_total = sum(r["suggested_chf"] for r in plan if r["included"])
    assert included_total <= cash + 0.01, "Included buys must not exceed cash"


# ── UT-08 to UT-12: P&L flag ─────────────────────────────────────────────

def test_pnl_profit():
    assert pnl_flag(10.0) == "green"


def test_pnl_small_loss():
    assert pnl_flag(-4.0) == "green"


def test_pnl_medium_loss():
    assert pnl_flag(-8.0) == "yellow"   # threshold/2 = -5, -8 < -5 but > -10


def test_pnl_large_loss():
    assert pnl_flag(-12.0) == "red"


def test_pnl_zero_avg_cost():
    result = calc_pnl(0, 55)
    assert result is None


# ── UT-13 / UT-14: Config structure ──────────────────────────────────────────

REQUIRED_CONFIG_ATTRS = ["TARGET_ALLOCATION", "MIN_TRADE",
                         "IB_LIVE_PORT", "IB_PAPER_PORT", "IB_HOST", "IB_CLIENT_ID"]

def _load_config_file(path: Path):
    import importlib.util
    spec = importlib.util.spec_from_file_location("_cfg_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_example_config_has_required_fields():
    """config.example.py must have every field that the app reads from config.py."""
    example = Path(__file__).parent.parent.parent / "claude" / "config.example.py"
    assert example.exists(), "config.example.py is missing from the repo"
    mod = _load_config_file(example)
    for attr in REQUIRED_CONFIG_ATTRS:
        assert hasattr(mod, attr), f"config.example.py is missing required field: {attr}"


def test_example_config_weights_sum_to_100():
    """config.example.py TARGET_ALLOCATION must sum to 100% — it's the CI reference."""
    example = Path(__file__).parent.parent.parent / "claude" / "config.example.py"
    mod = _load_config_file(example)
    total = sum(mod.TARGET_ALLOCATION.values())
    assert abs(total - 100.0) < 0.1, f"config.example.py weights sum to {total:.1f}%, must be 100%"


def test_real_config_matches_example_structure():
    """If config.py exists locally, it must have the same fields as config.example.py."""
    real = Path(__file__).parent.parent.parent / "claude" / "config.py"
    if not real.exists():
        pytest.skip("config.py not present (CI environment — expected)")
    mod = _load_config_file(real)
    for attr in REQUIRED_CONFIG_ATTRS:
        assert hasattr(mod, attr), f"config.py is missing required field: {attr}"
    total = sum(mod.TARGET_ALLOCATION.values())
    assert abs(total - 100.0) < 0.1, f"config.py weights sum to {total:.1f}%, must be 100%"


def test_default_targets_loaded():
    assert len(DEFAULT_TARGETS) > 0, "No targets loaded — config.py and config.example.py both missing"
    assert abs(sum(DEFAULT_TARGETS.values()) - 100.0) < 0.1


# ── UT-14: Delta calculation ─────────────────────────────────────────────

def test_delta_calculation():
    delta = calc_delta(23.7, 50.0)
    assert abs(delta - (-26.3)) < 0.01
