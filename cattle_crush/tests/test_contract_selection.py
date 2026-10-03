"""Hand-checked contract selection (HYPOTHESIS.md Section 4).

Expected contracts and last trade dates below were worked out by hand from CME's
published rules, independently of the Databento definitions the code uses:
  LE: last business day of the contract month
  GF: last Thursday of the contract month
  ZC: business day prior to the 15th calendar day of the contract month
Dates were chosen so that t + min_days falls near a last trade date.
"""
import pandas as pd
import pytest

from src import contracts
from src.config import data_start

pytestmark = pytest.mark.skipif(
    not (contracts.RAW / "LE_definition.parquet").exists(), reason="raw data not downloaded")

# (t, root, min_days, expected contract, expected last trade date, why)
CASES = [
    ("2013-06-28", "LE", 150, "LEZ2013", "2013-12-31", "t+150 = 2013-11-25; LEV3 ends 2013-10-31"),
    ("2013-06-28", "GF", 30, "GFQ2013", "2013-08-29", "t+30 = 2013-07-28; GF has no July contract"),
    ("2013-06-28", "ZC", 75, "ZCU2013", "2013-09-13", "t+75 = 2013-09-11; Sep 15 is a Sunday"),
    ("2015-11-30", "LE", 150, "LEJ2016", "2016-04-29", "t+150 = 2016-04-28; one day to spare"),
    ("2015-11-30", "GF", 30, "GFF2016", "2016-01-28", "t+30 = 2015-12-30"),
    ("2015-11-30", "ZC", 75, "ZCH2016", "2016-03-14", "t+75 = 2016-02-13"),
    ("2018-12-31", "LE", 150, "LEM2019", "2019-06-28", "t+150 = 2019-05-30; LEJ9 ends 2019-04-30"),
    ("2018-12-31", "GF", 30, "GFF2019", "2019-01-31", "t+30 = 2019-01-30; one day to spare"),
    ("2018-12-31", "ZC", 75, "ZCK2019", "2019-05-14", "t+75 = 2019-03-16; ZCH9 ends 2019-03-14"),
    ("2020-04-30", "LE", 150, "LEV2020", "2020-10-30", "t+150 = 2020-09-27; LEQ0 ends 2020-08-31"),
    ("2020-04-30", "GF", 30, "GFQ2020", "2020-08-27", "t+30 = 2020-05-30; GFK0 ends 2020-05-28"),
    ("2020-04-30", "ZC", 75, "ZCN2020", "2020-07-14", "t+75 = 2020-07-14; exactly on the boundary"),
    ("2024-09-30", "LE", 150, "LEG2025", "2025-02-28", "t+150 = 2025-02-27; LEZ4 ends 2024-12-31"),
    ("2024-09-30", "GF", 30, "GFV2024", "2024-10-31", "t+30 = 2024-10-30; one day to spare"),
    ("2024-09-30", "ZC", 75, "ZCH2025", "2025-03-14", "t+75 = 2024-12-14; ZCZ4 ends 2024-12-13"),
]


@pytest.mark.parametrize("t,root,min_days,contract,ltd,why", CASES)
def test_hand_checked_selection(t, root, min_days, contract, ltd, why):
    row = contracts.select(root, t, min_days)
    assert row is not None, why
    assert row["contract"] == contract, why
    assert row["last_trade_date"] == pd.Timestamp(ltd), why


def test_selected_contract_settles_on_t():
    """Every hand-checked selection has a settlement price on t itself."""
    for t, root, min_days, contract, *_ in CASES:
        panel = contracts.settle_panel(root)
        assert pd.notna(panel.loc[pd.Timestamp(t), contract]), (t, contract)


# Contracts whose last-trade-date settlement is missing from the feed (checked 2026-10-03).
KNOWN_GAPS = {
    "LEZ2014": "no settlement record and no trades on 2014-12-31; last settlement 2014-12-30",
    "GFU2014": "livestock feed gap 2014-09-23..25 (no LE/GF settlements or trades); cash final 2014-09-26",
}


def test_final_settlement_on_last_trade_date():
    """A contract's last trading-day settlement falls on its definition last trade date
    (GF's cash-settlement record, dated the next business day, is excluded)."""
    tbl = contracts.contract_table()
    tbl = tbl[~tbl["contract"].isin(KNOWN_GAPS)]
    cutoff = contracts.oos_start()
    for root in contracts.ROOTS:
        s = contracts.settlements(root)
        s = s[~s["cash_final"]]
        last = s.groupby("contract")["date"].max()
        expired = tbl[(tbl["root"] == root) & (tbl["last_trade_date"] < cutoff - pd.Timedelta(days=1))
                      & (tbl["last_trade_date"] > data_start() + pd.Timedelta(days=7))]
        mism = expired.set_index("contract")["last_trade_date"].ne(last.reindex(expired["contract"]))
        assert not mism.any(), f"{root}: {list(mism[mism].index)}"
