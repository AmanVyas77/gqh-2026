"""Audit the in-sample contract definitions and settlements.

Checks
- Contract size and tick from the exchange definitions vs config.yaml.
- Each definition's last trade date vs CME's published rules (LE: last business day of the
  month; GF: last Thursday, Thursday before Thanksgiving in November, one week earlier when a
  holiday falls in that week; ZC: business day before the 15th).
- Contracts with more than one published expiry or instrument_id.
- Last trading-day settlement vs definition last trade date.
- Dates a product is missing from the feed while another product settled.
- What each settlement-cleaning rule removed or changed, and whether any out-of-range print
  was ever used.
- Day-over-day settlement moves above 10% within a contract.

Writes results/tables/data_audit.txt and prints the same report.
Usage: python data/audit.py
"""
from __future__ import annotations

import io
import sys
from contextlib import redirect_stdout
from pathlib import Path

import pandas as pd
from dateutil.easter import easter
from pandas.tseries.holiday import USFederalHolidayCalendar

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import contracts  # noqa: E402
from src.config import RAW, RESULTS, load_config, oos_start  # noqa: E402

# Loose $/unit bounds used only to flag prints for review.
FLAG_BOUNDS = {"LE": (0.5, 3.0), "GF": (0.5, 4.0), "ZC": (1.5, 10.0)}
MDP3_START = pd.Timestamp("2017-05-21")


def _gf_rule(year: int, month: int, holidays: set) -> pd.Timestamp:
    thursdays = [d for d in pd.date_range(f"{year}-{month:02d}-01", periods=31)
                 if d.month == month and d.weekday() == 3]
    if month == 11:
        return thursdays[3] - pd.Timedelta(days=7)          # Thursday before Thanksgiving
    rule = thursdays[-1]
    while any(rule - pd.Timedelta(days=k) in holidays for k in range(7)):
        rule -= pd.Timedelta(days=7)
    return rule


def check_specs(tbl: pd.DataFrame, cfg: dict) -> None:
    print("== Contract size and tick vs config.yaml ==")
    for root in contracts.ROOTS:
        t = tbl[tbl["root"] == root]
        spec = cfg["specs"][root]
        sizes = sorted(float(x) for x in t.loc[t["size"] > 0, "size"].unique())
        ticks = sorted(float(x) for x in t["tick"].round(8).unique())
        zero = t.loc[t["size"] == 0, "contract"].tolist()
        ok = sizes == [spec["size"]] and ticks == [round(spec["tick_cents"] / 100, 8)]
        print(f"{root}: {len(t)} contracts; size {sizes} {t['unit'].iloc[0]}, tick ${ticks} -> "
              f"{'matches' if ok else 'MISMATCH'} config ({spec['size']}, ${spec['tick_cents'] / 100})"
              + (f"; defined with size 0: {zero}" if zero else ""))


def check_ltd_rules(tbl: pd.DataFrame) -> None:
    print("\n== Definition last trade date vs CME rules ==")
    years = range(tbl["last_trade_date"].dt.year.min(), tbl["last_trade_date"].dt.year.max() + 1)
    holidays = set(USFederalHolidayCalendar().holidays(str(years.start), str(years.stop))) | {
        pd.Timestamp(easter(y)) - pd.Timedelta(days=2) for y in years}      # + Good Friday
    cal = pd.DatetimeIndex(sorted(set().union(*(set(contracts.settlements(r)["date"]) for r in contracts.ROOTS))))
    for root in contracts.ROOTS:
        t = tbl[(tbl["root"] == root) & (tbl["last_trade_date"] < cal.max())]
        bad = []
        for _, r in t.iterrows():
            y, m = int(r["maturity_year"]), int(r["maturity_month"])
            month_days = cal[(cal.year == y) & (cal.month == m)]
            if root == "LE":
                rule = month_days.max()
            elif root == "GF":
                rule = _gf_rule(y, m, holidays)
            else:
                rule = month_days[month_days.day < 15].max()
            if rule != r["last_trade_date"]:
                bad.append(f"{r['contract']} rule {rule.date()} definition {r['last_trade_date'].date()}")
        print(f"{root}: {len(t)} expired contracts checked, {len(bad)} differ" + "".join(f"\n    {b}" for b in bad))


def check_versions() -> None:
    print("\n== Contracts with more than one published expiry or instrument_id ==")
    v = contracts.definition_versions()
    tbl = contracts.contract_table()
    for c in tbl[(tbl["n_ltd_versions"] > 1) | (tbl["n_ids"] > 1)]["contract"]:
        g = v[v["contract"] == c].sort_values("known_from")
        parts = [f"id {int(r.instrument_id)} expiry {r.last_trade_date.date()} published "
                 f"{r.known_from.date()}..{r.last_seen.date()} size {r['size']:g}" for _, r in g.iterrows()]
        print(f"  {c}: " + "; ".join(parts))


