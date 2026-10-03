"""Contract table, rule-based contract selection, and settlement panels (HYPOTHESIS.md Section 4).

- Expiries come from the exchange instrument definitions (Databento `expiration`,
  converted to the Chicago calendar date), never from hard-coded calendars.
- A contract is eligible at t only if its definition had been published by t.
- Contracts are labelled root + month code + 4-digit year (LEZ2014), because raw symbols
  repeat every decade (LEZ4 = Dec 2014 and Dec 2024). A contract may have more than one
  instrument_id and more than one published expiry; selection uses the expiry as
  published on or before t.
- Settlement = statistics stat_type 3: per instrument and trading date (ts_ref), the
  last record flagged final; if none is flagged final, the last record received
  (final=False, so it can be counted). Before CME's MDP 3.0 cutover (2017-05-21) the
  feed rarely sets the final bit, but the last record received is the evening (final)
  publication and all records agree on price on 99.9% of contract-days (checked
  2026-10-02). Records with a null ts_ref or a price <= 0 (unsettled far-deferred
  contracts in 2010) are dropped.
- In-sample by default: nothing dated on or after oos_start is returned unless oos=True.
"""
from __future__ import annotations

from functools import lru_cache

import pandas as pd

from src.config import PROCESSED, RAW, RAW_OOS, load_config, oos_start

ROOTS = ("LE", "GF", "ZC")
CASH_SETTLED = {"GF"}
MONTH_CODES = "FGHJKMNQUVXZ"
CHICAGO = "America/Chicago"


def _read(name: str, oos: bool) -> pd.DataFrame:
    dirs = [RAW, RAW_OOS] if oos else [RAW]
    parts = [pd.read_parquet(d / name) for d in dirs if (d / name).exists()]
    if not parts:
        raise FileNotFoundError(f"{name} not found; run `python data/download.py --pull all --yes`")
    return pd.concat(parts, ignore_index=True)


def _to_date(ts: pd.Series) -> pd.Series:
    """UTC timestamp with date precision (ts_ref) -> naive date."""
    return ts.dt.tz_localize(None).dt.normalize() if ts.dt.tz is not None else ts.dt.normalize()


@lru_cache(maxsize=2)
def definition_versions(oos: bool = False) -> pd.DataFrame:
    """Every published version of every outright's definition: one row per
    (contract, instrument_id, last_trade_date) with the Chicago date it was first and last seen.

    Versions matter: CME lists November feeder contracts with the last Thursday of the month
    and corrects the expiry to the Thursday before Thanksgiving about two weeks later; and a
    contract can be re-listed under a new instrument_id (ZCN2014 in July 2010)."""
    rows = []
    for root in ROOTS:
        d = _read(f"{root}_definition.parquet", oos)
        d["last_trade_date"] = d["expiration"].dt.tz_convert(CHICAGO).dt.tz_localize(None).dt.normalize()
        d["seen"] = d["ts_recv"].dt.tz_convert(CHICAGO).dt.tz_localize(None).dt.normalize()
        d["contract"] = (root + d["maturity_month"].map(lambda m: MONTH_CODES[int(m) - 1])
                         + d["maturity_year"].astype(int).astype(str))
        v = (d.groupby(["contract", "instrument_id", "raw_symbol", "last_trade_date"], as_index=False)
               .agg(known_from=("seen", "min"), last_seen=("seen", "max"),
                    maturity_year=("maturity_year", "last"), maturity_month=("maturity_month", "last"),
                    size=("unit_of_measure_qty", "max"), tick=("min_price_increment", "max"),
                    unit=("unit_of_measure", "last"), display_factor=("display_factor", "last")))
        v.insert(0, "root", root)
        rows.append(v)
    v = pd.concat(rows, ignore_index=True)
    # CME recycles instrument_ids across products (19296 was GFK2 in 2011-12, LEZ9 in 2018-19),
    # so uniqueness is required within a root; settlements are read per root.
    if v.groupby(["root", "instrument_id"])["contract"].nunique().gt(1).any():
        raise RuntimeError("an instrument_id maps to more than one contract within a root")
    # Expiry versions of a contract must follow each other in time (no flip-flopping).
    for c, g in v.groupby("contract"):
        spans = g.groupby("last_trade_date").agg(a=("known_from", "min"), b=("last_seen", "max")).sort_values("a")
        if len(spans) > 1 and (spans["a"].iloc[1:].to_numpy() <= spans["b"].iloc[:-1].to_numpy()).any():
            raise RuntimeError(f"{c}: overlapping expiry versions\n{spans}")
    if not oos:
        v = v[v["known_from"] < oos_start()]
    return v.reset_index(drop=True)


