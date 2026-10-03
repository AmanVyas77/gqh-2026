"""Feeding margin M_t (HYPOTHESIS.md Section 3)."""
import pandas as pd
import pytest

from src import contracts, margin
from src.config import oos_start

pytestmark = pytest.mark.skipif(
    not (contracts.RAW / "LE_definition.parquet").exists(), reason="raw data not downloaded")

HAND_DATES = ["2013-06-28", "2015-11-30", "2018-12-31", "2020-04-30", "2024-09-30"]


def test_bushels():
    assert margin.bushels(800, 1400, 6.0, 56) == pytest.approx(64.2857, abs=1e-4)   # Section 3 table
    assert margin.bushels(800, 1400, 5.5, 56) == pytest.approx(58.9286, abs=1e-4)
    assert margin.bushels(800, 1400, 6.5, 56) == pytest.approx(69.6429, abs=1e-4)


def test_hand_calculation():
    """2024-09-30: LEG2025 $1.8585/lb, GFV2024 $2.4620/lb, ZCH2025 $4.4125/bu (checkpoint table)."""
    m = margin.margin_at("2024-09-30")
    assert (m["sale_contract"], m["feeder_contract"], m["corn_contract"]) == ("LEG2025", "GFV2024", "ZCH2025")
    expected = 1400 * 1.8585 - 800 * 2.4620 - (600 * 6.0 / 56) * 4.4125 - 350
    assert m["margin"] == pytest.approx(expected, abs=1e-6)


def test_daily_path_matches_single_date_path():
    daily = margin.margin_daily().set_index("date")
    for t in HAND_DATES:
        a, b = daily.loc[pd.Timestamp(t)], margin.margin_at(t)
        for leg in ("sale", "feeder", "corn"):
            assert a[f"{leg}_contract"] == b[f"{leg}_contract"]
        assert a["margin"] == pytest.approx(b["margin"], abs=1e-9)


def test_month_end_skips_feed_gap():
    """ZC has no data on 2020-06-30, so June 2020's month-end is 2020-06-29 (Deviation Log)."""
    me = margin.month_end(margin.margin_daily())
    june = me[me["date"].dt.to_period("M") == pd.Period("2020-06")]["date"].iloc[0]
    assert june == pd.Timestamp("2020-06-29")


def test_in_sample_only():
    assert margin.margin_daily()["date"].max() < oos_start()