def check_last_settlement(tbl: pd.DataFrame) -> None:
    print("\n== Last trading-day settlement vs definition last trade date (expired contracts) ==")
    for root in contracts.ROOTS:
        s = contracts.settlements(root)
        n_cash = int(s["cash_final"].sum())
        last = s[~s["cash_final"]].groupby("contract")["date"].max()
        t = tbl[(tbl["root"] == root) & (tbl["last_trade_date"] < oos_start() - pd.Timedelta(days=1))
                & (tbl["last_trade_date"] > pd.Timestamp("2010-06-14"))].set_index("contract")
        diff = (last.reindex(t.index) - t["last_trade_date"]).dt.days
        miss = {c: int(d) for c, d in diff[diff.ne(0)].items()}
        print(f"{root}: {len(t)} contracts, {len(miss)} differ (days) {miss}"
              + (f"; GF cash-final records dated the next business day: {n_cash}" if root in contracts.CASH_SETTLED else ""))


def check_feed_gaps() -> None:
    print("\n== Dates a product is missing while another product settled ==")
    dates = {r: set(contracts.settlements(r).query("~cash_final")["date"]) for r in contracts.ROOTS}
    union = set().union(*dates.values())
    for r in contracts.ROOTS:
        miss = sorted(union - dates[r])
        print(f"{r}: {len(miss)} dates {[d.strftime('%Y-%m-%d') for d in miss]}")


def check_cleaning(cfg: dict) -> None:
    print("\n== Settlement cleaning: what each rule removed or changed (outright futures) ==")
    rows, notes = [], []
    for root in contracts.ROOTS:
        s = pd.read_parquet(RAW / f"{root}_statistics.parquet")
        s = s[(s["stat_type"] == cfg["databento"]["settlement_stat_type"]) & (s["update_action"] == 1)].copy()
        s["date"] = s["ts_ref"].dt.tz_localize(None).dt.normalize()
        s["final"] = (s["stat_flags"] & cfg["databento"]["settlement_final_flag"]) != 0
        null_ref = s["ts_ref"].isna()
        nonpos = ~null_ref & (s["price"] <= 0)
        dated = s[~null_ref]
        day_max = dated.groupby(["instrument_id", "date"])["price"].max()
        kept = dated[dated["price"] > 0].sort_values(["instrument_id", "date", "final", "ts_recv", "sequence"])
        chosen = kept.drop_duplicates(["instrument_id", "date"], keep="last").set_index(["instrument_id", "date"])
        first = kept.sort_values("ts_recv").groupby(["instrument_id", "date"])["price"].first()
        nuniq = kept.groupby(["instrument_id", "date"])["price"].nunique()
        change = (chosen["price"] - first.reindex(chosen.index)).abs()
        change = change[change > 1e-12]
        lo, hi = FLAG_BOUNDS[root]
        oob = kept[(kept["price"] < lo) | (kept["price"] > hi)]
        oob_used = chosen[(chosen["price"] < lo) | (chosen["price"] > hi)]
        post = chosen.reset_index()
        post = post[post["date"] >= MDP3_START]
        rows.append({
            "root": root,
            "settlement records": len(s),
            "dropped: null trading date": int(null_ref.sum()),
            "dropped: price <= 0": int(nonpos.sum()),
            "contract-days lost (only <=0 prints)": int((day_max <= 0).sum()),
            "contract-days kept": len(chosen),
            "days with disagreeing prints": int((nuniq > 1).sum()),
            "days where used price != first print": len(change),
            "largest such correction ($/unit)": round(float(change.max()), 5) if len(change) else 0.0,
            "out-of-range prints": len(oob),
            "out-of-range prints used": len(oob_used),
            "post-2017-05-21 days without a final flag": int((~post["final"]).sum()),
        })
        if root == "LE" and len(oob):
            hi_le = oob[oob["price"] > hi]
            notes.append(f"LE prints above ${hi}/lb: {len(hi_le)} on {sorted(hi_le['date'].dt.strftime('%Y-%m-%d').unique())}, "
                         f"instrument_ids {sorted(int(i) for i in hi_le['instrument_id'].unique())}")
    print(pd.DataFrame(rows).set_index("root").T.to_string())
    for n in notes:
        print(n)


def check_jumps() -> None:
    print("\n== Day-over-day settlement moves above 10% within a contract ==")
    for root in contracts.ROOTS:
        r = contracts.settle_panel(root).pct_change(fill_method=None).stack()
        big = r[r.abs() > 0.10]
        print(f"{root}: {len(big)}" + "".join(f"\n    {d.date()} {c} {v:+.1%}" for (d, c), v in big.head(10).items()))


def main() -> str:
    cfg = load_config()
    tbl = contracts.contract_table()
    buf = io.StringIO()
    with redirect_stdout(buf):
        print(f"Data audit (in-sample, trading dates before {oos_start().date()})\n")
        check_specs(tbl, cfg)
        check_ltd_rules(tbl)
        check_versions()
        check_last_settlement(tbl)
        check_feed_gaps()
        check_cleaning(cfg)
        check_jumps()
    report = buf.getvalue()
    out = RESULTS / "tables" / "data_audit.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report)
    print(report)
    return report


if __name__ == "__main__":
    main()
