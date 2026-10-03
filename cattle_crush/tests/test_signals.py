"""Signals (HYPOTHESIS.md Section 5) and the P1 outcome construction, on synthetic data where
possible. No placement outcomes are regressed here."""
import numpy as np
import pandas as pd
import pytest

from src import contracts, mechanism, signals
from src.config import oos_start

needs_data = pytest.mark.skipif(
    not (contracts.RAW / "LE_definition.parquet").exists(), reason="raw data not downloaded")


def _monthly(values, start="2010-06"):
    return pd.Series(values, index=pd.period_range(start, periods=len(values), freq="M").to_timestamp("M"))


def test_zscore_uses_only_prior_window():
    x = _monthly(np.random.default_rng(1).normal(size=80))
    z = signals.zscore(x, 36)
    assert z.iloc[:36].isna().all() and z.iloc[36:].notna().all()
    t = 50
    window = x.iloc[t - 36:t]
    assert z.iloc[t] == pytest.approx((x.iloc[t] - window.mean()) / window.std(ddof=1))
    bumped = x.copy()
    bumped.iloc[t + 1:] += 100.0                       # change the future: z up to t is unchanged
    pd.testing.assert_series_equal(signals.zscore(bumped, 36).iloc[:t + 1], z.iloc[:t + 1])


def test_seasonal_component():
    months = pd.period_range("2010-01", periods=96, freq="M")
    x = pd.Series(np.arange(96, dtype=float) + 10 * (months.month == 3), index=months.to_timestamp("M"))
    s = signals.seasonal_component(x, 5)
    assert s.iloc[:60].isna().all()
    t = 62                                            # March 2015: prior Marches at t-12k
    assert s.iloc[t] == pytest.approx(np.mean([x.iloc[t - 12 * k] for k in range(1, 6)]))


def test_seasonal_component_rejects_gaps():
    x = _monthly(np.arange(80.0)).drop(_monthly(np.arange(80.0)).index[10])
    with pytest.raises(ValueError):
        signals.seasonal_component(x, 5)


def test_p1_outcome_construction():
    """Placements growing 1% a month: every YoY change over a 3-month window is 12%."""
    plac = pd.Series(np.exp(0.01 * np.arange(60)), index=pd.period_range("2012-01", periods=60, freq="M"))
    y = mechanism.p1_outcome(plac)
    assert y.dropna().round(12).eq(0.12).all()
    assert y.index[y.notna()].min() == pd.Period("2012-12", "M")    # needs m-11..m-9
    assert y.index[y.notna()].max() == pd.Period("2016-09", "M")    # needs m+1..m+3


@needs_data
def test_k_invariance():
    a = signals.month_end_signals(k=0.0)
    b = signals.month_end_signals(k=350.0)
    for col in ("z", "z_sa", "z_seasonal_only", "z_le"):
        pd.testing.assert_series_equal(a[col], b[col], check_exact=False, rtol=1e-12, atol=1e-12)


@needs_data
def test_first_valid_signals_and_oos_guard():
    sig = signals.month_end_signals()
    assert sig.index.max() < oos_start()
    assert sig["z"].first_valid_index().strftime("%Y-%m") == "2013-06"        # 36 months after 2010-06
    assert sig["z_sa"].first_valid_index().strftime("%Y-%m") == "2018-06"     # + 5 years for seasonal mean


@needs_data
def test_p3_sample_rules():
    """P3 uses only outcomes before oos_start and drops the LEZ2014-affected month-ends (Deviation Log)."""
    sig = signals.month_end_signals()
    d = mechanism.p3_data(sig)
    assert (d["sale_ltd"] < oos_start()).all()
    assert "LEZ2014" not in set(d["sale_contract"])
    _, verdict = mechanism.p3_kill_test(sig)
    assert verdict["dropped_month_ends"] == ["2014-06-30", "2014-07-31", "2014-12-31"]
    assert (d["spot_change"] - d["fut_change"] - d["sale_minus_front"]).abs().max() < 1e-12


@needs_data
def test_leg_contributions_sum_to_margin_change():
    legs, _ = mechanism.leg_decomposition(signals.month_end_signals())
    parts = legs[["LE (sale value)", "GF (feeder cost)", "ZC (corn cost)"]].sum(axis=1)
    assert (parts - legs["dM (total)"]).abs().max() < 1e-9


@pytest.mark.parametrize("asof,known", [
    ("2019-06-04", "2019-06-10"),   # normal week: Friday release, known Monday (+6)
    ("2014-12-23", "2014-12-31"),   # Dec 25-26 closures: released Tue 12-30, known Wed (+8)
    ("2016-11-22", "2016-11-30"),   # Thanksgiving: released Mon, +8 is conservative
    ("2015-06-30", "2015-07-08"),   # July 3 holiday: released Mon 7-6
    ("2023-02-07", "2023-03-22"),   # ION incident backlog
    ("2013-10-08", "2013-11-12"),   # 2013 shutdown backlog
])
def test_cftc_known_from(asof, known):
    got = signals.cftc_known_from(pd.Series([pd.Timestamp(asof)]))
    assert got.iloc[0] == pd.Timestamp(known)
