"""Dollar costs match the tick math in HYPOTHESIS.md Section 7."""
import pytest

from src import costs


@pytest.mark.parametrize("root,tick_value,one_x,two_x", [
    ("LE", 10.00, 12.50, 25.00),     # 0.025 c x 40,000 lb
    ("GF", 12.50, 15.00, 30.00),     # 0.025 c x 50,000 lb
    ("ZC", 12.50, 15.00, 30.00),     # 0.25 c x 5,000 bu
])
def test_cost_per_side(root, tick_value, one_x, two_x):
    assert costs.tick_value(root) == pytest.approx(tick_value)
    assert costs.cost_per_side(root) == pytest.approx(one_x)
    assert costs.cost_per_side(root, multiplier=2) == pytest.approx(two_x)
    assert costs.cost_per_side(root, fee_only=True) == pytest.approx(2.50)
    assert costs.trade_cost(root, -3.5) == pytest.approx(3.5 * one_x)
