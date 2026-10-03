"""Transaction costs (HYPOTHESIS.md Section 7): per contract per side, ticks x tick value + fee."""
from __future__ import annotations

from src.config import load_config


def tick_value(root: str, cfg: dict | None = None) -> float:
    """Dollar value of one tick: tick_cents / 100 x contract size."""
    spec = (cfg or load_config())["specs"][root]
    return spec["tick_cents"] / 100 * spec["size"]


def cost_per_side(root: str, multiplier: float = 1.0, fee_only: bool = False, cfg: dict | None = None) -> float:
    """Dollar cost of one contract, one side. multiplier=2 is the stress test (2 ticks + $5.00).
    fee_only drops slippage (GF cash-final closes in Variant B, Deviation Log 2026-10-03)."""
    cfg = cfg or load_config()
    c = cfg["costs"]
    slippage = 0.0 if fee_only else c["ticks_per_side"] * tick_value(root, cfg)
    return multiplier * (slippage + c["fee_per_contract_side"])


def trade_cost(root: str, contracts: float, multiplier: float = 1.0, fee_only: bool = False,
               cfg: dict | None = None) -> float:
    """Dollar cost of trading |contracts| (fractional allowed) on one side."""
    return abs(contracts) * cost_per_side(root, multiplier, fee_only, cfg)