@lru_cache(maxsize=2)
def contract_table(oos: bool = False) -> pd.DataFrame:
    """One row per outright contract: [root, contract, raw_symbol, last_trade_date (latest published),
    known_from, size, tick ($/unit), unit, n_ids, n_ltd_versions]."""
    v = definition_versions(oos)
    latest = v.sort_values("last_seen").groupby("contract").tail(1).set_index("contract")
    agg = v.groupby("contract").agg(root=("root", "first"), known_from=("known_from", "min"),
                                    maturity_year=("maturity_year", "last"),
                                    maturity_month=("maturity_month", "last"),
                                    size=("size", "max"), tick=("tick", "max"),
                                    n_sizes=("size", lambda x: x[x > 0].nunique()),
                                    unit=("unit", "last"), display_factor=("display_factor", "last"),
                                    n_ids=("instrument_id", "nunique"),
                                    n_ltd_versions=("last_trade_date", "nunique"))
    tbl = agg.join(latest[["raw_symbol", "last_trade_date"]]).reset_index()
    cols = ["root", "contract", "raw_symbol", "last_trade_date", "known_from", "maturity_year",
            "maturity_month", "size", "tick", "n_sizes", "unit", "display_factor", "n_ids", "n_ltd_versions"]
    return tbl[cols].sort_values(["root", "last_trade_date"]).reset_index(drop=True)


def select(root: str, t, min_days: int, oos: bool = False) -> pd.Series | None:
    """First contract of `root` known at t whose last trade date, as published by t,
    is >= t + min_days. Returns that contract's row with the as-of-t last trade date."""
    t = pd.Timestamp(t)
    v = definition_versions(oos)
    v = v[(v["root"] == root) & (v["known_from"] <= t)]
    asof = v.sort_values("known_from").groupby("contract").tail(1)
    c = asof[asof["last_trade_date"] >= t + pd.Timedelta(days=min_days)]
    if c.empty:
        return None
    pick = c.loc[c["last_trade_date"].idxmin()]
    row = contract_table(oos).set_index("contract").loc[pick["contract"]].copy()
    row["contract"] = pick["contract"]
    row["last_trade_date"] = pick["last_trade_date"]
    return row


def select_series(root: str, dates, min_days: int, oos: bool = False) -> pd.Series:
    """Selected contract label for each date (None if none qualifies)."""
    out = {}
    for t in pd.DatetimeIndex(dates):
        row = select(root, t, min_days, oos)
        out[t] = None if row is None else row["contract"]
    return pd.Series(out, name=f"{root}_{min_days}d")


def settlements(root: str, oos: bool = False) -> pd.DataFrame:
    """Long table [date, contract, price, final, actual, cash_final] of daily settlements ($/unit).
    cash_final marks GF's cash settlement, dated the business day after the last trade date."""
    cache = PROCESSED / f"{root}_settle{'_oos' if oos else ''}.parquet"
    if cache.exists():
        s = pd.read_parquet(cache)
    else:
        cfg = load_config()["databento"]
        s = _read(f"{root}_statistics.parquet", oos)
        s = s[(s["stat_type"] == cfg["settlement_stat_type"]) & (s["update_action"] == 1)
              & s["ts_ref"].notna() & (s["price"] > 0)]
        s = s.assign(date=_to_date(s["ts_ref"]),
                     final=(s["stat_flags"] & cfg["settlement_final_flag"]) != 0,
                     actual=(s["stat_flags"] & 2) != 0)
        # Prefer the last final record per (instrument, date); else the last preliminary one.
        s = s.sort_values(["instrument_id", "date", "final", "ts_recv", "sequence"])
        s = s.drop_duplicates(["instrument_id", "date"], keep="last")
        ids = definition_versions(oos).query("root == @root")[["instrument_id", "contract"]].drop_duplicates()
        ltd = contract_table(oos)[["contract", "last_trade_date"]]
        s = s.merge(ids, on="instrument_id", how="inner").merge(ltd, on="contract", how="left")
        if s.duplicated(["contract", "date"]).any():
            raise RuntimeError(f"{root}: two instrument_ids settle the same contract on the same date")
        s = s[["date", "contract", "instrument_id", "price", "final", "actual", "last_trade_date"]]
        # Feeder cattle is cash-settled to the CME Feeder Cattle Index; CME publishes that final
        # cash settlement dated the next business day after the last trade date. LE and ZC are
        # physically delivered and must not settle after their last trade date.
        after = s["date"] > s["last_trade_date"]
        s = s.assign(cash_final=after)
        if after.any():
            late = s[after]
            next_day = late["date"] <= late["last_trade_date"] + pd.offsets.BDay(1)
            one_each = not late["contract"].duplicated().any()
            if root not in CASH_SETTLED or not (next_day.all() and one_each):
                raise RuntimeError(f"{root}: settlement dated after a contract's last trade date\n{late}")
        PROCESSED.mkdir(parents=True, exist_ok=True)
        s.to_parquet(cache, index=False)
    if not oos:
        s = s[s["date"] < oos_start()]
    return s.reset_index(drop=True)


def settle_panel(root: str, oos: bool = False) -> pd.DataFrame:
    """Date x contract matrix of settlement prices."""
    return settlements(root, oos).pivot(index="date", columns="contract", values="price").sort_index()
