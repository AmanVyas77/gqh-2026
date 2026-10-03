"""Backtest engine mechanics on synthetic prices (no market data needed)."""
import numpy as np
import pandas as pd
import pytest

from src import backtest


@pytest.fixture(autouse=True)
def _temp_trial_log(tmp_path, monkeypatch):
    monkeypatch.setenv("CATTLE_TRIAL_LOG", str(tmp_path / "trial_log.csv"))


def _market(prices: dict, locked=(), cash_final=None):
    """prices: contract -> list of (date, price); all contracts are LE."""
    m = backtest.Market.__new__(backtest.Market)
    m.roots, m.size = ("LE",), {"LE": 40000}
    frame = pd.DataFrame({c: pd.Series({pd.Timestamp(d): p for d, p in v}) for c, v in prices.items()})
    m.px = {"LE": frame.sort_index()}
    m.cash_final = cash_final or {}
    m.has_cash_final = {c for c, _ in m.cash_final}
    m.locked = {(pd.Timestamp(d), c) for d, c in locked}
    m.root_of = {c: "LE" for c in prices}
    m.ltd = {c: pd.Timestamp("2030-01-01") for c in prices}
    m.dates = list(m.px["LE"].index)
    return m


D = pd.bdate_range("2020-01-01", periods=8)


def test_pnl_roll_and_costs():
    m = _market({"A": [(d, 1.00 + 0.01 * i) for i, d in enumerate(D[:6])],
                 "B": [(d, 2.00 + 0.02 * i) for i, d in enumerate(D)]})
    rbs = [backtest.Rebalance(D[0], {"LE": ("A", 2.0)}), backtest.Rebalance(D[3], {"LE": ("B", -1.0)})]
    res = backtest.run(m, rbs, capital=1e6)
    t = res.trades
    assert list(t["date"]) == [D[1], D[4], D[4]]                    # next-day executions; roll on one day
    assert t["cost"].sum() == pytest.approx((2 + 2 + 1) * 12.50)      # open A, close A, open B
    daily = res.daily.set_index("date")
    assert daily.loc[D[2], "pnl"] == pytest.approx(2 * 40000 * 0.01)  # long 2 A, +1 cent
    assert daily.loc[D[4], "pnl"] == pytest.approx(2 * 40000 * 0.01)  # A held into the roll settlement
    assert daily.loc[D[5], "pnl"] == pytest.approx(-1 * 40000 * 0.02) # short 1 B
    assert daily.index[0] == D[1]                                     # returns start at first execution


def test_locked_day_defers_whole_trade():
    m = _market({"A": [(d, 1.0) for d in D], "B": [(d, 2.0) for d in D]}, locked=[(D[4], "A")])
    rbs = [backtest.Rebalance(D[0], {"LE": ("A", 1.0)}), backtest.Rebalance(D[3], {"LE": ("B", 1.0)})]
    res = backtest.run(m, rbs, capital=1e6)
    roll = res.trades[res.trades["signal_date"] == D[3]]
    assert set(roll["date"]) == {D[5]}                                 # both legs moved to the next day
    assert res.events["deferred_trades"] == 1 and res.events["deferred_days"] == 1


def test_feed_gap_carries_pnl_to_next_settlement():
    prices = [(d, 1.0 + 0.01 * i) for i, d in enumerate(D) if i != 3]  # no settlement on D[3]
    m = _market({"A": prices})
    res = backtest.run(m, [backtest.Rebalance(D[0], {"LE": ("A", 1.0)})], capital=1e6)
    daily = res.daily.set_index("date")
    assert D[3] not in daily.index or daily.loc[D[3], "pnl"] == 0
    assert daily.loc[D[4], "pnl"] == pytest.approx(40000 * 0.02)      # two days of change at once


def test_overlay_halves_and_restores():
    # Price path: long 10 contracts loses 20% of capital, then recovers.
    path = [1.0, 1.0, 0.9, 0.5, 0.5, 0.5, 1.4, 1.4]     # halved: +0.9 x 5 x 40,000 lb = +18%
    m = _market({"A": list(zip(D, path))})
    rbs = [backtest.Rebalance(d, {"LE": ("A", 10.0)}) for d in (D[0], D[3], D[6])]
    res = backtest.run(m, rbs, capital=1e6, overlay=True)
    scales = res.rebalances.set_index("signal_date")["scale"]
    assert scales[D[0]] == 1.0 and scales[D[3]] == 0.5                # 20% drawdown -> halve
    assert scales[D[6]] == 1.0                                        # back within 7.5% -> restore


def _gf_market(cash_final: bool):
    """One GF contract expiring on D[3] (settles through D[3]), held from D[1]."""
    m = _market({"G": [(d, 2.0 + 0.01 * i) for i, d in enumerate(D[:4])]},
                cash_final={("G", D[4]): 2.05} if cash_final else None)
    m.roots, m.size, m.root_of = ("GF",), {"GF": 50000}, {"G": "GF"}
    m.px = {"GF": m.px["LE"]}
    m.ltd = {"G": D[3]}
    m.dates = list(D)
    return m


def test_gf_closed_at_cash_final_fee_only():
    m = _gf_market(cash_final=True)
    res = backtest.run(m, [backtest.Rebalance(D[0], {"GF": ("G", -1.0)})], capital=1e6)
    close = res.trades[res.trades["reason"] == "cash_final"].iloc[0]
    assert close["date"] == D[4] and close["price"] == 2.05 and close["cost"] == 2.50
    assert res.events["gf_cash_final_closes"] == 1


def test_gf_closed_at_last_settlement_without_cash_final():
    m = _gf_market(cash_final=False)
    res = backtest.run(m, [backtest.Rebalance(D[0], {"GF": ("G", -1.0)})], capital=1e6)
    close = res.trades[res.trades["reason"] == "ltd_settlement_no_cash_final"].iloc[0]
    assert close["price"] == pytest.approx(2.03) and close["cost"] == 2.50
    assert res.events["gf_ltd_settlement_closes"] == 1
