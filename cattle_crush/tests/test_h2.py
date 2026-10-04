"""H2 primary specification: data cutoff, signal timing, and exposure limits (HYPOTHESIS_H2.md)."""
import pandas as pd
import pytest

from src import contracts, h2
from src.config import oos_start

pytestmark = pytest.mark.skipif(not (contracts.RAW / "h2_equities.parquet").exists(), reason="H2 data not downloaded")


def test_equities_end_before_holdout():
    assert h2.equities().index.max() < oos_start()


def test_signal_contract_rule_and_lookback():
    sig = h2.cattle_signal()
    ltd = contracts.contract_table().set_index("contract")["last_trade_date"]
    assert ((ltd.reindex(sig["contract"]).to_numpy() - sig["base_date"].to_numpy()) >= pd.Timedelta(days=45)).all()
    assert sig["s"].first_valid_index().strftime("%Y-%m") == "2013-07"      # 36 prior months from 2010-07


def test_rebalance_timing_and_gross_limit():
    px = h2.equities()
    rets = px.pct_change().iloc[1:]
    rb = h2.rebalances(h2.cattle_signal(), rets, 1e6)
    assert (rb["exec_date"] > rb["signal_date"]).all()
    assert (rb["exec_date"] < oos_start()).all()
    gross = rb[[c for c in rb.columns if c.startswith("tgt_")]].abs().sum(axis=1) / 1e6
    assert gross.max() <= h2.GROSS_CAP + 1e-9
    assert (rb["w"].abs() <= h2.MAX_W).all()
